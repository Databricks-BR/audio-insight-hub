import os
import json
import base64
import datetime
import traceback
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .database import get_cursor, init_database
from .ai_service import transcribe_audio, analyze_transcription, generate_detailed_report
from .pdf_service import generate_analysis_pdf, generate_batch_pdf

app = FastAPI(title="Audio Insight Hub API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    try:
        init_database()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Warning: Could not initialize database: {e}")


# ---- Models ----

class CategoryCreate(BaseModel):
    name: str
    color: str = "#6366f1"
    icon: str = "tag"


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None


class SettingUpdate(BaseModel):
    key: str
    value: str


class BatchRequest(BaseModel):
    volume_path: str
    category_ids: list[int] = []
    selected_files: list[str] = []  # if empty, process all


# ---- Health ----

@app.get("/api/debug/env")
async def debug_env():
    """Temporary: check which DATABRICKS env vars are available."""
    import os
    keys = [k for k in os.environ if k.startswith("DATABRICKS")]
    return {k: ("***" if "SECRET" in k or "TOKEN" in k or "PASSWORD" in k else os.environ[k]) for k in sorted(keys)}


@app.get("/api/health")
async def health():
    db_ok = False
    try:
        with get_cursor() as cur:
            cur.execute("SELECT 1")
            db_ok = True
    except Exception:
        pass
    return {"status": "ok", "database": db_ok, "version": "1.0.0"}


# ---- Categories ----

@app.get("/api/categories")
async def list_categories():
    with get_cursor() as cur:
        cur.execute("SELECT * FROM categories ORDER BY name")
        return cur.fetchall()


@app.post("/api/categories")
async def create_category(cat: CategoryCreate):
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO categories (name, color, icon) VALUES (%s, %s, %s) RETURNING *",
            (cat.name, cat.color, cat.icon),
        )
        return cur.fetchone()


@app.put("/api/categories/{cat_id}")
async def update_category(cat_id: int, cat: CategoryUpdate):
    updates, values = [], []
    if cat.name is not None:
        updates.append("name = %s"); values.append(cat.name)
    if cat.color is not None:
        updates.append("color = %s"); values.append(cat.color)
    if cat.icon is not None:
        updates.append("icon = %s"); values.append(cat.icon)
    if not updates:
        raise HTTPException(400, "No fields to update")
    values.append(cat_id)
    with get_cursor() as cur:
        cur.execute(f"UPDATE categories SET {', '.join(updates)} WHERE id = %s RETURNING *", values)
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Category not found")
        return row


@app.delete("/api/categories/{cat_id}")
async def delete_category(cat_id: int):
    with get_cursor() as cur:
        cur.execute("DELETE FROM categories WHERE id = %s", (cat_id,))
        return {"deleted": True}


# ---- Shared processing logic ----

def _get_category_names(category_ids: list[int] | None = None) -> list[str]:
    """Get category names, optionally filtered by IDs."""
    with get_cursor() as cur:
        if category_ids:
            placeholders = ",".join(["%s"] * len(category_ids))
            cur.execute(f"SELECT name FROM categories WHERE id IN ({placeholders}) ORDER BY name", category_ids)
        else:
            cur.execute("SELECT name FROM categories ORDER BY name")
        return [r["name"] for r in cur.fetchall()]


