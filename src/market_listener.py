"""Market Listener — daily career market trend scanner.

Scans web for career/HR trends and generates topic suggestions
for Yuki content pipeline. Uses DuckDuckGo search + LLM synthesis.
"""

import json
import logging
import os
import threading
from datetime import date, datetime

logger = logging.getLogger(__name__)

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_INSIGHTS_PATH = os.path.join(_DATA_DIR, "market_insights.json")
_lock = threading.Lock()

SEARCH_QUERIES = [
    "рынок труда тренды 2026 site:hh.ru OR site:linkedin.com",
    "карьера поиск работы тренды новости",
    "AI HR найм автоматизация новости",
    "remote work hybrid 2026 trends",
]

_SYNTHESIS_PROMPT = """Ты аналитик карьерного рынка. На основе поисковых результатов
выдели 5 актуальных тем для LinkedIn-постов про карьеру и поиск работы.

Поисковые результаты:
{snippets}

Верни ТОЛЬКО JSON-массив из 5 строк (тем), без комментариев.
Каждая тема — 1 предложение, конкретная, актуальная, провокационная.
Пример: ["Тема 1", "Тема 2", ...]"""


def _insights_path() -> str:
    return _INSIGHTS_PATH


def _load_insights() -> dict:
    path = _insights_path()
    with _lock:
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
        except Exception as e:
            logger.warning(f"Failed to load market insights: {e}")
    return {"scans": [], "updated_at": ""}


def _save_insights(data: dict) -> bool:
    path = _insights_path()
    with _lock:
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.warning(f"Failed to save market insights: {e}")
            return False


def get_today_topics() -> list[str]:
    """Return cached topics for today. Empty list if no scan yet."""
    today_str = date.today().isoformat()
    data = _load_insights()
    for scan in reversed(data.get("scans", [])):
        if scan.get("date") == today_str:
            return scan.get("topics", [])
    return []


async def run_daily_scan() -> list[str]:
    """Run web search + LLM synthesis to generate topic suggestions.

    Returns list of 3-5 topic strings.
    """
    import asyncio

    # Step 1: Search
    snippets = []
    try:
        from .tools.tech_tools import WebSearchTool
        search_tool = WebSearchTool()
        for query in SEARCH_QUERIES:
            try:
                result = await asyncio.to_thread(search_tool._run, query=query)
                if result:
                    snippets.append(result[:500])
            except Exception as e:
                logger.warning(f"Search failed for '{query[:30]}': {e}")
    except Exception as e:
        logger.warning(f"WebSearchTool import failed: {e}")

    if not snippets:
        logger.warning("No search results for market listener")
        return []

    # Step 2: LLM synthesis
    topics = []
    try:
        combined = "\n---\n".join(snippets)
        prompt = _SYNTHESIS_PROMPT.format(snippets=combined[:3000])

        from .tools.tech_tools import _call_llm_tech
        response = await asyncio.to_thread(_call_llm_tech, prompt)

        # Parse JSON array from response
        if response:
            # Try to extract JSON array
            start = response.find("[")
            end = response.rfind("]")
            if start >= 0 and end > start:
                topics = json.loads(response[start:end + 1])
                topics = [str(t) for t in topics if isinstance(t, str)][:5]
    except Exception as e:
        logger.error(f"LLM synthesis failed: {e}", exc_info=True)

    if not topics:
        return []

    # Step 3: Save
    data = _load_insights()
    data["scans"].append({
        "date": date.today().isoformat(),
        "topics": topics,
        "snippets_count": len(snippets),
        "created_at": datetime.now().isoformat(),
    })
    # Keep last 30 days
    if len(data["scans"]) > 30:
        data["scans"] = data["scans"][-30:]
    data["updated_at"] = datetime.now().isoformat()
    _save_insights(data)

    logger.info(f"Market listener: {len(topics)} topics generated")
    return topics


def format_topics_for_menu(topics: list[str]) -> str:
    """Format topics for Telegram message."""
    if not topics:
        return "💡 Нет свежих тем. Запусти сканирование позже."

    lines = ["💡 Горячие темы сегодня:"]
    for i, t in enumerate(topics, 1):
        lines.append(f"  {i}. {t[:80]}")
    return "\n".join(lines)
