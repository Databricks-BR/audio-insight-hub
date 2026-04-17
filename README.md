# Audio Insight Hub

A full-stack Databricks App for AI-powered audio transcription, sentiment analysis, and categorization — backed by **Lakebase** (managed PostgreSQL).

## Overview

Audio Insight Hub converts audio files into actionable intelligence. It transcribes audio using Gemini 2.5 Flash, then analyzes the transcription with Claude Sonnet (via Databricks FMAPI) to extract sentiment, categories, key topics, urgency levels, and action items.

The app supports **two processing modes**:
- **Single upload** — Drag-and-drop a file and get instant results
- **Batch processing** — Select multiple files from a Databricks Volume and process them with real-time SSE progress

**Key capabilities:**
- **Transcription** — Automatic speech-to-text via Gemini 2.5 Flash (supports WAV, MP3, OGG, FLAC, M4A, WebM)
- **Sentiment analysis** — Positive, negative, or neutral with confidence score (0–1)
- **Categorization** — User-defined categories (complaint, praise, suggestion, etc.)
- **Key topics** — Automatic extraction of main topics discussed
- **Urgency levels** — Low, normal, high, critical classification
- **Language detection** — Portuguese, English, Spanish
- **Speaker count** — Estimates number of speakers in the audio
- **Action items** — Extracts actionable recommendations
- **PDF reports** — Single analysis or batch export
- **Multi-language UI** — Portuguese, English, Spanish

## Architecture

```
+--------------------------------------------------+
|              Browser (React SPA)                  |
|  Dashboard | Process | Analyses | Settings        |
+--------------------------------------------------+
              | REST API + SSE
              v
+--------------------------------------------------+
|          FastAPI Backend (Python)                  |
|  Transcription (Gemini) -> Analysis (Claude)      |
|  Audio conversion + real-time SSE progress        |
+--------------------------------------------------+
       |              |              |
       v              v              v
+------------+  +------------+  +------------+
| Lakebase   |  | FMAPI      |  | Volumes    |
| PostgreSQL |  | Gemini +   |  | source     |
| (3 tables) |  | Claude     |  | audio      |
+------------+  +------------+  +------------+
```

## Key Features

| Feature | Description |
|---------|-------------|
| **AI transcription** | Audio-to-text via Gemini 2.5 Flash with native audio support |
| **Sentiment analysis** | Positive/negative/neutral with confidence score |
| **Custom categories** | User-created categories with colors and icons for classification |
| **Batch processing** | Select files from Databricks Volume, process with real-time progress |
| **Single upload** | Drag-and-drop audio file for instant analysis |
| **Audio preview** | Play files directly in the browser before processing |
| **SSE progress** | Real-time per-file status updates during batch processing |
| **Processing queue** | Status page with live stages: downloading → converting → transcribing → analyzing → saving |
| **Dashboard** | KPIs, sentiment distribution, category breakdown, timeline, top topics |
| **PDF export** | Single analysis or batch report with formatted output |
| **Configurable AI model** | Select any FMAPI endpoint via Settings (Claude, GPT, Llama, Gemini, etc.) |
| **Dark mode** | Persistent dark/light theme toggle |
| **Multi-language UI** | Portuguese, English, Spanish — switchable in sidebar |
| **Audio format support** | WAV, MP3, OGG, FLAC, M4A, WebM — auto-conversion to 16kHz mono WAV |

## Technologies

### Backend
| Technology | Version | Purpose |
|-----------|---------|---------|
| Python | 3.11+ | Backend language |
| FastAPI | >= 0.115 | Async REST API framework |
| Uvicorn | >= 0.30 | ASGI server |
| psycopg2 | >= 2.9 | PostgreSQL driver (Lakebase) |
| Databricks SDK | >= 0.36 | Auth, Volumes, Serving Endpoints |
| httpx | >= 0.27 | HTTP client for FMAPI calls |
| miniaudio | >= 1.61 | Fast MP3/FLAC/Vorbis decoding |
| pydub | >= 0.25 | Audio format conversion (with ffmpeg) |
| SpeechRecognition | >= 3.10 | Audio processing utilities |
| fpdf2 | >= 2.8 | PDF report generation |

### Frontend
| Technology | Version | Purpose |
|-----------|---------|---------|
| React | 19.2 | UI framework (SPA) |
| Vite | 8.0 | Build tool and dev server |
| Tailwind CSS | 3.4 | Utility-first styling |
| Lucide React | 0.577 | Icon library |
| PostCSS + Autoprefixer | - | CSS postprocessing |
| Server-Sent Events | - | Real-time batch progress streaming |
| i18n (custom) | - | Multi-language support (PT/EN/ES) |

