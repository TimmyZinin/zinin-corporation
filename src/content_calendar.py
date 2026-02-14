"""
📅 Zinin Corp — Content Calendar

Thread-safe JSON persistence for weekly content plans.
Used by Proactive Planner to auto-generate SMM actions in morning touchpoints.
"""

import json
import logging
import os
import threading
from datetime import datetime, date, timedelta
from uuid import uuid4

logger = logging.getLogger(__name__)

_lock = threading.Lock()


def _short_id() -> str:
    return uuid4().hex[:8]


_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_CALENDAR_PATH = os.path.join(_DATA_DIR, "content_calendar.json")


def _calendar_path() -> str:
    """Get path for content calendar JSON file. Uses _CALENDAR_PATH module variable (patchable in tests)."""
    return _CALENDAR_PATH


def _load_calendar() -> dict:
    path = _calendar_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as e:
            logger.warning(f"Failed to load content calendar: {e}")
    return {"entries": [], "updated_at": ""}


def _save_calendar(data: dict) -> bool:
    path = _calendar_path()
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        return True
    except Exception as e:
        logger.warning(f"Failed to save content calendar: {e}")
        return False


def add_entry(
    *,
    entry_date: str,
    topic: str,
    author: str = "tim",
    platform: str = "linkedin",
    cta: str = "",
    brand: str = "personal",
    status: str = "planned",
) -> dict:
    """Add a content calendar entry. Returns the new entry."""
    entry = {
        "id": _short_id(),
        "date": entry_date,
        "topic": topic,
        "author": author,
        "platform": platform,
        "cta": cta,
        "brand": brand,
        "status": status,
        "post_id": "",
        "created_at": datetime.now().isoformat(),
    }
    with _lock:
        data = _load_calendar()
        data["entries"].append(entry)
        data["updated_at"] = datetime.now().isoformat()
        _save_calendar(data)
    return entry


def get_today() -> list[dict]:
    """Get all entries for today."""
    today_str = date.today().isoformat()
    with _lock:
        data = _load_calendar()
    return [e for e in data.get("entries", []) if e.get("date") == today_str]


def get_date(target_date: str) -> list[dict]:
    """Get all entries for a specific date (YYYY-MM-DD)."""
    with _lock:
        data = _load_calendar()
    return [e for e in data.get("entries", []) if e.get("date") == target_date]


def get_week() -> list[dict]:
    """Get entries for the next 7 days."""
    today = date.today()
    dates = [(today + timedelta(days=i)).isoformat() for i in range(7)]
    with _lock:
        data = _load_calendar()
    return [e for e in data.get("entries", []) if e.get("date") in dates]


def get_overdue() -> list[dict]:
    """Get entries before today that are not done or skipped."""
    today_str = date.today().isoformat()
    with _lock:
        data = _load_calendar()
    return [
        e for e in data.get("entries", [])
        if e.get("date", "9999") < today_str
        and e.get("status") not in ("done", "skipped")
    ]


def get_all_entries() -> list[dict]:
    """Get all calendar entries."""
    with _lock:
        data = _load_calendar()
    return data.get("entries", [])


def get_entry_by_id(entry_id: str) -> dict | None:
    """Get a single calendar entry by its ID."""
    with _lock:
        data = _load_calendar()
    for e in data.get("entries", []):
        if e.get("id") == entry_id:
            return e
    return None


def update_entry(entry_id: str, **kwargs) -> bool:
    """Update a calendar entry's fields (topic, author, platform, cta, date, brand, status)."""
    allowed = {"topic", "author", "platform", "cta", "date", "brand", "status"}
    with _lock:
        data = _load_calendar()
        for entry in data.get("entries", []):
            if entry.get("id") == entry_id:
                for key, val in kwargs.items():
                    if key in allowed:
                        entry[key] = val
                data["updated_at"] = datetime.now().isoformat()
                return _save_calendar(data)
    return False


def mark_done(entry_id: str, post_id: str = "") -> bool:
    """Mark a calendar entry as done, optionally linking to the published post."""
    with _lock:
        data = _load_calendar()
        for entry in data.get("entries", []):
            if entry.get("id") == entry_id:
                entry["status"] = "done"
                if post_id:
                    entry["post_id"] = post_id
                data["updated_at"] = datetime.now().isoformat()
                return _save_calendar(data)
    return False