def _process_and_save(file_name: str, audio_bytes: bytes, category_names: list[str],
                      file_path: str | None = None) -> dict:
    """Transcribe, analyze, and save a single audio file."""
    transcript_result = transcribe_audio(audio_bytes, file_name)
    transcription = transcript_result["text"]

    analysis = analyze_transcription(transcription, category_names)

    category_id = None
    with get_cursor() as cur:
        cur.execute("SELECT id FROM categories WHERE name = %s", (analysis.get("category", ""),))
        row = cur.fetchone()
        if row:
            category_id = row["id"]

    with get_cursor() as cur:
        cur.execute(
            """INSERT INTO audio_analyses
            (file_name, file_path, file_size, transcription, summary, category_id,
             sentiment, sentiment_score, key_topics, urgency_level,
             language_detected, speaker_count, action_items, processed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *""",
            (
                file_name, file_path, len(audio_bytes),
                transcription, analysis.get("summary", ""), category_id,
                analysis.get("sentiment", "neutral"),
                analysis.get("sentiment_score", 0.5),
                analysis.get("key_topics", []),
                analysis.get("urgency_level", "normal"),
                analysis.get("language_detected", "pt"),
                analysis.get("speaker_count", 1),
                analysis.get("action_items", []),
                datetime.datetime.now(),
            ),
        )
        saved = cur.fetchone()

    return {
        **_serialize_row(saved),
        "category_name": analysis.get("category", ""),
    }


# ---- Audio Upload (single file) ----

@app.post("/api/audio/upload")
async def upload_and_process(
    file: UploadFile = File(...),
    category_ids: str = Form(default=""),
):
    """Upload an audio file, transcribe and analyze. Runs in thread to not block."""
    import asyncio
    if not file.filename:
        raise HTTPException(400, "No file provided")

    audio_bytes = await file.read()
    cat_ids = [int(x) for x in category_ids.split(",") if x.strip()] if category_ids else []

    try:
        categories = _get_category_names(cat_ids if cat_ids else None)
        result = await asyncio.to_thread(_process_and_save, file.filename, audio_bytes, categories)
        return result
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Processing error: {str(e)}")


# ---- Batch (Volume) Processing with SSE (non-blocking) ----

