"""
📋 Zinin Corp — Shared Task Pool with Dependency Engine (v2.3)

CEO Алексей — единственный назначающий. Каждая задача проходит через него.
Agent Tag Router подсказывает оптимального исполнителя по тегам.
Dependency Engine автоматически разблокирует задачи при завершении зависимостей.
"""

import json
import logging
import os
import re
import threading
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Task Status enum
# ──────────────────────────────────────────────────────────

class TaskStatus(str, Enum):
    TODO = "TODO"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    BLOCKED = "BLOCKED"


class TaskPriority(int, Enum):
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


# ──────────────────────────────────────────────────────────
# PoolTask model
# ──────────────────────────────────────────────────────────

def _short_id() -> str:
    return uuid4().hex[:8]


class PoolTask(BaseModel):
    id: str = Field(default_factory=_short_id)
    title: str
    status: TaskStatus = TaskStatus.TODO
    assignee: str = ""           # agent key: "accountant", "automator", "smm", etc.
    assigned_by: str = ""        # "ceo-alexey" or "tim"
    tags: list[str] = Field(default_factory=list)
    priority: int = TaskPriority.MEDIUM
    blocked_by: list[str] = Field(default_factory=list)
    blocks: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    assigned_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[str] = None
    source: str = ""             # "telegram", "brain_dump", "scheduler", "manual"


# ──────────────────────────────────────────────────────────
# Agent Tag Router
# ──────────────────────────────────────────────────────────

AGENT_TAGS: dict[str, list[str]] = {
    "manager": [
        "strategy", "delegation", "coordination", "review",
        "report", "planning", "escalation",
    ],
    "accountant": [
        "finance", "budget", "revenue", "p&l", "portfolio",
        "crypto", "banking", "billing", "tribute", "costs",
        "forex", "transactions",
    ],
    "automator": [
        "architecture", "infrastructure", "mcp", "code",
        "api", "health", "deployment", "testing", "audit",
        "security", "devops", "monitoring",
    ],
    "smm": [
        "content", "linkedin", "threads", "post", "podcast",
        "social", "copywriting", "seo", "brand",
    ],
    "designer": [
        "design", "visual", "image", "infographic", "chart",
        "video", "branding", "ui", "ux",
    ],
    "cpo": [
        "product", "backlog", "sprint", "feature", "roadmap",
        "metrics", "analytics", "kpi",
    ],
}

# Keyword → tag mapping for auto-tagging from title
_TAG_KEYWORDS: dict[str, list[str]] = {
    "finance": ["финанс", "бюджет", "p&l", "баланс", "revenue", "доход", "расход"],
    "revenue": ["revenue", "mrr", "подписк", "выручк", "tribute", "монетизац"],
    "crypto": ["крипто", "bitcoin", "btc", "eth", "портфел", "defi", "токен"],
    "content": ["контент", "пост", "статья", "публикац", "текст", "копирайт"],
    "linkedin": ["linkedin", "линкедин"],
    "threads": ["threads", "тредс"],
    "podcast": ["подкаст", "podcast", "аудио"],
    "design": ["дизайн", "визуал", "картинк", "инфографик", "баннер"],
    "infrastructure": ["инфраструктур", "деплой", "docker", "railway", "сервер"],
    "mcp": ["mcp", "сервер mcp", "обёртк"],
    "api": ["api", "интеграц", "webhook", "эндпоинт"],
    "code": ["код", "рефактор", "баг", "фикс", "тест"],
    "architecture": ["архитектур", "систем"],
    "product": ["продукт", "фич", "бэклог", "roadmap", "спринт"],
    "strategy": ["стратег", "план", "vision"],
    "social": ["smm", "соцсет", "social"],
    "brand": ["бренд", "brand"],
    "seo": ["seo", "оптимизац", "мета"],
    "audit": ["аудит", "ревью", "review"],
    "monitoring": ["мониторинг", "алерт", "health"],
    "hitl": ["утверд", "подтвержд", "approve", "согласов"],
}


