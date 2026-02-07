"""Storage for financial data extracted from screenshots."""

import json
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

MAX_ENTRIES = 200


def _storage_path() -> str:
    for p in ["/app/data/screenshot_data.json", "data/screenshot_data.json"]:
        if os.path.isdir(os.path.dirname(p) or "."):
            return p
    return "data/screenshot_data.json"


def load_all_screenshots() -> list[dict]:
    path = _storage_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            pass
    return []


def save_screenshot_data(extracted: dict) -> bool:
    """Append extracted screenshot data to storage."""
    data = load_all_screenshots()

    entry = {
        "extracted_at": datetime.utcnow().isoformat(),
        "source": extracted.get("source", "unknown"),
        "screen_type": extracted.get("screen_type", "unknown"),
        "accounts": extracted.get("accounts", []),
        "transactions": extracted.get("transactions", []),
        "summary": extracted.get("summary", ""),
    }
    data.append(entry)

    if len(data) > MAX_ENTRIES:
        data = data[-MAX_ENTRIES:]

    try:
        path = _storage_path()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        return True
    except Exception as e:
        logger.error(f"Failed to save screenshot data: {e}")
        return False


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
