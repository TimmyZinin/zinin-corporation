"""
📋 Zinin Corp — Shared Task Pool with Dependency Engine (v2.3)

CEO Алексей — единственный назначающий. Каждая задача проходит через него.
Agent Tag Router подсказывает оптимального исполнителя по тегам.
Dependency Engine автоматически разблокирует задачи при завершении зависимостей.
"""

import glob as glob_mod
import json
import logging
import os
import re
import shutil
import threading
from datetime import datetime, timedelta
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
    updated_at: Optional[str] = None
    assigned_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[str] = None
    source: str = ""             # "telegram", "brain_dump", "scheduler", "manual"


# Escalation threshold — if best suggest_assignee confidence < this, escalate
ESCALATION_THRESHOLD = 0.3


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
    now_iso = datetime.now().isoformat()
    task.updated_at = now_iso
    if assignee:
        task.status = TaskStatus.ASSIGNED
        task.assigned_at = now_iso

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

        now_iso = datetime.now().isoformat()
        raw["assignee"] = assignee
        raw["assigned_by"] = assigned_by
        raw["assigned_at"] = now_iso
        raw["updated_at"] = now_iso

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
        raw["updated_at"] = datetime.now().isoformat()
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

        now_iso = datetime.now().isoformat()
        raw["status"] = TaskStatus.DONE
        raw["completed_at"] = now_iso
        raw["updated_at"] = now_iso
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
        raw["updated_at"] = datetime.now().isoformat()
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


# ──────────────────────────────────────────────────────────
# Archive — move DONE tasks to daily JSON files
# ──────────────────────────────────────────────────────────

def _archive_dir() -> str:
    """Get path for archive directory."""
    for base in ["/app/data/archive", "data/archive"]:
        parent = os.path.dirname(base)
        if os.path.isdir(parent):
            return base
    return "data/archive"


def archive_done_tasks(keep_recent_days: int = 1) -> int:
    """Move DONE tasks older than keep_recent_days to daily archive files.

    Returns number of archived tasks.
    """
    cutoff = datetime.now() - timedelta(days=keep_recent_days)
    archived_count = 0

    with _lock:
        pool = _load_pool()
        to_keep = []
        to_archive: dict[str, list[dict]] = {}  # date_str → tasks

        for t in pool:
            if t.get("status") == TaskStatus.DONE and t.get("completed_at"):
                try:
                    completed = datetime.fromisoformat(t["completed_at"])
                    if completed < cutoff:
                        date_str = completed.strftime("%Y-%m-%d")
                        to_archive.setdefault(date_str, []).append(t)
                        archived_count += 1
                        continue
                except (ValueError, TypeError):
                    pass
            to_keep.append(t)

        if not to_archive:
            return 0

        # Write archive files
        arc_dir = _archive_dir()
        os.makedirs(arc_dir, exist_ok=True)
        for date_str, tasks in to_archive.items():
            arc_path = os.path.join(arc_dir, f"{date_str}.json")
            existing = []
            if os.path.exists(arc_path):
                try:
                    with open(arc_path, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                except Exception:
                    pass
            existing.extend(tasks)
            with open(arc_path, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2, default=str)

        # Save cleaned pool
        _save_pool(to_keep)

    logger.info(f"Archived {archived_count} DONE tasks to {len(to_archive)} file(s)")
    return archived_count


def get_archived_tasks(date: str) -> list[PoolTask]:
    """Load archived tasks for a specific date (YYYY-MM-DD)."""
    arc_path = os.path.join(_archive_dir(), f"{date}.json")
    if not os.path.exists(arc_path):
        return []
    try:
        with open(arc_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [PoolTask(**t) for t in data]
    except Exception as e:
        logger.warning(f"Failed to load archive {date}: {e}")
        return []


def get_archive_stats() -> dict:
    """Get archive statistics: file count, total tasks, date range."""
    arc_dir = _archive_dir()
    if not os.path.isdir(arc_dir):
        return {"files": 0, "total_tasks": 0, "dates": []}

    files = sorted(glob_mod.glob(os.path.join(arc_dir, "*.json")))
    total = 0
    dates = []
    for fp in files:
        base = os.path.basename(fp).replace(".json", "")
        dates.append(base)
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
            total += len(data)
        except Exception:
            pass

    return {"files": len(files), "total_tasks": total, "dates": dates}


# ──────────────────────────────────────────────────────────
# Stale task detection (Orphan Patrol)
# ──────────────────────────────────────────────────────────

def get_stale_tasks(stale_days: int = 3) -> list[PoolTask]:
    """Get tasks in ASSIGNED/IN_PROGRESS not updated in stale_days days."""
    cutoff = datetime.now() - timedelta(days=stale_days)
    active_statuses = {TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS}

    with _lock:
        pool = _load_pool()

    stale = []
    for t in pool:
        if t.get("status") not in active_statuses:
            continue
        # Use updated_at, fall back to assigned_at, then created_at
        ts_str = t.get("updated_at") or t.get("assigned_at") or t.get("created_at", "")
        if not ts_str:
            continue
        try:
            ts = datetime.fromisoformat(ts_str)
            if ts < cutoff:
                stale.append(PoolTask(**t))
        except (ValueError, TypeError):
            continue

    return sorted(stale, key=lambda t: t.priority)


def format_stale_report(tasks: list[PoolTask]) -> str:
    """Format stale tasks for CTO Orphan Patrol alert."""
    if not tasks:
        return "🔍 Orphan Task Patrol — все задачи в движении, orphan'ов нет."

    lines = [f"🔍 <b>Orphan Task Patrol — Мартин</b>\n"]
    lines.append(f"Найдено {len(tasks)} задач без движения:\n")

    for t in tasks[:10]:
        ts_str = t.updated_at or t.assigned_at or t.created_at
        try:
            ts = datetime.fromisoformat(ts_str)
            days = (datetime.now() - ts).days
        except (ValueError, TypeError):
            days = "?"
        lines.append(
            f"  • <code>{t.id}</code> «{t.title[:50]}»\n"
            f"    👤 {t.assignee or '—'} | {t.status.value} | {days}д без движения"
        )

    if len(tasks) > 10:
        lines.append(f"\n  ... и ещё {len(tasks) - 10}")

    return "\n".join(lines)