def auto_tag(title: str) -> list[str]:
    """Extract tags from task title using keyword matching."""
    title_lower = title.lower()
    tags: list[str] = []
    for tag, keywords in _TAG_KEYWORDS.items():
        for kw in keywords:
            if kw in title_lower:
                tags.append(tag)
                break
    return sorted(set(tags))


def suggest_assignee(tags: list[str]) -> list[tuple[str, float]]:
    """Match task tags against agent competencies.

    Returns list of (agent_key, confidence) sorted by confidence desc.
    Confidence = matched_tags / total_task_tags.
    """
    if not tags:
        return []
    results: list[tuple[str, float]] = []
    tag_set = set(tags)
    for agent, agent_tags in AGENT_TAGS.items():
        overlap = tag_set & set(agent_tags)
        if overlap:
            confidence = len(overlap) / len(tag_set)
            results.append((agent, round(confidence, 2)))
    results.sort(key=lambda x: x[1], reverse=True)
    return results


# ──────────────────────────────────────────────────────────
# Persistence (JSON, thread-safe)
# ──────────────────────────────────────────────────────────

_lock = threading.Lock()


def _pool_path() -> str:
    """Get path for task pool JSON file."""
    for p in ["/app/data/task_pool.json", "data/task_pool.json"]:
        parent = os.path.dirname(p)
        if os.path.isdir(parent):
            return p
    return "data/task_pool.json"


def _load_pool() -> list[dict]:
    path = _pool_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as e:
            logger.warning(f"Failed to load task pool: {e}")
    return []


def _save_pool(tasks: list[dict]) -> bool:
    path = _pool_path()
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2, default=str)
        return True
    except Exception as e:
        logger.warning(f"Failed to save task pool: {e}")
        return False


def _find_task(tasks: list[dict], task_id: str) -> Optional[dict]:
    for t in tasks:
        if t.get("id") == task_id:
            return t
    return None


# ──────────────────────────────────────────────────────────
# CRUD Operations
# ──────────────────────────────────────────────────────────

def create_task(
    title: str,
    *,
    priority: int = TaskPriority.MEDIUM,
    tags: Optional[list[str]] = None,
    blocked_by: Optional[list[str]] = None,
    source: str = "manual",
    assigned_by: str = "",
    assignee: str = "",
) -> PoolTask:
    """Create a new task in the pool.

    Auto-tags from title if tags not provided.
    Sets up reverse `blocks` on dependencies.
    """
    if tags is None:
        tags = auto_tag(title)

    task = PoolTask(
        title=title,
        priority=priority,
        tags=tags,
        blocked_by=blocked_by or [],
        source=source,
        assigned_by=assigned_by,
        assignee=assignee,
    )

    # If assignee provided at creation, set status to ASSIGNED
    if assignee:
        task.status = TaskStatus.ASSIGNED
        task.assigned_at = datetime.now().isoformat()

    # If blocked, mark as BLOCKED
    if task.blocked_by:
        task.status = TaskStatus.BLOCKED

    with _lock:
        pool = _load_pool()

        # Set up reverse `blocks` on dependencies
        for dep_id in task.blocked_by:
            dep = _find_task(pool, dep_id)
            if dep and task.id not in dep.get("blocks", []):
                dep.setdefault("blocks", []).append(task.id)

        pool.append(task.model_dump())
        _save_pool(pool)

    logger.info(f"Created task {task.id}: {title} [{task.status}]")
    return task


def assign_task(task_id: str, assignee: str, assigned_by: str = "ceo-alexey") -> Optional[PoolTask]:
    """Assign a task to an agent. TODO → ASSIGNED (or BLOCKED if dependencies unmet)."""
    with _lock:
        pool = _load_pool()
        raw = _find_task(pool, task_id)
        if not raw:
            logger.warning(f"Task {task_id} not found")
            return None

        if raw["status"] not in (TaskStatus.TODO, TaskStatus.BLOCKED):
            logger.warning(f"Task {task_id} cannot be assigned (status={raw['status']})")
            return None

        raw["assignee"] = assignee
        raw["assigned_by"] = assigned_by
        raw["assigned_at"] = datetime.now().isoformat()

        # Check if all dependencies are DONE
        unmet = _get_unmet_deps(pool, raw)
        if unmet:
            raw["status"] = TaskStatus.BLOCKED
        else:
            raw["status"] = TaskStatus.ASSIGNED

        _save_pool(pool)

    task = PoolTask(**raw)
    logger.info(f"Assigned {task_id} → {assignee} [{task.status}]")
    return task


