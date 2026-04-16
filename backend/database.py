import os
import subprocess
import json
import httpx
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

LAKEBASE_HOST = os.environ.get(
    "DATABRICKS_LAKEBASE_HOST",
    "ep-sparkling-truth-d2q43hj7.database.us-east-1.cloud.databricks.com",
)
LAKEBASE_DB = os.environ.get("DATABRICKS_LAKEBASE_DB", "audio_insight_hub")
LAKEBASE_PORT = os.environ.get("DATABRICKS_LAKEBASE_PORT", "5432")

# Cache for OAuth token
_token_cache = {"token": None, "user": None}


def _get_credentials():
    """Get user and password for Lakebase connection."""
    # 1. Explicit env vars (manual override)
    user = os.environ.get("DATABRICKS_LAKEBASE_USER", "")
    password = os.environ.get("DATABRICKS_LAKEBASE_PASSWORD", "")
    if user and password:
        return user, password

    # 2. Databricks Apps environment (OAuth M2M)
    client_id = os.environ.get("DATABRICKS_CLIENT_ID", "")
    client_secret = os.environ.get("DATABRICKS_CLIENT_SECRET", "")
    host = os.environ.get("DATABRICKS_HOST", "")

    if client_id and client_secret and host:
        # Get OAuth token via client credentials flow
        try:
            if not host.startswith("http"):
                host = f"https://{host}"
            token_url = f"{host.rstrip('/')}/oidc/v1/token"
            resp = httpx.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "scope": "all-apis",
                },
                auth=(client_id, client_secret),
                timeout=15,
            )
            resp.raise_for_status()
            token = resp.json()["access_token"]
            # For Lakebase, user = service principal client_id
            return client_id, token
        except Exception as e:
            print(f"OAuth M2M token error: {e}")

    # 3. DATABRICKS_TOKEN (e.g. PAT or injected token)
    token = os.environ.get("DATABRICKS_TOKEN", "")
    if token:
        user = client_id or "token"
        return user, token

    # 4. Local dev: CLI-based auth
    try:
        profile = os.environ.get("DATABRICKS_PROFILE", "fevm-jsf")
        cli = os.path.expanduser("~/bin/databricks")
        result = subprocess.run(
            [cli, "postgres", "generate-database-credential",
             "projects/audio-insight-hub/branches/production/endpoints/primary",
             "--profile", profile, "--output", "json"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            password = json.loads(result.stdout)["token"]

        result2 = subprocess.run(
            [cli, "current-user", "me", "--profile", profile, "--output", "json"],
            capture_output=True, text=True, timeout=15,
        )
        if result2.returncode == 0:
            user = json.loads(result2.stdout)["userName"]

        if user and password:
            return user, password
    except Exception:
        pass

    return "", ""


def get_connection():
    """Get a connection to the Lakebase PostgreSQL database."""
    user, password = _get_credentials()
    if not user or not password:
        raise Exception("No Lakebase credentials available. Check env vars.")
    return psycopg2.connect(
        host=LAKEBASE_HOST,
        database=LAKEBASE_DB,
        user=user,
        password=password,
        port=LAKEBASE_PORT,
        sslmode="require",
    )


@contextmanager
def get_cursor():
    """Context manager for database cursor."""
    conn = get_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def init_database():
    """Initialize the database schema (tables already created via psql)."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL UNIQUE,
                    color VARCHAR(7) DEFAULT '#6366f1',
                    icon VARCHAR(50) DEFAULT 'tag',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audio_analyses (
                    id SERIAL PRIMARY KEY,
                    file_name VARCHAR(500) NOT NULL,
                    file_path VARCHAR(1000),
                    file_size BIGINT,
                    duration_seconds FLOAT,
                    transcription TEXT,
                    summary TEXT,
                    category_id INTEGER REFERENCES categories(id),
                    sentiment VARCHAR(20),
                    sentiment_score FLOAT,
                    key_topics TEXT[],
                    urgency_level VARCHAR(20) DEFAULT 'normal',
                    language_detected VARCHAR(10),
                    speaker_count INTEGER DEFAULT 1,
                    action_items TEXT[],
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMP
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    key VARCHAR(100) PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cursor.execute("""
                INSERT INTO categories (name, color, icon) VALUES
                    ('Reclamacao', '#ef4444', 'alert-triangle'),
                    ('Elogio', '#22c55e', 'thumbs-up'),
                    ('Duvida', '#3b82f6', 'help-circle'),
                    ('Sugestao', '#f59e0b', 'lightbulb'),
                    ('Solicitacao', '#8b5cf6', 'clipboard'),
                    ('Cancelamento', '#dc2626', 'x-circle'),
                    ('Informacao', '#06b6d4', 'info')
                ON CONFLICT (name) DO NOTHING;
            """)
            conn.commit()
        finally:
            cursor.close()
            conn.close()
    except Exception as e:
        print(f"Database init warning: {e}")
