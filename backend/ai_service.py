import os
import io
import json
import httpx
import speech_recognition as sr
from pydub import AudioSegment


def _get_host():
    host = os.environ.get("DATABRICKS_HOST", "")
    if host and not host.startswith("http"):
        host = f"https://{host}"
    return host


def _get_token():
    """Get an access token, handling both PAT and OAuth M2M."""
    token = os.environ.get("DATABRICKS_TOKEN", "")
    if token:
        return token

    client_id = os.environ.get("DATABRICKS_CLIENT_ID", "")
    client_secret = os.environ.get("DATABRICKS_CLIENT_SECRET", "")
    host = _get_host()

    if client_id and client_secret and host:
        try:
            resp = httpx.post(
                f"{host}/oidc/v1/token",
                data={"grant_type": "client_credentials", "scope": "all-apis"},
                auth=(client_id, client_secret),
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()["access_token"]
        except Exception as e:
            print(f"OAuth token error: {e}")
    return ""


def _get_model():
    """Get the configured model name from DB or default."""
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
    """Call LLM via Databricks FMAPI (text only)."""
    host = _get_host()
    token = _get_token()
    model = _get_model()

    url = f"{host}/serving-endpoints/{model}/invocations"

    payload = {
        "anthropic_version": "2023-06-01",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }

    resp = httpx.post(
        url,
        json=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=120,
    )
    if resp.status_code != 200:
        print(f"FMAPI error {resp.status_code}: {resp.text[:500]}")
        resp.raise_for_status()

    data = resp.json()

    # Handle both Anthropic and OpenAI response formats
    if "content" in data and isinstance(data["content"], list):
        return "\n".join(b["text"] for b in data["content"] if b.get("type") == "text")
    if "choices" in data:
        return data["choices"][0]["message"]["content"]
    return str(data)


def transcribe_audio(audio_bytes: bytes, file_name: str) -> dict:
    """Transcribe audio using Google Speech Recognition API.

    Converts any audio format to WAV via pydub, then transcribes
    using Google's free Speech Recognition service.
    """
    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else "mp3"

    # Convert to WAV using pydub
    try:
        audio_segment = AudioSegment.from_file(io.BytesIO(audio_bytes), format=ext)
    except Exception:
        audio_segment = AudioSegment.from_file(io.BytesIO(audio_bytes))

    # Split into chunks of ~55 seconds for API limits
    chunk_duration_ms = 55_000
    chunks = [audio_segment[i:i + chunk_duration_ms]
              for i in range(0, len(audio_segment), chunk_duration_ms)]

    recognizer = sr.Recognizer()
    transcription_parts = []

    for i, chunk in enumerate(chunks):
        wav_buffer = io.BytesIO()
        chunk.export(wav_buffer, format="wav")
        wav_buffer.seek(0)

        with sr.AudioFile(wav_buffer) as source:
            audio_data = recognizer.record(source)

        try:
            text = recognizer.recognize_google(audio_data, language="pt-BR")
            transcription_parts.append(text)
        except sr.UnknownValueError:
            transcription_parts.append(f"[trecho {i+1}: audio nao reconhecido]")
        except sr.RequestError as e:
            print(f"Google STT error: {e}")
            transcription_parts.append(f"[trecho {i+1}: erro no servico de transcricao]")

    full_text = " ".join(transcription_parts)

    if not full_text.strip() or all("[" in p for p in transcription_parts):
        # Fallback: ask Claude to generate analysis context
        size_kb = len(audio_bytes) / 1024
        full_text = f"[Transcricao automatica indisponivel para {file_name} ({size_kb:.0f}KB)]"

    return {"text": full_text}


def analyze_transcription(transcription: str, categories: list[str]) -> dict:
    """Analyze transcription for summary, sentiment, category, topics, action items."""
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

    text = _call_llm(prompt, max_tokens=2048, temperature=0.1)
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(text)


def generate_detailed_report(transcription: str, summary: str, category: str) -> str:
    """Generate a detailed narrative report for PDF export."""
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
