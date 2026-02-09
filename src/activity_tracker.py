"""
📡 Zinin Corp — Activity Tracker
Tracks agent activities, tasks, and inter-agent communication
"""

import json
import os
import logging
import threading
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Activity log file
# ──────────────────────────────────────────────────────────
def _log_path() -> str:
    for p in ["/app/data/activity_log.json", "data/activity_log.json"]:
        parent = os.path.dirname(p)
        if os.path.isdir(parent):
            return p
    return "data/activity_log.json"


def _load_log() -> dict:
    path = _log_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"events": [], "agent_status": {}}


def _save_log(data: dict):
    path = _log_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to save activity log: {e}")


_lock = threading.Lock()


# ──────────────────────────────────────────────────────────
# Agent names mapping
# ──────────────────────────────────────────────────────────
AGENT_NAMES = {
    "manager": "Алексей",
    "accountant": "Маттиас",
    "smm": "Юки",
    "automator": "Мартин",
}

AGENT_EMOJI = {
    "manager": "👑",
    "accountant": "🏦",
    "smm": "📱",
    "automator": "⚙️",
}


# ──────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────
def log_task_start(agent_key: str, task_description: str):
    """Log that an agent started working on a task."""
    with _lock:
        data = _load_log()
        now = datetime.now().isoformat()

        # Update agent status
        data["agent_status"][agent_key] = {
            "status": "working",
            "task": task_description[:120],
            "started_at": now,
            "communicating_with": None,
        }

        # Add event
        data["events"].append({
            "type": "task_start",
            "agent": agent_key,
            "task": task_description[:120],
            "timestamp": now,
        })

        _trim_events(data)
        _save_log(data)


def log_task_end(agent_key: str, task_description: str, success: bool = True):
    """Log that an agent finished a task."""
    with _lock:
        data = _load_log()
        now = datetime.now().isoformat()

        # Calculate duration
        status = data.get("agent_status", {}).get(agent_key, {})
        started = status.get("started_at")
        duration_sec = 0
        if started:
            try:
                start_dt = datetime.fromisoformat(started)
                duration_sec = int((datetime.now() - start_dt).total_seconds())
            except Exception:
                pass

        # Update agent status
        data["agent_status"][agent_key] = {
            "status": "idle",
            "task": None,
            "started_at": None,
            "communicating_with": None,
            "last_task": task_description[:120],
            "last_task_time": now,
            "last_task_success": success,
            "last_task_duration_sec": duration_sec,
        }

        # Add event
        data["events"].append({
            "type": "task_end",
            "agent": agent_key,
            "task": task_description[:120],
            "success": success,
            "duration_sec": duration_sec,
            "timestamp": now,
        })

        _trim_events(data)
        _save_log(data)


def log_communication(from_agent: str, to_agent: str, description: str = ""):
    """Log inter-agent communication (context passing)."""
    with _lock:
        data = _load_log()
        now = datetime.now().isoformat()

        # Update both agents' communication status
        for agent_key in [from_agent, to_agent]:
            if agent_key in data.get("agent_status", {}):
                other = to_agent if agent_key == from_agent else from_agent
                data["agent_status"][agent_key]["communicating_with"] = other

        # Add event
        data["events"].append({
            "type": "communication",
            "from_agent": from_agent,
            "to_agent": to_agent,
            "description": description[:120],
            "timestamp": now,
        })

        _trim_events(data)
        _save_log(data)


def log_delegation(from_agent: str, to_agent: str, task_desc: str):
    """Log that one agent delegated a task to another."""
    with _lock:
        data = _load_log()
        now = datetime.now().isoformat()

        data["events"].append({
            "type": "delegation",
            "from_agent": from_agent,
            "to_agent": to_agent,
            "description": task_desc[:120],
            "timestamp": now,
        })

        _trim_events(data)
        _save_log(data)


