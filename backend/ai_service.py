import os
import io
import json
import struct
import httpx
import speech_recognition as sr
import miniaudio

# Ensure ffmpeg binary is in PATH (downloaded by start.sh to /tmp/ffmpeg-bin)
_ffbin = "/tmp/ffmpeg-bin"
if os.path.isdir(_ffbin) and _ffbin not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _ffbin + ":" + os.environ.get("PATH", "")


def _get_host():
    host = os.environ.get("DATABRICKS_HOST", "")
    if host and not host.startswith("http"):
        host = f"https://{host}"
    return host


def _get_token():
    token = os.environ.get("DATABRICKS_TOKEN", "")
    if token:
        return token
    client_id = os.environ.get("DATABRICKS_CLIENT_ID", "")
    client_secret = os.environ.get("DATABRICKS_CLIENT_SECRET", "")
    host = _get_host()
    if client_id and client_secret and host:
        try:
            resp = httpx.post(f"{host}/oidc/v1/token",
                data={"grant_type": "client_credentials", "scope": "all-apis"},
                auth=(client_id, client_secret), timeout=15)
            resp.raise_for_status()
            return resp.json()["access_token"]
        except Exception as e:
            print(f"OAuth token error: {e}")
    return ""


def _get_model():
    try:
        from .database import get_cursor
        with get_cursor() as cur:
            cur.execute("SELECT value FROM app_settings WHERE key = 'llm_model'")
            row = cur.fetchone()
            if row:
                return row["value"]
    except Exception:
        pass
    return os.environ.get("LLM_MODEL", "databricks-claude-sonnet-4-6")


def _call_llm(prompt: str, max_tokens: int = 2048, temperature: float = 0.1) -> str:
    host = _get_host()
    token = _get_token()
    model = _get_model()
    url = f"{host}/serving-endpoints/{model}/invocations"
    payload = {
        "anthropic_version": "2023-06-01",
        "max_tokens": max_tokens, "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    resp = httpx.post(url, json=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, timeout=120)
    if resp.status_code != 200:
        print(f"FMAPI error {resp.status_code}: {resp.text[:500]}")
        resp.raise_for_status()
    data = resp.json()
    if "content" in data and isinstance(data["content"], list):
        return "\n".join(b["text"] for b in data["content"] if b.get("type") == "text")
    if "choices" in data:
        return data["choices"][0]["message"]["content"]
    return str(data)


def convert_to_wav(audio_bytes: bytes, file_name: str) -> tuple:
    """Convert any audio format to 16kHz mono 16-bit WAV.

    Tries miniaudio first (MP3/FLAC/Vorbis), falls back to pydub+ffmpeg (Opus/others).
    Returns (wav_bytes, format_detected).
    """
    if audio_bytes[:4] == b'RIFF':
        return audio_bytes, "wav"

    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else "mp3"

    # Try miniaudio first (fast, no external deps for mp3/flac/vorbis)
    try:
        decoded = miniaudio.decode(audio_bytes,
                                   output_format=miniaudio.SampleFormat.SIGNED16,
                                   nchannels=1,
                                   sample_rate=16000)
        pcm_data = decoded.samples.tobytes()
        return _pcm_to_wav(pcm_data), ext
    except Exception as e:
        print(f"miniaudio failed for {file_name}: {e}, trying ffmpeg...")

    # Fallback: pydub + ffmpeg (handles Opus, AAC, etc.)
    from pydub import AudioSegment
    audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format=ext if ext != "ogg" else "ogg")
    audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
    buf = io.BytesIO()
    audio.export(buf, format="wav")
    return buf.getvalue(), ext


def _pcm_to_wav(pcm_data: bytes) -> bytes:
    """Wrap raw 16kHz mono 16-bit PCM in a WAV header."""
    sr_val, ch, sw = 16000, 1, 2
    data_size = len(pcm_data)
    header = struct.pack('<4sI4s4sIHHIIHH4sI',
        b'RIFF', 36 + data_size, b'WAVE',
        b'fmt ', 16, 1, ch, sr_val,
        sr_val * ch * sw, ch * sw, sw * 8,
        b'data', data_size)
    return header + pcm_data


def transcribe_audio(audio_bytes: bytes, file_name: str) -> dict:
    """Transcribe audio using Gemini 2.5 Flash via Databricks FMAPI.

    Gemini accepts audio via image_url data URI. Auto-converts to WAV first.
    """
    import base64

    # Convert to WAV if needed
    if audio_bytes[:4] != b'RIFF':
        try:
            audio_bytes, fmt = convert_to_wav(audio_bytes, file_name)
            print(f"Converted {file_name} ({fmt}) to WAV: {len(audio_bytes)} bytes")
        except Exception as e:
            print(f"Conversion failed for {file_name}: {e}")
            return {"text": f"[Erro na conversao: {file_name} - {e}]"}

    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

    host = _get_host()
    token = _get_token()

    resp = httpx.post(
        f"{host}/serving-endpoints/databricks-gemini-2-5-flash/invocations",
        json={
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:audio/wav;base64,{audio_b64}"}},
                {"type": "text", "text": (
                    "Transcreva este audio palavra por palavra em portugues brasileiro. "
                    "Inclua mudancas de falante se detectavel. "
                    "Retorne APENAS o texto da transcricao, sem comentarios extras."
                )},
            ]}],
            "max_tokens": 4096,
        },
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=180,
    )
    if resp.status_code != 200:
        print(f"Gemini transcription error {resp.status_code}: {resp.text[:300]}")
        return {"text": f"[Erro na transcricao: {resp.status_code}]"}

    data = resp.json()
    text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    if not text.strip():
        return {"text": f"[Audio sem fala reconhecida: {file_name}]"}

    return {"text": text}


def analyze_transcription(transcription: str, categories: list[str]) -> dict:
    categories_str = ", ".join(categories)
    prompt = f"""Analyze the following customer service call transcription and provide a structured analysis.

Available categories: {categories_str}

Transcription:
---
{transcription}
---

Respond ONLY with a valid JSON object (no markdown, no code blocks) with these exact fields:
{{
    "summary": "A concise 2-3 sentence summary of the call in Portuguese",
    "category": "One of the available categories that best fits",
    "sentiment": "positive, negative, or neutral",
    "sentiment_score": 0.0 to 1.0 (0=very negative, 0.5=neutral, 1=very positive),
    "key_topics": ["topic1", "topic2", "topic3"],
    "urgency_level": "low, normal, high, or critical",
    "language_detected": "pt, en, or es",
    "speaker_count": estimated number of speakers,
    "action_items": ["action1", "action2"]
}}"""
    text = _call_llm(prompt, max_tokens=2048, temperature=0.1).strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(text)


def generate_detailed_report(transcription: str, summary: str, category: str) -> str:
    prompt = f"""Based on this customer service call analysis, write a professional detailed report in Portuguese (Brazil).

Category: {category}
Summary: {summary}
Full Transcription:
{transcription}

Write a structured report with these sections:
1. Resumo Executivo
2. Detalhes da Interacao
3. Pontos Principais Identificados
4. Analise de Sentimento
5. Recomendacoes e Proximos Passos

Be professional and concise. Use bullet points where appropriate."""
    return _call_llm(prompt, max_tokens=3000, temperature=0.3)
