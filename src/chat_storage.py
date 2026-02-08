"""
💾 Zinin Corp — Persistent Chat Storage

Stores chat history in PostgreSQL (if DATABASE_URL is set),
with automatic fallback to local JSON file.
"""

import json
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# PostgreSQL storage
# ──────────────────────────────────────────────────────────

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS chat_history (
    id SERIAL PRIMARY KEY,
    messages JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at TIMESTAMP DEFAULT NOW()
);
"""

_UPSERT = """
INSERT INTO chat_history (id, messages, updated_at)
VALUES (1, %s, NOW())
ON CONFLICT (id) DO UPDATE SET messages = EXCLUDED.messages, updated_at = NOW();
"""

_SELECT = """
SELECT messages FROM chat_history WHERE id = 1;
"""


def _get_db_url() -> Optional[str]:
    """Get DATABASE_URL from environment."""
    return os.getenv("DATABASE_URL")


def _get_connection():
    """Create a PostgreSQL connection."""
    import psycopg2
    url = _get_db_url()
    if not url:
        return None
    # Normalize Railway hostname case (Postgres.railway.internal → lowercase)
    if ".railway.internal" in url.lower() and ".railway.internal" not in url:
        import re
        url = re.sub(
            r"@([A-Za-z0-9.-]+\.railway\.internal)",
            lambda m: "@" + m.group(1).lower(),
            url, flags=re.IGNORECASE,
        )
    return psycopg2.connect(url)


def _ensure_table(conn):
    """Create the chat_history table if it doesn't exist."""
    with conn.cursor() as cur:
        cur.execute(_CREATE_TABLE)
    conn.commit()


def save_to_postgres(messages: list) -> bool:
    """Save messages to PostgreSQL. Returns True on success."""
    try:
        conn = _get_connection()
        if conn is None:
            return False
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(_UPSERT, (json.dumps(messages, ensure_ascii=False, default=str),))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.warning(f"PostgreSQL save failed: {e}")
        return False


def load_from_postgres() -> Optional[list]:
    """Load messages from PostgreSQL. Returns None if unavailable."""
    try:
        conn = _get_connection()
        if conn is None:
            return None
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(_SELECT)
            row = cur.fetchone()
        conn.close()
        if row and row[0]:
            data = row[0]
            if isinstance(data, str):
                data = json.loads(data)
            if isinstance(data, list) and len(data) > 0:
                return data
        return []
    except Exception as e:
        logger.warning(f"PostgreSQL load failed: {e}")
        return None


# ──────────────────────────────────────────────────────────
# Local JSON fallback
# ──────────────────────────────────────────────────────────

def _chat_path() -> str:
    """Get path for local JSON chat history file."""
    for p in ["/app/data/chat_history.json", "data/chat_history.json"]:
        parent = os.path.dirname(p)
        if os.path.isdir(parent):
            return p
    return "data/chat_history.json"


def save_to_json(messages: list) -> bool:
    """Save messages to local JSON file. Returns True on success."""
    path = _chat_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, indent=2, default=str)
        return True
    except Exception as e:
        logger.warning(f"JSON save failed: {e}")
        return False


def load_from_json() -> list:
    """Load messages from local JSON file."""
    path = _chat_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return data
        except Exception:
            pass
    return []


# ──────────────────────────────────────────────────────────
# Public API: PostgreSQL first, JSON fallback
# ──────────────────────────────────────────────────────────

def save_chat_history(messages: list):
    """Save chat history. Tries PostgreSQL first, falls back to local JSON."""
    if _get_db_url():
        if save_to_postgres(messages):
            # Also save to JSON as local cache
            save_to_json(messages)
            return
        logger.warning("PostgreSQL save failed, falling back to JSON")
    save_to_json(messages)


def load_chat_history() -> list:
    """Load chat history. Tries PostgreSQL first, falls back to local JSON."""
    if _get_db_url():
        data = load_from_postgres()
        if data is not None:
            return data
        logger.warning("PostgreSQL load failed, falling back to JSON")
    return load_from_json()


def is_persistent() -> bool:
    """Check if persistent storage (PostgreSQL) is available."""
    return _get_db_url() is not None