def mark_skipped(entry_id: str) -> bool:
    """Mark a calendar entry as skipped."""
    with _lock:
        data = _load_calendar()
        for entry in data.get("entries", []):
            if entry.get("id") == entry_id:
                entry["status"] = "skipped"
                data["updated_at"] = datetime.now().isoformat()
                return _save_calendar(data)
    return False


def format_today_plan() -> str:
    """Format today's content plan for Telegram."""
    entries = get_today()
    overdue = get_overdue()

    if not entries and not overdue:
        return "📅 Контент-план на сегодня: пусто"

    lines = [f"📅 Контент-план на {date.today().strftime('%d.%m')}"]

    if overdue:
        lines.append(f"\n⚠️ Просрочено ({len(overdue)}):")
        for e in overdue:
            lines.append(f"  🔴 [{e['date']}] {e['topic']} ({e['author']}, {e['platform']})")

    if entries:
        lines.append(f"\n📝 Сегодня ({len(entries)}):")
        for e in entries:
            status_icon = "✅" if e["status"] == "done" else "⏳" if e["status"] == "planned" else "⏭"
            lines.append(f"  {status_icon} {e['topic']} ({e['author']}, {e['platform']})")
            if e.get("cta"):
                lines.append(f"     CTA: {e['cta']}")

    return "\n".join(lines)


def format_week_plan() -> str:
    """Format weekly content plan for Telegram."""
    entries = get_week()
    if not entries:
        return "📅 Контент-план на неделю: пусто"

    lines = ["📅 Контент-план на неделю"]

    # Group by date
    by_date: dict[str, list[dict]] = {}
    for e in entries:
        d = e.get("date", "unknown")
        by_date.setdefault(d, []).append(e)

    for d in sorted(by_date.keys()):
        try:
            dt = datetime.strptime(d, "%Y-%m-%d")
            day_label = dt.strftime("%a %d.%m")
        except Exception:
            day_label = d
        lines.append(f"\n📆 {day_label}:")
        for e in by_date[d]:
            status_icon = "✅" if e["status"] == "done" else "⏳"
            lines.append(f"  {status_icon} {e['topic']} ({e['author']}, {e['platform']})")

    return "\n".join(lines)


def seed_sborka_launch() -> list[dict]:
    """Seed 5 Sborka launch posts for Feb 14-18, 2026. Returns created entries."""
    plan = [
        {
            "entry_date": "2026-02-14",
            "topic": "Как мы строим AI-команду для бизнеса",
            "author": "kristina",
            "platform": "linkedin",
            "cta": "Подписаться на канал",
            "brand": "sborka",
        },
        {
            "entry_date": "2026-02-15",
            "topic": "5 задач, которые AI-агенты уже делают за нас",
            "author": "kristina",
            "platform": "linkedin",
            "cta": "Бесплатный trial",
            "brand": "sborka",
        },
        {
            "entry_date": "2026-02-16",
            "topic": "Почему SMM-агент лучше фрилансера (Build in Public)",
            "author": "tim",
            "platform": "linkedin",
            "cta": "Ссылка на Сборку",
            "brand": "sborka",
        },
        {
            "entry_date": "2026-02-17",
            "topic": "Результаты первой недели: цифры",
            "author": "kristina",
            "platform": "linkedin",
            "cta": "Trial + Tribute",
            "brand": "sborka",
        },
        {
            "entry_date": "2026-02-18",
            "topic": "LAUNCH DAY — Сборка открыта: AI для вашего SMM",
            "author": "both",
            "platform": "linkedin+threads",
            "cta": "Tribute подписка",
            "brand": "sborka",
        },
    ]
    created = []
    for item in plan:
        entry = add_entry(**item)
        created.append(entry)
    return created