@app.post("/api/audio/batch")
async def process_batch_sse(req: BatchRequest):
    """Process audio files with real-time SSE updates. Runs heavy work in threads."""
    import asyncio
    from databricks.sdk import WorkspaceClient
    from starlette.responses import StreamingResponse
    from .ai_service import convert_to_wav

    try:
        w = WorkspaceClient()
    except Exception as e:
        raise HTTPException(500, f"Could not connect to Databricks: {e}")

    categories = _get_category_names(req.category_ids if req.category_ids else None)
    audio_extensions = {".wav", ".mp3", ".ogg", ".flac", ".m4a", ".webm"}

    try:
        files = list(w.files.list_directory_contents(req.volume_path))
    except Exception as e:
        raise HTTPException(400, f"Cannot list volume: {e}")

    audio_files = [
        f for f in files
        if f.path and ("." + f.path.rsplit(".", 1)[-1].lower() if "." in f.path else "") in audio_extensions
    ]
    if req.selected_files:
        selected_set = set(req.selected_files)
        audio_files = [f for f in audio_files if f.path.rsplit("/", 1)[-1] in selected_set]
    if not audio_files:
        raise HTTPException(400, "No audio files found")

    event_queue = asyncio.Queue()

    def _process_file(f, idx, total):
        """Run in thread — does all heavy I/O and CPU work."""
        file_name = f.path.rsplit("/", 1)[-1]
        try:
            event_queue.put_nowait({"type": "status", "file": file_name, "index": idx, "total": total,
                                    "stage": "downloading", "message": f"Baixando {file_name}..."})
            resp = w.files.download(f.path)
            audio_bytes = resp.contents.read()

            ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
            if ext != "wav" and audio_bytes[:4] != b'RIFF':
                event_queue.put_nowait({"type": "status", "file": file_name, "index": idx, "total": total,
                                        "stage": "converting", "message": f"Convertendo {ext.upper()} para WAV..."})
                audio_bytes, _ = convert_to_wav(audio_bytes, file_name)

            event_queue.put_nowait({"type": "status", "file": file_name, "index": idx, "total": total,
                                    "stage": "transcribing", "message": f"Transcrevendo {file_name}..."})
            transcript_result = transcribe_audio(audio_bytes, file_name)
            transcription = transcript_result["text"]

            event_queue.put_nowait({"type": "status", "file": file_name, "index": idx, "total": total,
                                    "stage": "analyzing", "message": f"Analisando sentimento e categorias..."})
            analysis = analyze_transcription(transcription, categories)

            event_queue.put_nowait({"type": "status", "file": file_name, "index": idx, "total": total,
                                    "stage": "saving", "message": f"Salvando resultados..."})
            category_id = None
            with get_cursor() as cur:
                cur.execute("SELECT id FROM categories WHERE name = %s", (analysis.get("category", ""),))
                row = cur.fetchone()
                if row:
                    category_id = row["id"]
            with get_cursor() as cur:
                cur.execute(
                    """INSERT INTO audio_analyses
                    (file_name, file_path, file_size, transcription, summary, category_id,
                     sentiment, sentiment_score, key_topics, urgency_level,
                     language_detected, speaker_count, action_items, processed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *""",
                    (file_name, f.path, len(audio_bytes),
                     transcription, analysis.get("summary", ""), category_id,
                     analysis.get("sentiment", "neutral"), analysis.get("sentiment_score", 0.5),
                     analysis.get("key_topics", []), analysis.get("urgency_level", "normal"),
                     analysis.get("language_detected", "pt"), analysis.get("speaker_count", 1),
                     analysis.get("action_items", []), datetime.datetime.now()),
                )
                saved = cur.fetchone()

            result_data = {**_serialize_row(saved), "category_name": analysis.get("category", "")}
            event_queue.put_nowait({"type": "completed", "file": file_name, "index": idx, "total": total,
                                    "result": result_data})
            return True
        except Exception as e:
            traceback.print_exc()
            event_queue.put_nowait({"type": "error", "file": file_name, "index": idx, "total": total,
                                    "error": str(e)})
            return False

    async def run_batch():
        """Run all files sequentially in a background thread."""
        total = len(audio_files)
        ok, fail = 0, 0
        for idx, f in enumerate(audio_files):
            success = await asyncio.to_thread(_process_file, f, idx, total)
            if success:
                ok += 1
            else:
                fail += 1
        event_queue.put_nowait({"type": "done", "processed": ok, "errors": fail})

    async def event_stream():
        # Start processing in background task
        task = asyncio.create_task(run_batch())

        # Stream events as they arrive
        while True:
            try:
                event = await asyncio.wait_for(event_queue.get(), timeout=1.0)
                yield f"data: {json.dumps(event, default=str)}\n\n"
                if event.get("type") == "done":
                    break
            except asyncio.TimeoutError:
                # Send keepalive so connection doesn't drop
                yield ": keepalive\n\n"
                if task.done():
                    # Drain remaining events
                    while not event_queue.empty():
                        event = event_queue.get_nowait()
                        yield f"data: {json.dumps(event, default=str)}\n\n"
                        if event.get("type") == "done":
                            return
                    break

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ---- List Volume Files (for preview) ----

@app.get("/api/volume/list")
async def list_volume_files(path: str = Query(...)):
    """List audio files in a volume for preview."""
    from databricks.sdk import WorkspaceClient

    try:
        w = WorkspaceClient()
        files = list(w.files.list_directory_contents(path))
    except Exception as e:
        raise HTTPException(400, f"Cannot list volume: {e}")

    audio_extensions = {".wav", ".mp3", ".ogg", ".flac", ".m4a", ".webm"}
    audio_files = []
    for f in files:
        if not f.path:
            continue
        ext = "." + f.path.rsplit(".", 1)[-1].lower() if "." in f.path else ""
        if ext in audio_extensions:
            audio_files.append({
                "name": f.path.rsplit("/", 1)[-1],
                "path": f.path,
                "size": getattr(f, "file_size", None),
            })

    return {"files": audio_files, "total": len(audio_files)}


# ---- Serve audio from volume (for player) ----