### AI / Audio
| Technology | Purpose |
|-----------|---------|
| Databricks FMAPI (Gemini 2.5 Flash) | Audio transcription (native audio input) |
| Databricks FMAPI (Claude Sonnet) | Sentiment analysis, categorization, topic extraction |
| Configurable model | Default: Claude Sonnet. Changeable via Settings to any FMAPI endpoint |
| ffmpeg | Audio format conversion (downloaded at container startup) |

### Infrastructure
| Resource | Purpose |
|---------|---------|
| **Databricks Lakebase** | Managed PostgreSQL database (scales to zero) |
| Databricks Apps | App hosting (managed container) |
| Databricks Volumes | Source audio file storage |
| Serving Endpoints | FMAPI model access (transcription + analysis) |
| Service Principal | Automatic app authentication |

## Configuration (Environment Variables)

All settings are parameterizable via `app.yaml`:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABRICKS_LAKEBASE_HOST` | (required) | Lakebase endpoint host |
| `DATABRICKS_LAKEBASE_DB` | `audio_insight_hub` | Database name |
| `DATABRICKS_LAKEBASE_PORT` | `5432` | PostgreSQL port |
| `DATABRICKS_LAKEBASE_USER` | (auto from SP) | PostgreSQL username |
| `DATABRICKS_LAKEBASE_PASSWORD` | (auto from OAuth) | PostgreSQL password |
| `DATABRICKS_HOST` | (auto in Apps) | Workspace host for FMAPI |
| `DATABRICKS_TOKEN` | (auto in Apps) | Auth token |
| `DATABRICKS_CLIENT_ID` | (auto in Apps) | OAuth M2M client ID |
| `DATABRICKS_CLIENT_SECRET` | (auto in Apps) | OAuth M2M secret |
| `LLM_MODEL` | `databricks-claude-sonnet-4-6` | Analysis model endpoint |

### Authentication Fallback Chain

The app automatically resolves credentials in this order:

1. **Explicit** — `DATABRICKS_LAKEBASE_USER` + `DATABRICKS_LAKEBASE_PASSWORD`
2. **OAuth M2M** — `DATABRICKS_CLIENT_ID` + `DATABRICKS_CLIENT_SECRET` (client credentials flow)
3. **PAT token** — `DATABRICKS_TOKEN`
4. **CLI-based** — `databricks postgres generate-database-credential` (local development)

## Database Schema (PostgreSQL / Lakebase)

| Table | Purpose |
|-------|---------|
| `categories` | User-defined classification categories with name, color, and icon |
| `audio_analyses` | Full analysis results: transcription, sentiment, topics, urgency, action items |
| `app_settings` | Key-value store for app configuration (e.g., selected LLM model) |

### Default Categories (seeded on first startup)

| Category | Color |
|----------|-------|
| Reclamacao | Red |
| Elogio | Green |
| Duvida | Blue |
| Sugestao | Yellow |
| Solicitacao | Purple |
| Cancelamento | Orange |
| Informacao | Cyan |

Tables and seed data are auto-created on first startup.

## Setup

### 1. Create Lakebase Project

```bash
databricks postgres create-project audio-insight-hub \
  --json '{"spec": {"display_name": "Audio Insight Hub"}}' \
  -p PROFILE
```

### 2. Create Database

```bash
HOST=$(databricks postgres list-endpoints projects/audio-insight-hub/branches/production \
  -p PROFILE -o json | jq -r '.[0].status.hosts.host')
TOKEN=$(databricks postgres generate-database-credential \
  projects/audio-insight-hub/branches/production/endpoints/primary \
  -p PROFILE -o json | jq -r '.token')
EMAIL=$(databricks current-user me -p PROFILE -o json | jq -r '.userName')

PGPASSWORD=$TOKEN psql "host=$HOST port=5432 dbname=postgres user=$EMAIL sslmode=require" \
  -c "CREATE DATABASE audio_insight_hub;"
```

### 3. Create app.yaml

The `app.yaml` file contains credentials and is **not included in the repository** for security. Create it from the template:

```bash
cp app.yaml.template app.yaml
```

Then edit `app.yaml` and replace all `<PLACEHOLDER>` values:

| Placeholder | Description | Where to find |
|-------------|-------------|---------------|
| `<LAKEBASE_ENDPOINT_HOST>` | Lakebase endpoint hostname | `databricks postgres list-endpoints ...` |
| `<DATABASE_NAME>` | PostgreSQL database name | The database you created in step 2 |
| `<LAKEBASE_USER>` | PostgreSQL username | Service principal UUID or email |
| `<LAKEBASE_PASSWORD>` | PostgreSQL password | Set when creating the PG role |

> **Security note:** Never commit `app.yaml` with real credentials. The `.gitignore` prevents this automatically.

### 4. Build Frontend

```bash
cd frontend && npm install && npm run build
```

### 5. Deploy

```bash
databricks apps create audio-insight-hub
databricks sync . /Workspace/Users/<email>/audio-insight-hub -p PROFILE
databricks apps deploy audio-insight-hub /Workspace/Users/<email>/audio-insight-hub SNAPSHOT
```

Tables and seed data are auto-created on first startup.

## API Endpoints

### Categories
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/categories` | List all categories |
| POST | `/api/categories` | Create category |
| PUT | `/api/categories/{id}` | Update category |
| DELETE | `/api/categories/{id}` | Delete category |