def start_task(task_id: str) -> Optional[PoolTask]:
    """Move task to IN_PROGRESS. ASSIGNED → IN_PROGRESS."""
    with _lock:
        pool = _load_pool()
        raw = _find_task(pool, task_id)
        if not raw:
            return None

        if raw["status"] != TaskStatus.ASSIGNED:
            logger.warning(f"Task {task_id} cannot start (status={raw['status']})")
            return None

        raw["status"] = TaskStatus.IN_PROGRESS
        _save_pool(pool)

    task = PoolTask(**raw)
    logger.info(f"Started {task_id} [{task.status}]")
    return task


def complete_task(task_id: str, result: str = "") -> Optional[PoolTask]:
    """Complete a task. IN_PROGRESS → DONE. Triggers Dependency Engine."""
    with _lock:
        pool = _load_pool()
        raw = _find_task(pool, task_id)
        if not raw:
            return None

        if raw["status"] not in (TaskStatus.IN_PROGRESS, TaskStatus.ASSIGNED):
            logger.warning(f"Task {task_id} cannot complete (status={raw['status']})")
            return None

        raw["status"] = TaskStatus.DONE
        raw["completed_at"] = datetime.now().isoformat()
        raw["result"] = result

        # Dependency Engine: unblock dependent tasks
        unblocked = _run_dependency_engine(pool, task_id)

        _save_pool(pool)

    task = PoolTask(**raw)
    if unblocked:
        logger.info(f"Completed {task_id}, unblocked: {unblocked}")
    else:
        logger.info(f"Completed {task_id}")
    return task


def block_task(task_id: str) -> Optional[PoolTask]:
    """Manually block a task."""
    with _lock:
        pool = _load_pool()
        raw = _find_task(pool, task_id)
        if not raw:
            return None

        raw["status"] = TaskStatus.BLOCKED
        _save_pool(pool)

    return PoolTask(**raw)


# ──────────────────────────────────────────────────────────
# Dependency Engine
# ──────────────────────────────────────────────────────────

def _get_unmet_deps(pool: list[dict], task: dict) -> list[str]:
    """Return IDs of blocked_by tasks that are NOT DONE."""
    unmet = []
    for dep_id in task.get("blocked_by", []):
        dep = _find_task(pool, dep_id)
        if dep and dep.get("status") != TaskStatus.DONE:
            unmet.append(dep_id)
        elif not dep:
            # Dependency doesn't exist — treat as met (removed/external)
            pass
    return unmet


def _run_dependency_engine(pool: list[dict], completed_id: str) -> list[str]:
    """When a task completes, unblock dependents.

    For each task that has `completed_id` in `blocked_by`:
    - Remove it from blocked_by
    - If blocked_by is now empty and task has assignee → ASSIGNED
    - If blocked_by is now empty and no assignee → TODO

    Returns list of unblocked task IDs.
    """
    unblocked: list[str] = []

    for t in pool:
        bb = t.get("blocked_by", [])
        if completed_id in bb:
            bb.remove(completed_id)
            t["blocked_by"] = bb

            # Check if all remaining deps are DONE
            remaining_unmet = _get_unmet_deps(pool, t)
            if not remaining_unmet and t.get("status") == TaskStatus.BLOCKED:
                if t.get("assignee"):
                    t["status"] = TaskStatus.ASSIGNED
                else:
                    t["status"] = TaskStatus.TODO
                unblocked.append(t["id"])

    return unblocked


# ──────────────────────────────────────────────────────────
# Query helpers
# ──────────────────────────────────────────────────────────

def get_all_tasks() -> list[PoolTask]:
    """Get all tasks from the pool."""
    with _lock:
        pool = _load_pool()
    return [PoolTask(**t) for t in pool]


