"""
🧠 Zinin Corp — Lessons Learned System

Stores, retrieves, and manages operational insights from agent tasks.
Persisted to disk as JSON. Queryable by agent, category, and recency.
"""

import json
import logging
import os
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────────────────

CATEGORIES = [
    "quality",       # Response quality issues and fixes
    "tool_usage",    # Tool misuse, correct patterns
    "delegation",    # Delegation routing lessons
    "performance",   # Speed, cost, efficiency
    "data",          # Data accuracy, anti-fabrication
    "integration",   # API, webhook, external service issues
    "process",       # Workflow, sprint, planning
    "other",
]


class Lesson(BaseModel):
    """A single lesson learned."""
    id: str = ""
    agent: str = ""           # Which agent learned this
    category: str = "other"   # One of CATEGORIES
    summary: str              # Short 1-line summary
    detail: str = ""          # Longer explanation
    action: str = ""          # What to do differently next time
    task_context: str = ""    # What task triggered this lesson
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    useful_count: int = 0     # How many times this was retrieved and found useful


class LessonsStore(BaseModel):
    """Persistent store for all lessons."""
    lessons: list[Lesson] = Field(default_factory=list)
    next_id: int = 1


# ──────────────────────────────────────────────────────────
# Persistence
# ──────────────────────────────────────────────────────────

MAX_LESSONS = 500


def _store_path() -> str:
    for p in ["/app/data/lessons_learned.json", "data/lessons_learned.json"]:
        parent = os.path.dirname(p)
        if os.path.isdir(parent):
            return p
    os.makedirs("data", exist_ok=True)
    return "data/lessons_learned.json"


def _load_store() -> LessonsStore:
    path = _store_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return LessonsStore.model_validate(data)
        except Exception as e:
            logger.warning(f"Failed to load lessons store: {e}")
    return LessonsStore()


def _save_store(store: LessonsStore):
    path = _store_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(store.model_dump(), f, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"Failed to save lessons store: {e}")


# ──────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────

def add_lesson(
    summary: str,
    agent: str = "",
    category: str = "other",
    detail: str = "",
    action: str = "",
    task_context: str = "",
) -> str:
    """Add a new lesson. Returns the lesson ID."""
    store = _load_store()
    lesson_id = f"L{store.next_id:04d}"
    store.next_id += 1

    if category not in CATEGORIES:
        category = "other"

    lesson = Lesson(
        id=lesson_id,
        agent=agent,
        category=category,
        summary=summary[:200],
        detail=detail[:1000],
        action=action[:500],
        task_context=task_context[:200],
    )
    store.lessons.append(lesson)

    # Cap at MAX_LESSONS, keep newest
    if len(store.lessons) > MAX_LESSONS:
        store.lessons = store.lessons[-MAX_LESSONS:]

    _save_store(store)
    return lesson_id


def get_lessons(
    agent: str = "",
    category: str = "",
    limit: int = 10,
) -> list[Lesson]:
    """Get lessons, optionally filtered by agent and/or category."""
    store = _load_store()
    results = store.lessons

    if agent:
        results = [l for l in results if l.agent == agent]
    if category:
        results = [l for l in results if l.category == category]

    return results[-limit:]


def get_lessons_for_context(agent: str = "", task_text: str = "", limit: int = 5) -> str:
    """Get lessons as formatted text for injection into agent prompts.

    Returns a compact string suitable for prepending to task descriptions.
    If no relevant lessons found, returns empty string.
    """
    store = _load_store()
    if not store.lessons:
        return ""

    # Filter by agent if provided
    candidates = store.lessons
    if agent:
        agent_lessons = [l for l in candidates if l.agent == agent]
        # Also include general lessons (no agent)
        general_lessons = [l for l in candidates if not l.agent]
        candidates = agent_lessons + general_lessons

    if not candidates:
        return ""

    # Take most recent lessons
    selected = candidates[-limit:]

    lines = ["📝 УРОКИ ИЗ ПРОШЛОГО ОПЫТА:"]
    for lesson in selected:
        lines.append(f"• {lesson.summary}")
        if lesson.action:
            lines.append(f"  → {lesson.action}")
    lines.append("")

    return "\n".join(lines)


def get_all_lessons() -> list[Lesson]:
    """Get all lessons (for admin/dashboard)."""
    store = _load_store()
    return store.lessons


def get_lesson_stats() -> dict:
    """Get statistics about lessons."""
    store = _load_store()
    lessons = store.lessons

    by_category = {}
    by_agent = {}
    for l in lessons:
        by_category[l.category] = by_category.get(l.category, 0) + 1
        if l.agent:
            by_agent[l.agent] = by_agent.get(l.agent, 0) + 1

    return {
        "total": len(lessons),
        "by_category": by_category,
        "by_agent": by_agent,
    }


def mark_useful(lesson_id: str) -> bool:
    """Increment useful_count for a lesson. Returns True if found."""
    store = _load_store()
    for lesson in store.lessons:
        if lesson.id == lesson_id:
            lesson.useful_count += 1
            _save_store(store)
            return True
    return False


def delete_lesson(lesson_id: str) -> bool:
    """Delete a lesson by ID. Returns True if found and deleted."""
    store = _load_store()
    before = len(store.lessons)
    store.lessons = [l for l in store.lessons if l.id != lesson_id]
    if len(store.lessons) < before:
        _save_store(store)
        return True
    return False
