"""Storage for financial data extracted from screenshots.

Uses persistent_storage (PostgreSQL on Railway, local files in dev).
Data survives container restarts.
"""

import logging
from datetime import datetime

from . import persistent_storage as store

logger = logging.getLogger(__name__)

STORAGE_KEY = "screenshot_data"
MAX_ENTRIES = 200


def load_all_screenshots() -> list[dict]:
    return store.load(STORAGE_KEY, [])


def save_screenshot_data(extracted: dict) -> bool:
    """Append extracted screenshot data to storage."""
    entry = {
        "extracted_at": datetime.utcnow().isoformat(),
        "source": extracted.get("source", "unknown"),
        "screen_type": extracted.get("screen_type", "unknown"),
        "accounts": extracted.get("accounts", []),
        "transactions": extracted.get("transactions", []),
        "summary": extracted.get("summary", ""),
    }
    return store.append_to_list(STORAGE_KEY, entry, max_items=MAX_ENTRIES)


def get_latest_balances() -> dict[str, dict]:
    """Get latest balance per source (for Маттиас reports)."""
    latest: dict[str, dict] = {}
    for entry in load_all_screenshots():
        source = entry.get("source", "unknown")
        if entry.get("accounts"):
            latest[source] = {
                "accounts": entry["accounts"],
                "extracted_at": entry.get("extracted_at"),
            }
    return latest