def seed_sborka_launch_v2() -> list[dict]:
    """Seed 5 Sborka webinar launch posts for Feb 13-17, 2026.

    Focus: drive registrations for the webinar on Feb 17 at 15:00 MSK.
    """
    plan = [
        {
            "entry_date": "2026-02-13",
            "topic": "Проблема: почему поиск работы не работает как система",
            "author": "kristina",
            "platform": "linkedin",
            "cta": "Записывайся на вебинар 17 фев → @sborka_career_bot",
            "brand": "sborka",
        },
        {
            "entry_date": "2026-02-14",
            "topic": "Как мы строим клуб карьерной дисциплины с AI",
            "author": "tim",
            "platform": "linkedin",
            "cta": "Первая неделя бесплатно → @sborka_career_bot",
            "brand": "sborka",
        },
        {
            "entry_date": "2026-02-15",
            "topic": "5 вещей, которые ломают поиск работы — и как СБОРКА их чинит",
            "author": "kristina",
            "platform": "linkedin+threads",
            "cta": "Регистрация на вебинар → @sborka_career_bot",
            "brand": "sborka",
        },
        {
            "entry_date": "2026-02-16",
            "topic": "Завтра вебинар: покажем всю систему СБОРКИ live",
            "author": "tim",
            "platform": "linkedin+threads",
            "cta": "Последний день записаться → @sborka_career_bot",
            "brand": "sborka",
        },
        {
            "entry_date": "2026-02-17",
            "topic": "СБОРКА LIVE: вебинар сегодня в 15:00 — AI для карьерной дисциплины",
            "author": "both",
            "platform": "linkedin+threads+telegram",
            "cta": "Присоединяйся сейчас → @sborka_career_bot",
            "brand": "sborka",
        },
    ]
    created = []
    for item in plan:
        entry = add_entry(**item)
        created.append(entry)
    return created


def seed_sborka_launch_v3() -> list[dict]:
    """Seed 7 Sborka launch posts for Feb 14-17, 2026.

    Narrative: Зачем → Как → Urgency → Launch Day.
    Webinar Tue Feb 17 at 15:00 MSK. No social proof (first launch).
    2 posts/day (Tim + Kristina), launch day — both.
    """
    plan = [
        {
            "entry_date": "2026-02-14",
            "topic": "Зачем мы запускаем СБОРКУ — проблема поиска работы",
            "author": "kristina",
            "platform": "linkedin",
            "cta": "Записывайся на вебинар 17 фев → @sborka_career_bot",
            "brand": "sborka",
        },
        {
            "entry_date": "2026-02-14",
            "topic": "Я 3 года нанимал людей. Вот что я понял о поиске работы",
            "author": "tim",
            "platform": "linkedin",
            "cta": "Бесплатный вебинар 17 фев → @sborka_career_bot",
            "brand": "sborka",
        },
        {
            "entry_date": "2026-02-15",
            "topic": "Что такое СБОРКА — система вместо хаоса в поиске работы",
            "author": "tim",
            "platform": "linkedin+threads",
            "cta": "Вебинар 17 фев, бесплатно → @sborka_career_bot",
            "brand": "sborka",
        },
        {
            "entry_date": "2026-02-15",
            "topic": "5 принципов, которые мы заложили в СБОРКУ",
            "author": "kristina",
            "platform": "linkedin",
            "cta": "Регистрация → @sborka_career_bot",
            "brand": "sborka",
        },
        {
            "entry_date": "2026-02-16",
            "topic": "Завтра покажем всю систему live — последний день записи",
            "author": "tim",
            "platform": "linkedin+threads+telegram",
            "cta": "Последний шанс → @sborka_career_bot",
            "brand": "sborka",
        },
        {
            "entry_date": "2026-02-16",
            "topic": "Что будет на вебинаре и почему стоит прийти",
            "author": "kristina",
            "platform": "linkedin+threads",
            "cta": "Последний день → @sborka_career_bot",
            "brand": "sborka",
        },
        {
            "entry_date": "2026-02-17",
            "topic": "СБОРКА LIVE: вебинар сегодня 15:00 МСК",
            "author": "both",
            "platform": "linkedin+threads+telegram",
            "cta": "Присоединяйся сейчас → @sborka_career_bot",
            "brand": "sborka",
        },
    ]
    created = []
    for item in plan:
        entry = add_entry(**item)
        created.append(entry)
    return created