### Audio Processing
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/audio/upload` | Upload and process single file (multipart) |
| POST | `/api/audio/batch` | Start batch processing with SSE progress |
| GET | `/api/volume/list?path=...` | List audio files in Databricks Volume |
| GET | `/api/audio/stream?path=...` | Stream audio file for browser playback |

### Analyses
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/analyses` | List analyses with filters (category, sentiment, search) |
| GET | `/api/analyses/{id}` | Get single analysis detail |
| DELETE | `/api/analyses/{id}` | Delete analysis |
| DELETE | `/api/analyses` | Delete all analyses |

### Reports & Dashboard
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dashboard/stats` | Dashboard KPIs and aggregations |
| GET | `/api/export/pdf/{id}` | Export single analysis as PDF |
| GET | `/api/export/pdf/all` | Export all analyses as PDF |

### Settings & Discovery
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/settings` | Get all settings |
| PUT | `/api/settings` | Save setting (key-value) |
| GET | `/api/models` | List available FMAPI endpoints |
| GET | `/api/health` | Health check with DB status |
| GET | `/api/debug/env` | Check Databricks environment variables |

## Processing Pipeline

```
Audio file (MP3/WAV/OGG/FLAC/M4A/WebM)
  │
  ▼
Auto-convert to 16kHz mono WAV (miniaudio → pydub+ffmpeg fallback)
  │
  ▼
Transcribe via Gemini 2.5 Flash (native audio input, base64 data URI)
  │
  ▼
Analyze via Claude Sonnet (structured JSON output)
  │  ├── Sentiment + confidence score
  │  ├── Category classification
  │  ├── Key topics extraction
  │  ├── Urgency level (low/normal/high/critical)
  │  ├── Language detection
  │  ├── Speaker count estimation
  │  └── Action items
  │
  ▼
Save to Lakebase (PostgreSQL)
```

## Sample Audio Files

The repository includes sample audio files in Portuguese for testing:

| File | Type |
|------|------|
| `reclamacao_atendimento_ruim.mp3` | Complaint — poor customer service |
| `reclamacao_cobranca_indevida.mp3` | Complaint — incorrect billing |
| `reclamacao_demora_entrega.mp3` | Complaint — delayed delivery |
| `reclamacao_internet_lenta.mp3` | Complaint — slow internet |
| `elogio_atendimento_excelente.mp3` | Praise — excellent service |
| `elogio_produto_qualidade.mp3` | Praise — product quality |
| `elogio_suporte_tecnico.mp3` | Praise — technical support |
| `sugestao_melhorias_app.mp3` | Suggestion — app improvements |

## Project Structure

```
audio-insight-hub/
  start.sh                    # Startup script (ffmpeg download + uvicorn)
  app.yaml                    # Databricks Apps config (env vars, resources)
  requirements.txt            # Python dependencies
  backend/
    main.py                   # FastAPI entry point + all API routes
    database.py               # Lakebase connection (psycopg2, auto-setup)
    ai_service.py             # Gemini transcription + Claude analysis
    pdf_service.py            # PDF report generation (fpdf2)
  frontend/
    index.html                # HTML entry point
    package.json              # React 19, Vite 8, Tailwind CSS
    vite.config.js            # Build config + dev proxy
    tailwind.config.js        # Custom brand colors
    src/
      main.jsx                # React root
      App.jsx                 # SPA shell: sidebar + routing + dark mode
      pages/
        Dashboard.jsx         # KPIs, charts, sentiment distribution
        ProcessPage.jsx       # Upload + batch processing UI
        ProcessingStatus.jsx  # Real-time SSE batch progress
        AnalysesPage.jsx      # Search and filter analyses
        AnalysisDetail.jsx    # Full transcription + metadata view
        SettingsPage.jsx      # Categories + AI model + database management
        VolumePage.jsx        # Databricks Volume file browser
      hooks/
        useApi.jsx            # Centralized API client
        useToast.jsx          # Toast notifications
        useProcessing.jsx     # Processing queue state management
      i18n/
        useTranslation.jsx    # i18n hook
        translations.js       # PT/EN/ES translations (~200 keys)
  sample_audios/              # Portuguese voice samples (.mp3)
  sample_audios_wav/          # Same samples in .wav format
  scripts/
    generate_audio_macos.sh   # macOS TTS sample generator
    generate_sample_audio.py  # Python TTS sample generator
```

## License

Internal use only. Built with Databricks Apps + Lakebase + FMAPI.