def log_quality_score(agent_key: str, task_description: str, score: float,
                      details: Optional[dict] = None):
    """Log quality score from LLM judge for an agent response."""
    with _lock:
        data = _load_log()
        now = datetime.now().isoformat()

        data["events"].append({
            "type": "quality_score",
            "agent": agent_key,
            "task": task_description[:120],
            "score": round(score, 2),
            "details": details or {},
            "timestamp": now,
        })

        _trim_events(data)
        _save_log(data)


def log_communication_end(agent_key: str):
    """Clear communication indicator for an agent."""
    with _lock:
        data = _load_log()
        if agent_key in data.get("agent_status", {}):
            data["agent_status"][agent_key]["communicating_with"] = None
            _save_log(data)


def get_agent_status(agent_key: str) -> dict:
    """Get current status for one agent, including queued_tasks count."""
    data = _load_log()
    status = data.get("agent_status", {}).get(agent_key, {
        "status": "idle",
        "task": None,
        "started_at": None,
        "communicating_with": None,
    })

    # Count queued (delegated) tasks for this agent
    cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
    queued = sum(
        1 for e in data.get("events", [])
        if e.get("type") == "delegation"
        and e.get("to_agent") == agent_key
        and e.get("timestamp", "") >= cutoff
    )
    status["queued_tasks"] = queued

    return status


def get_all_statuses() -> dict:
    """Get current status for all agents, including queued_tasks."""
    data = _load_log()
    cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
    result = {}
    for key in AGENT_NAMES:
        status = data.get("agent_status", {}).get(key, {
            "status": "idle",
            "task": None,
            "started_at": None,
            "communicating_with": None,
        })
        # Count queued (delegated) tasks
        queued = sum(
            1 for e in data.get("events", [])
            if e.get("type") == "delegation"
            and e.get("to_agent") == key
            and e.get("timestamp", "") >= cutoff
        )
        status["queued_tasks"] = queued
        result[key] = status
    return result


def get_recent_events(hours: int = 24, limit: int = 50) -> list:
    """Get events from the last N hours."""
    data = _load_log()
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    events = [e for e in data.get("events", []) if e.get("timestamp", "") >= cutoff]
    return events[-limit:]


def get_agent_task_count(agent_key: str, hours: int = 24) -> int:
    """Count tasks for an agent in the last N hours.

    Includes both completed tasks (task_end) and delegated tasks (delegation).
    """
    events = get_recent_events(hours=hours, limit=500)
    return sum(
        1 for e in events
        if (e.get("type") == "task_end" and e.get("agent") == agent_key)
        or (e.get("type") == "delegation" and e.get("to_agent") == agent_key)
    )


def get_task_progress(agent_key: str) -> Optional[float]:
    """Estimate progress for a running task (0.0 - 1.0).

    Uses average duration of past tasks as estimate.
    Returns None if agent is idle.
    """
    status = get_agent_status(agent_key)
    if status.get("status") != "working" or not status.get("started_at"):
        return None

    try:
        start = datetime.fromisoformat(status["started_at"])
        elapsed = (datetime.now() - start).total_seconds()
    except Exception:
        return None

    # Estimate based on typical task duration (60-180 seconds)
    # Look at recent completed tasks for this agent
    data = _load_log()
    durations = [
        e.get("duration_sec", 0)
        for e in data.get("events", [])
        if e.get("type") == "task_end"
        and e.get("agent") == agent_key
        and e.get("duration_sec", 0) > 0
    ]

    if durations:
        avg_duration = sum(durations) / len(durations)
    else:
        avg_duration = 90  # default estimate: 90 seconds

    progress = min(elapsed / max(avg_duration, 1), 0.95)  # cap at 95%
    return round(progress, 2)


# ──────────────────────────────────────────────────────────
# Internal
# ──────────────────────────────────────────────────────────
def _trim_events(data: dict, max_events: int = 500):
    """Keep only the last N events."""
    if len(data.get("events", [])) > max_events:
        data["events"] = data["events"][-max_events:]
