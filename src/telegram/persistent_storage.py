"""Persistent key-value storage backed by PostgreSQL.

Falls back to local JSON files when DATABASE_URL is not set (local dev).
Data survives Railway container restarts.

SECURITY: Sensitive keys (transactions, screenshots, payments) are
encrypted via vault.py (AES-256, VAULT_PASSWORD env var).

Tables auto-created on first use:
  kv_store(key TEXT PRIMARY KEY, value TEXT, updated_at TIMESTAMP)
"""

import json
import logging
import os
from typing import Optional

from . import vault

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

    # Railway sometimes has uppercase hostnames (Postgres.railway.internal)
    if ".railway.internal" in _db_url.lower() and ".railway.internal" not in _db_url:
        import re
        _db_url = re.sub(
            r"@([A-Za-z0-9.-]+\.railway\.internal)",
            lambda m: "@" + m.group(1).lower(),
            _db_url,
            flags=re.IGNORECASE,
        )

    try:
        import psycopg2
        conn = psycopg2.connect(_db_url)
        conn.autocommit = True
        cur = conn.cursor()
        # Use TEXT for value column (encrypted data is not valid JSON)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS kv_store (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT '{}',
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
    """Save data under a key. Encrypts sensitive keys. Returns True on success."""
    if vault.is_sensitive(key):
        blob = vault.encrypt(data)
    else:
        blob = json.dumps(data, ensure_ascii=False, default=str)

    if _init_db():
        return _db_save(key, blob)
    return _file_save(key, blob)


def load(key: str, default=None):
    """Load data by key. Decrypts sensitive keys. Returns default if not found."""
    if _init_db():
        blob = _db_load_raw(key)
    else:
        blob = _file_load_raw(key)

    if blob is None:
        return default

    if vault.is_sensitive(key):
        result = vault.decrypt(blob)
        return result if result is not None else default

    # Non-sensitive: parse JSON
    if isinstance(blob, str):
        try:
            return json.loads(blob)
        except (json.JSONDecodeError, TypeError):
            return blob
    return blob


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

def _db_save(key: str, blob: str) -> bool:
    try:
        import psycopg2
        conn = psycopg2.connect(_db_url)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO kv_store (key, value, updated_at) VALUES (%s, %s, NOW())
               ON CONFLICT (key) DO UPDATE SET value = %s, updated_at = NOW()""",
            (key, blob, blob),
        )
        cur.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"DB save '{key}' failed: {e}")
        return _file_save(key, blob)  # fallback


def _db_load_raw(key: str) -> Optional[str]:
    """Load raw string from PostgreSQL (may be encrypted)."""
    try:
        import psycopg2
        conn = psycopg2.connect(_db_url)
        cur = conn.cursor()
        cur.execute("SELECT value FROM kv_store WHERE key = %s", (key,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            val = row[0]
            if isinstance(val, (dict, list)):
                return json.dumps(val, ensure_ascii=False, default=str)
            return str(val) if val is not None else None
        return None
    except Exception as e:
        logger.error(f"DB load '{key}' failed: {e}")
        return _file_load_raw(key)  # fallback


# ── File backend (local dev) ──────────────────────────────

def _file_path(key: str) -> str:
    safe_key = key.replace("/", "_").replace("\\", "_")
    for base in ["/app/data", "data"]:
        if os.path.isdir(base):
            return os.path.join(base, f"{safe_key}.json")
    os.makedirs("data", exist_ok=True)
    return f"data/{safe_key}.json"


def _file_save(key: str, blob: str) -> bool:
    try:
        path = _file_path(key)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(blob)
        return True
    except Exception as e:
        logger.error(f"File save '{key}' failed: {e}")
        return False


def _file_load_raw(key: str) -> Optional[str]:
    """Load raw string from file (may be encrypted)."""
    try:
        path = _file_path(key)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"File load '{key}' failed: {e}")
        return None
