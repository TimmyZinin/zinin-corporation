"""Persistent key-value storage backed by PostgreSQL.

Falls back to local JSON files when DATABASE_URL is not set (local dev).
Data survives Railway container restarts.

Tables auto-created on first use:
  kv_store(key TEXT PRIMARY KEY, value JSONB, updated_at TIMESTAMP)
"""

import json
import logging
import os
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

_db_url = None
_use_db = False
_engine = None


def _init_db():
    """Initialize database connection (lazy, once)."""
    global _db_url, _use_db, _engine
    if _engine is not None:
        return _use_db

    _db_url = os.getenv("DATABASE_URL", "")
    if not _db_url:
        _use_db = False
        return False

    try:
        import psycopg2
        conn = psycopg2.connect(_db_url)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS kv_store (
                key TEXT PRIMARY KEY,
                value JSONB NOT NULL DEFAULT '{}',
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.close()
        conn.close()
        _engine = True
        _use_db = True
        logger.info("Persistent storage: PostgreSQL initialized")
        return True
    except Exception as e:
        logger.warning(f"Persistent storage: PostgreSQL unavailable ({e}), using local files")
        _engine = False
        _use_db = False
        return False


def save(key: str, data) -> bool:
    """Save data under a key. Returns True on success."""
    if _init_db():
        return _db_save(key, data)
    return _file_save(key, data)


def load(key: str, default=None):
    """Load data by key. Returns default if not found."""
    if _init_db():
        return _db_load(key, default)
    return _file_load(key, default)


def append_to_list(key: str, item: dict, max_items: int = 200) -> bool:
    """Append item to a list stored under key (with max size limit)."""
    data = load(key, [])
    if not isinstance(data, list):
        data = []
    data.append(item)
    if len(data) > max_items:
        data = data[-max_items:]
    return save(key, data)


# ── PostgreSQL backend ─────────────────────────────────────

def _db_save(key: str, data) -> bool:
    try:
        import psycopg2
        conn = psycopg2.connect(_db_url)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO kv_store (key, value, updated_at) VALUES (%s, %s, NOW())
               ON CONFLICT (key) DO UPDATE SET value = %s, updated_at = NOW()""",
            (key, json.dumps(data, ensure_ascii=False, default=str),
             json.dumps(data, ensure_ascii=False, default=str)),
        )
        cur.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"DB save '{key}' failed: {e}")
        return _file_save(key, data)  # fallback


def _db_load(key: str, default=None):
    try:
        import psycopg2
        conn = psycopg2.connect(_db_url)
        cur = conn.cursor()
        cur.execute("SELECT value FROM kv_store WHERE key = %s", (key,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return row[0] if isinstance(row[0], (dict, list)) else json.loads(row[0])
        return default
    except Exception as e:
        logger.error(f"DB load '{key}' failed: {e}")
        return _file_load(key, default)  # fallback


# ── File backend (local dev) ──────────────────────────────

def _file_path(key: str) -> str:
    safe_key = key.replace("/", "_").replace("\\", "_")
    for base in ["/app/data", "data"]:
        if os.path.isdir(base):
            return os.path.join(base, f"{safe_key}.json")
    os.makedirs("data", exist_ok=True)
    return f"data/{safe_key}.json"


def _file_save(key: str, data) -> bool:
    try:
        path = _file_path(key)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        return True
    except Exception as e:
        logger.error(f"File save '{key}' failed: {e}")
        return False


def _file_load(key: str, default=None):
    try:
        path = _file_path(key)
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"File load '{key}' failed: {e}")
        return default
