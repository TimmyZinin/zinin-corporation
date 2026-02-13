"""Competitor analysis — daily scan of competitor LinkedIn activity via CTO web search.

Stores insights in JSON for trend tracking and weekly summaries.
"""

import json
import logging
import os
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_INSIGHTS_PATH = os.path.join(_DATA_DIR, "competitor_insights.json")
_lock = threading.Lock()

# Default competitors — configurable via data file
DEFAULT_COMPETITORS = [
    "Кристина Жукова СБОРКА",
    "Botanica School",
    "Карьерный консультант LinkedIn",
]


def _load_insights() -> dict:
    """Load competitor insights from disk."""
    with _lock:
        try:
            if os.path.exists(_INSIGHTS_PATH):
                with open(_INSIGHTS_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load competitor insights: {e}")
    return {"competitors": DEFAULT_COMPETITORS, "insights": [], "updated_at": ""}


def _save_insights(data: dict) -> bool:
    """Save competitor insights to disk."""
    with _lock:
        try:
            os.makedirs(_DATA_DIR, exist_ok=True)
            data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            with open(_INSIGHTS_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.warning(f"Failed to save competitor insights: {e}")
            return False


def get_competitors() -> list[str]:
    """Get list of tracked competitors."""
    data = _load_insights()
    return data.get("competitors", DEFAULT_COMPETITORS)


def add_insight(competitor: str, summary: str, source: str = "daily_scan") -> dict:
    """Add a new competitor insight."""
    data = _load_insights()
    entry = {
        "id": f"ci_{int(time.time())}",
        "competitor": competitor,
        "summary": summary,
        "source": source,
        "timestamp": time.time(),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    data["insights"].append(entry)
    # Keep last 200 entries
    if len(data["insights"]) > 200:
        data["insights"] = data["insights"][-200:]
    _save_insights(data)
    return entry


def get_recent_insights(days: int = 7) -> list[dict]:
    """Get insights from the last N days."""
    data = _load_insights()
    cutoff = time.time() - days * 86400
    return [i for i in data.get("insights", []) if i.get("timestamp", 0) >= cutoff]


def format_insights_summary(insights: list[dict]) -> str:
    """Format insights for Telegram display."""
    if not insights:
        return "🔍 Нет данных о конкурентах за последнюю неделю."

    lines = [f"🔍 Анализ конкурентов ({len(insights)} наблюдений):\n"]
    # Group by competitor
    by_comp: dict[str, list] = {}
    for ins in insights:
        comp = ins.get("competitor", "?")
        by_comp.setdefault(comp, []).append(ins)

    for comp, items in by_comp.items():
        lines.append(f"\n📊 {comp} ({len(items)} записей):")
        for item in items[-3:]:  # Last 3 per competitor
            lines.append(f"  • {item.get('summary', '?')[:150]}")

    return "\n".join(lines)


async def run_daily_scan() -> list[dict]:
    """Run daily competitor scan via CTO agent (web search).

    Returns list of new insight entries.
    """
    results = []
    competitors = get_competitors()

    for competitor in competitors:
        try:
            from .telegram.bridge import AgentBridge
            response = await AgentBridge.send_to_agent(
                message=(
                    f"Найди последние публикации и активность: {competitor} в LinkedIn. "
                    f"Кратко: о чём пишут, какие темы, сколько реакций. "
                    f"Только факты, без комментариев. Максимум 3 предложения."
                ),
                agent_name="automator",
            )
            entry = add_insight(
                competitor=competitor,
                summary=response[:500],
                source="daily_scan",
            )
            results.append(entry)
        except Exception as e:
            logger.error(f"Competitor scan error for {competitor}: {e}")

    logger.info(f"Daily competitor scan: {len(results)} insights from {len(competitors)} competitors")
    return results