def get_task(task_id: str) -> Optional[PoolTask]:
    """Get a single task by ID."""
    with _lock:
        pool = _load_pool()
        raw = _find_task(pool, task_id)
    if raw:
        return PoolTask(**raw)
    return None


def get_tasks_by_status(*statuses: TaskStatus) -> list[PoolTask]:
    """Get tasks filtered by one or more statuses."""
    status_set = set(s.value for s in statuses)
    with _lock:
        pool = _load_pool()
    return [PoolTask(**t) for t in pool if t.get("status") in status_set]


def get_tasks_by_assignee(assignee: str) -> list[PoolTask]:
    """Get all tasks assigned to a specific agent."""
    with _lock:
        pool = _load_pool()
    return [PoolTask(**t) for t in pool if t.get("assignee") == assignee]


def get_ready_tasks() -> list[PoolTask]:
    """Get TODO tasks with no unmet dependencies (ready for assignment)."""
    with _lock:
        pool = _load_pool()
        ready = []
        for t in pool:
            if t.get("status") == TaskStatus.TODO:
                if not _get_unmet_deps(pool, t):
                    ready.append(PoolTask(**t))
    return sorted(ready, key=lambda t: t.priority)


def get_blocked_tasks() -> list[PoolTask]:
    """Get all blocked tasks."""
    return get_tasks_by_status(TaskStatus.BLOCKED)


def get_pool_summary() -> dict[str, int]:
    """Get count of tasks by status."""
    with _lock:
        pool = _load_pool()
    summary: dict[str, int] = {}
    for t in pool:
        s = t.get("status", "TODO")
        summary[s] = summary.get(s, 0) + 1
    summary["total"] = len(pool)
    return summary


# ──────────────────────────────────────────────────────────
# Utility
# ──────────────────────────────────────────────────────────

def delete_task(task_id: str) -> bool:
    """Remove a task from the pool entirely."""
    with _lock:
        pool = _load_pool()
        original_len = len(pool)
        pool = [t for t in pool if t.get("id") != task_id]
        if len(pool) == original_len:
            return False

        # Clean up references
        for t in pool:
            if task_id in t.get("blocked_by", []):
                t["blocked_by"].remove(task_id)
            if task_id in t.get("blocks", []):
                t["blocks"].remove(task_id)

        _save_pool(pool)
    logger.info(f"Deleted task {task_id}")
    return True


def format_task_summary(task: PoolTask) -> str:
    """Format a task for Telegram display."""
    status_emoji = {
        TaskStatus.TODO: "📝",
        TaskStatus.ASSIGNED: "👤",
        TaskStatus.IN_PROGRESS: "🔄",
        TaskStatus.DONE: "✅",
        TaskStatus.BLOCKED: "🚫",
    }
    emoji = status_emoji.get(task.status, "❓")
    priority_label = {1: "🔴", 2: "🟠", 3: "🟡", 4: "🟢"}.get(task.priority, "⚪")

    parts = [f"{emoji} {priority_label} <b>{task.title}</b>"]
    parts.append(f"   ID: <code>{task.id}</code> | {task.status.value}")
    if task.assignee:
        parts.append(f"   👤 {task.assignee}")
    if task.blocked_by:
        parts.append(f"   🔗 blocked by: {', '.join(task.blocked_by)}")
    if task.tags:
        parts.append(f"   🏷 {', '.join(task.tags)}")
    return "\n".join(parts)


def format_pool_summary() -> str:
    """Format full pool summary for Telegram."""
    summary = get_pool_summary()
    if summary.get("total", 0) == 0:
        return "📋 Task Pool пуст"

    lines = ["📋 <b>Task Pool</b>\n"]
    for status in TaskStatus:
        count = summary.get(status.value, 0)
        if count:
            emoji = {"TODO": "📝", "ASSIGNED": "👤", "IN_PROGRESS": "🔄",
                     "DONE": "✅", "BLOCKED": "🚫"}.get(status.value, "❓")
            lines.append(f"{emoji} {status.value}: {count}")
    lines.append(f"\n📊 Всего: {summary.get('total', 0)}")
    return "\n".join(lines)
