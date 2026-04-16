import os
import json
import base64
import httpx


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


def _call_anthropic(messages: list, max_tokens: int = 4096, temperature: float = 0.1) -> str:
    """Call Claude via Databricks FMAPI using Anthropic native format (supports audio)."""
    host = _get_host()
    token = _get_token()

    # Use the Anthropic-compatible endpoint on Databricks
    url = f"{host}/serving-endpoints/databricks-claude-sonnet-4-6/invocations"

    payload = {
        "anthropic_version": "2023-06-01",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages,
    }

    resp = httpx.post(
        url,
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        timeout=180,
    )
    resp.raise_for_status()
    data = resp.json()

    # Anthropic format: content is a list of blocks
    content = data.get("content", [])
    text_parts = [block["text"] for block in content if block.get("type") == "text"]
    return "\n".join(text_parts)


def transcribe_audio(audio_bytes: bytes, file_name: str) -> dict:
    """Transcribe audio using Claude via Anthropic native API (supports audio input)."""
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else "wav"
    mime_map = {
        "wav": "audio/wav", "mp3": "audio/mpeg", "ogg": "audio/ogg",
        "flac": "audio/flac", "m4a": "audio/mp4", "webm": "audio/webm",
    }
    media_type = mime_map.get(ext, "audio/mpeg")

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "media",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": audio_b64,
                    },
                },
                {
                    "type": "text",
                    "text": (
                        "Transcreva este audio palavra por palavra em portugues. "
                        "Inclua mudancas de falante se detectavel. "
                        "Retorne APENAS o texto da transcricao, sem comentarios extras."
                    ),
                },
            ],
        }
    ]

    transcription = _call_anthropic(messages, max_tokens=4096, temperature=0.0)
    return {"text": transcription}


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
    "summary": "A concise 2-3 sentence summary of the call",
    "category": "One of the available categories that best fits",
    "sentiment": "positive, negative, or neutral",
    "sentiment_score": 0.0 to 1.0 (0=very negative, 0.5=neutral, 1=very positive),
    "key_topics": ["topic1", "topic2", "topic3"],
    "urgency_level": "low, normal, high, or critical",
    "language_detected": "pt, en, or es",
    "speaker_count": estimated number of speakers,
    "action_items": ["action1", "action2"]
}}"""

    text = _call_anthropic(
        [{"role": "user", "content": prompt}],
        max_tokens=2048,
        temperature=0.1,
    )

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

    return _call_anthropic(
        [{"role": "user", "content": prompt}],
        max_tokens=3000,
        temperature=0.3,
    )