@app.get("/api/audio/stream")
async def stream_audio(path: str = Query(...)):
    """Stream an audio file from a Databricks Volume for the player."""
    from databricks.sdk import WorkspaceClient

    try:
        w = WorkspaceClient()
        resp = w.files.download(path)
        audio_bytes = resp.contents.read()
    except Exception as e:
        raise HTTPException(400, f"Cannot read file: {e}")

    ext = path.rsplit(".", 1)[-1].lower() if "." in path else "mp3"
    mime_map = {
        "wav": "audio/wav", "mp3": "audio/mpeg", "ogg": "audio/ogg",
        "flac": "audio/flac", "m4a": "audio/mp4", "webm": "audio/webm",
    }
    return Response(content=audio_bytes, media_type=mime_map.get(ext, "audio/mpeg"))


# ---- Analyses ----

@app.get("/api/analyses")
async def list_analyses(
    category_id: Optional[int] = None,
    sentiment: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    conditions, params = [], []
    if category_id:
        conditions.append("a.category_id = %s"); params.append(category_id)
    if sentiment:
        conditions.append("a.sentiment = %s"); params.append(sentiment)
    if search:
        conditions.append("(a.file_name ILIKE %s OR a.transcription ILIKE %s OR a.summary ILIKE %s)")
        params.extend([f"%{search}%"] * 3)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    with get_cursor() as cur:
        cur.execute(f"SELECT COUNT(*) as total FROM audio_analyses a {where}", params)
        total = cur.fetchone()["total"]

        cur.execute(
            f"""SELECT a.*, c.name as category_name, c.color as category_color, c.icon as category_icon
                FROM audio_analyses a LEFT JOIN categories c ON a.category_id = c.id
                {where} ORDER BY a.created_at DESC LIMIT %s OFFSET %s""",
            params + [limit, offset],
        )
        rows = cur.fetchall()

    return {"total": total, "items": _serialize_rows(rows)}


@app.get("/api/analyses/{analysis_id}")
async def get_analysis(analysis_id: int):
    with get_cursor() as cur:
        cur.execute(
            """SELECT a.*, c.name as category_name, c.color as category_color, c.icon as category_icon
               FROM audio_analyses a LEFT JOIN categories c ON a.category_id = c.id
               WHERE a.id = %s""",
            (analysis_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Analysis not found")
        return _serialize_row(row)


@app.delete("/api/analyses/{analysis_id}")
async def delete_analysis(analysis_id: int):
    with get_cursor() as cur:
        cur.execute("DELETE FROM audio_analyses WHERE id = %s", (analysis_id,))
        return {"deleted": True}


@app.delete("/api/analyses")
async def delete_all_analyses():
    """Delete ALL analyses from the database."""
    with get_cursor() as cur:
        cur.execute("DELETE FROM audio_analyses")
        return {"deleted_all": True}


# ---- Available Models ----

@app.get("/api/models")
async def list_models():
    """List available FMAPI serving endpoints."""
    from databricks.sdk import WorkspaceClient
    try:
        w = WorkspaceClient()
        endpoints = list(w.serving_endpoints.list())
        models = [
            {"name": e.name, "state": e.state.ready.value if e.state and e.state.ready else "UNKNOWN"}
            for e in endpoints
            if e.name and ("claude" in e.name.lower() or "gpt" in e.name.lower()
                           or "llama" in e.name.lower() or "qwen" in e.name.lower()
                           or "gemma" in e.name.lower())
        ]
        return sorted(models, key=lambda m: m["name"])
    except Exception as e:
        return [
            {"name": "databricks-claude-sonnet-4-6", "state": "READY"},
            {"name": "databricks-claude-sonnet-4-5", "state": "READY"},
            {"name": "databricks-claude-haiku-4-5", "state": "READY"},
            {"name": "databricks-gpt-5-4", "state": "READY"},
            {"name": "databricks-gpt-5-4-mini", "state": "READY"},
        ]


# ---- Dashboard Stats ----

@app.get("/api/dashboard/stats")
async def dashboard_stats():
    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) as total FROM audio_analyses")
        total = cur.fetchone()["total"]
        cur.execute("SELECT sentiment, COUNT(*) as count FROM audio_analyses GROUP BY sentiment")
        sentiments = {r["sentiment"]: r["count"] for r in cur.fetchall()}
        cur.execute(
            """SELECT c.name, c.color, COUNT(a.id) as count FROM categories c
               LEFT JOIN audio_analyses a ON a.category_id = c.id
               GROUP BY c.name, c.color ORDER BY count DESC""")
        categories = cur.fetchall()
        cur.execute("SELECT urgency_level, COUNT(*) as count FROM audio_analyses GROUP BY urgency_level")
        urgency = {r["urgency_level"]: r["count"] for r in cur.fetchall()}
        cur.execute("SELECT AVG(sentiment_score) as avg_score FROM audio_analyses")
        avg_sentiment = cur.fetchone()["avg_score"]
        cur.execute(
            """SELECT DATE(created_at) as date, COUNT(*) as count FROM audio_analyses
               WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
               GROUP BY DATE(created_at) ORDER BY date""")
        timeline = cur.fetchall()
        cur.execute(
            """SELECT unnest(key_topics) as topic, COUNT(*) as count FROM audio_analyses
               GROUP BY topic ORDER BY count DESC LIMIT 10""")
        top_topics = cur.fetchall()

    return {
        "total_analyses": total, "sentiments": sentiments,
        "categories": [dict(r) for r in categories], "urgency": urgency,
        "avg_sentiment_score": float(avg_sentiment) if avg_sentiment else 0.5,
        "timeline": [{"date": str(r["date"]), "count": r["count"]} for r in timeline],
        "top_topics": [dict(r) for r in top_topics],
    }


# ---- PDF Export ----

@app.get("/api/export/pdf/{analysis_id}")
async def export_single_pdf(analysis_id: int):
    with get_cursor() as cur:
        cur.execute(
            "SELECT a.*, c.name as category_name FROM audio_analyses a LEFT JOIN categories c ON a.category_id = c.id WHERE a.id = %s",
            (analysis_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Analysis not found")
    data = dict(row)
    data["category"] = data.pop("category_name", "N/A")
    return Response(content=generate_analysis_pdf(data), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="analise_{analysis_id}.pdf"'})


@app.get("/api/export/pdf/all")
async def export_all_pdf():
    with get_cursor() as cur:
        cur.execute("SELECT a.*, c.name as category_name FROM audio_analyses a LEFT JOIN categories c ON a.category_id = c.id ORDER BY a.created_at DESC")
        rows = cur.fetchall()
    if not rows:
        raise HTTPException(404, "No analyses found")
    analyses = []
    for row in rows:
        d = dict(row); d["category"] = d.pop("category_name", "N/A"); analyses.append(d)
    return Response(content=generate_batch_pdf(analyses), media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="relatorio_completo.pdf"'})


# ---- Settings ----

@app.get("/api/settings")
async def get_settings():
    with get_cursor() as cur:
        cur.execute("SELECT * FROM app_settings")
        return {r["key"]: r["value"] for r in cur.fetchall()}


@app.put("/api/settings")
async def update_setting(setting: SettingUpdate):
    with get_cursor() as cur:
        cur.execute(
            """INSERT INTO app_settings (key, value, updated_at) VALUES (%s, %s, CURRENT_TIMESTAMP)
               ON CONFLICT (key) DO UPDATE SET value = %s, updated_at = CURRENT_TIMESTAMP""",
            (setting.key, setting.value, setting.value),
        )
        return {"key": setting.key, "value": setting.value}


# ---- Serve Frontend ----

frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
if os.path.isdir(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


# ---- Helpers ----

def _serialize_row(row):
    d = dict(row)
    for k, v in d.items():
        if isinstance(v, (datetime.datetime, datetime.date)):
            d[k] = v.isoformat()
    return d

def _serialize_rows(rows):
    return [_serialize_row(r) for r in rows]
