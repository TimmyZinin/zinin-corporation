"""Comment digest — fetch and summarize recent LinkedIn comment activity.

Uses AgentBridge to delegate LinkedIn comment checking to CTO Мартин (web search).
"""

import json
import logging
import os
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_DIGEST_PATH = os.path.join(_DATA_DIR, "comment_digest.json")
_lock = threading.Lock()


def _load_digest() -> dict:
    """Load comment digest from disk."""
    with _lock:
        try:
            if os.path.exists(_DIGEST_PATH):
                with open(_DIGEST_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load comment digest: {e}")
    return {"digests": [], "updated_at": ""}


def _save_digest(data: dict) -> bool:
    """Save comment digest to disk."""
    with _lock:
        try:
            os.makedirs(_DATA_DIR, exist_ok=True)
            data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            with open(_DIGEST_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.warning(f"Failed to save comment digest: {e}")
            return False


def get_comment_count(hours: int = 3) -> int:
    """Get approximate comment count from recent digests."""
    data = _load_digest()
    cutoff = time.time() - hours * 3600
    count = 0
    for digest in data.get("digests", []):
        ts = digest.get("timestamp", 0)
        if ts >= cutoff:
            count += digest.get("comment_count", 0)
    return count


def add_digest_entry(summary: str, comment_count: int, source: str = "scheduled") -> dict:
    """Add a new digest entry."""
    data = _load_digest()
    entry = {
        "id": f"cd_{int(time.time())}",
        "summary": summary,
        "comment_count": comment_count,
        "source": source,
        "timestamp": time.time(),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    data["digests"].append(entry)
    # Keep last 50 entries
    if len(data["digests"]) > 50:
        data["digests"] = data["digests"][-50:]
    _save_digest(data)
    return entry


def get_recent_digests(hours: int = 24) -> list[dict]:
    """Get digest entries from the last N hours."""
    data = _load_digest()
    cutoff = time.time() - hours * 3600
    return [d for d in data.get("digests", []) if d.get("timestamp", 0) >= cutoff]


def format_comment_digest(digests: list[dict]) -> str:
    """Format digest entries for Telegram display."""
    if not digests:
        return "💬 Нет новых комментариев за последние часы."

    total = sum(d.get("comment_count", 0) for d in digests)
    lines = [f"💬 Дайджест комментариев ({total} новых):\n"]
    for d in digests[-5:]:  # Show last 5
        lines.append(f"• {d.get('summary', '?')[:200]}")
    return "\n".join(lines)


async def fetch_comment_digest() -> Optional[dict]:
    """Fetch comment digest via CTO agent (web search for LinkedIn activity).

    Returns dict with summary and count, or None on failure.
    """
    try:
        from .telegram.bridge import AgentBridge
        response = await AgentBridge.send_to_agent(
            message=(
                "Проверь последние комментарии к постам Тима Зинина в LinkedIn. "
                "Кратко резюмируй: сколько новых комментариев, на какие посты, "
                "есть ли вопросы требующие ответа. "
                "Формат: количество комментариев | краткая сводка."
            ),
            agent_name="automator",
        )
        # Parse response for count (best effort)
        count = 0
        for word in response.split():
            if word.isdigit():
                count = int(word)
                break

        entry = add_digest_entry(
            summary=response[:500],
            comment_count=max(count, 0),
            source="agent_fetch",
        )
        return entry
    except Exception as e:
        logger.error(f"Comment digest fetch error: {e}", exc_info=True)
        return None
