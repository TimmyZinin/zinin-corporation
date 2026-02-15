"""
🔗 Zinin Corp — GitHub Issues Sync (v1.0)

One-way sync: task_pool → GitHub Issues via `gh` CLI.
Subscribes to EventBus events and mirrors task lifecycle to GitHub Issues.

Task pool remains the source of truth. GitHub Issues provide:
- External visibility (browser, mobile, email notifications)
- Audit trail (issue comments)
- Integration potential (GitHub Actions, Projects)
"""

import json
import logging
import os
import subprocess
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────

REPO = os.getenv("GITHUB_SYNC_REPO", "TimmyZinin/zinin-corporation")

AGENT_LABEL_MAP = {
    "manager": "agent:ceo",
    "accountant": "agent:cfo",
    "automator": "agent:cto",
    "smm": "agent:smm",
    "designer": "agent:designer",
    "cpo": "agent:cpo",
}

STATUS_LABEL_MAP = {
    "TODO": "status:todo",
    "ASSIGNED": "status:assigned",
    "IN_PROGRESS": "status:in-progress",
    "BLOCKED": "status:blocked",
    "DONE": "status:done",
}

PRIORITY_LABEL_MAP = {
    1: "priority:critical",
    2: "priority:high",
    3: "priority:medium",
    4: "priority:low",
}

SOURCE_LABEL_MAP = {
    "telegram": "source:telegram",
    "scheduler": "source:scheduler",
    "brain_dump": "source:brain-dump",
    "manual": "source:manual",
}

# Label colors for creation
_LABEL_COLORS = {
    "agent:": "7057ff",
    "status:": "0e8a16",
    "priority:": "d93f0b",
    "source:": "006b75",
}

# ──────────────────────────────────────────────────────────
# Issue map: task_pool ID → GH issue number
# ──────────────────────────────────────────────────────────

_issue_map: dict[str, int] = {}
_map_lock = threading.Lock()
_last_sync_time: float = 0.0


def _sync_file_path() -> str:
    for p in ["/app/data/github_sync.json", "data/github_sync.json"]:
        parent = os.path.dirname(p)
        if os.path.isdir(parent):
            return p
    return "data/github_sync.json"


def _load_sync_map() -> dict[str, int]:
    path = _sync_file_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return {str(k): int(v) for k, v in data.items()}
        except Exception as e:
            logger.warning(f"Failed to load github_sync map: {e}")
    return {}


def _save_sync_map():
    path = _sync_file_path()
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(_issue_map, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save github_sync map: {e}")


# ──────────────────────────────────────────────────────────
# gh CLI wrapper
# ──────────────────────────────────────────────────────────

def _gh_run(args: list[str], timeout: int = 30) -> tuple[bool, str]:
    """Run gh CLI command. Returns (success, stdout)."""
    try:
        result = subprocess.run(
            ["gh", *args],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            logger.debug(f"gh {' '.join(args[:3])}... failed: {result.stderr[:200]}")
            return False, result.stderr.strip()
        return True, result.stdout.strip()
    except FileNotFoundError:
        logger.warning("gh CLI not found — GitHub sync disabled")
        return False, "gh not found"
    except subprocess.TimeoutExpired:
        logger.warning(f"gh CLI timeout ({timeout}s): {args[:3]}")
        return False, "timeout"
    except Exception as e:
        logger.warning(f"gh CLI error: {e}")
        return False, str(e)


def _gh_available() -> bool:
    """Check if gh CLI is available and authenticated."""
    ok, _ = _gh_run(["auth", "status"], timeout=10)
    return ok


# ──────────────────────────────────────────────────────────
# Issue operations
# ──────────────────────────────────────────────────────────

def _build_labels(assignee: str = "", tags: list = None,
                  status: str = "TODO", source: str = "") -> list[str]:
    """Build label list from task metadata."""
    labels = []
    if status and status in STATUS_LABEL_MAP:
        labels.append(STATUS_LABEL_MAP[status])
    if assignee and assignee in AGENT_LABEL_MAP:
        labels.append(AGENT_LABEL_MAP[assignee])
    if source and source in SOURCE_LABEL_MAP:
        labels.append(SOURCE_LABEL_MAP[source])
    return labels


def _create_issue(task_id: str, title: str, assignee: str = "",
                  tags: list = None, status: str = "TODO",
                  source: str = "") -> Optional[int]:
    """Create a GitHub Issue for a task. Returns issue number or None."""
    labels = _build_labels(assignee, tags, status, source)

    args = [
        "issue", "create",
        "--repo", REPO,
        "--title", f"[{task_id}] {title}",
        "--body", f"Task Pool ID: `{task_id}`\nSource: {source}\nTags: {', '.join(tags or [])}",
    ]
    if labels:
        args.extend(["--label", ",".join(labels)])

    ok, output = _gh_run(args)
    if not ok:
        logger.warning(f"Failed to create GH issue for task {task_id}: {output}")
        return None

    # Extract issue number from URL (output is like https://github.com/.../issues/42)
    try:
        issue_num = int(output.strip().rstrip("/").split("/")[-1])
        with _map_lock:
            _issue_map[task_id] = issue_num
            _save_sync_map()
        logger.info(f"GitHub issue #{issue_num} created for task {task_id}")
        return issue_num
    except (ValueError, IndexError):
        logger.warning(f"Could not parse issue number from: {output}")
        return None


def _update_issue_labels(task_id: str, status: str = "",
                         assignee: str = ""):
    """Update labels on an existing GitHub Issue."""
    with _map_lock:
        issue_num = _issue_map.get(task_id)
    if not issue_num:
        return

    # Remove old status labels, add new one
    labels_to_add = []
    labels_to_remove = []

    if status:
        # Remove all status: labels first
        for s_label in STATUS_LABEL_MAP.values():
            labels_to_remove.append(s_label)
        if status in STATUS_LABEL_MAP:
            labels_to_add.append(STATUS_LABEL_MAP[status])

    if assignee and assignee in AGENT_LABEL_MAP:
        labels_to_add.append(AGENT_LABEL_MAP[assignee])

    # Remove old labels
    for label in labels_to_remove:
        _gh_run([
            "issue", "edit", str(issue_num),
            "--repo", REPO,
            "--remove-label", label,
        ])

    # Add new labels
    if labels_to_add:
        _gh_run([
            "issue", "edit", str(issue_num),
            "--repo", REPO,
            "--add-label", ",".join(labels_to_add),
        ])


def _close_issue(task_id: str, result: str = ""):
    """Close a GitHub Issue when task completes."""
    with _map_lock:
        issue_num = _issue_map.get(task_id)
    if not issue_num:
        return

    # Add completion comment
    if result:
        comment = f"**Task completed.**\n\nResult:\n```\n{result[:500]}\n```"
        _gh_run([
            "issue", "comment", str(issue_num),
            "--repo", REPO,
            "--body", comment,
        ])

    # Close the issue
    _gh_run([
        "issue", "close", str(issue_num),
        "--repo", REPO,
    ])
    logger.info(f"GitHub issue #{issue_num} closed for task {task_id}")


def _add_issue_comment(task_id: str, comment: str):
    """Add a comment to a GitHub Issue. Used by checkpoint system."""
    with _map_lock:
        issue_num = _issue_map.get(task_id)
    if not issue_num:
        return

    _gh_run([
        "issue", "comment", str(issue_num),
        "--repo", REPO,
        "--body", comment,
    ])


# ──────────────────────────────────────────────────────────
# EventBus callbacks
# ──────────────────────────────────────────────────────────

def _on_task_created(event):
    """Handle task.created → create GitHub Issue."""
    global _last_sync_time
    p = event.payload
    _create_issue(
        task_id=p.get("task_id", ""),
        title=p.get("title", "Untitled"),
        assignee=p.get("assignee", ""),
        tags=p.get("tags", []),
        status=p.get("status", "TODO"),
        source=p.get("source", ""),
    )
    _last_sync_time = time.time()


def _on_task_assigned(event):
    """Handle task.assigned → update labels."""
    global _last_sync_time
    p = event.payload
    _update_issue_labels(
        task_id=p.get("task_id", ""),
        status=p.get("status", "ASSIGNED"),
        assignee=p.get("assignee", ""),
    )
    _last_sync_time = time.time()


def _on_task_started(event):
    """Handle task.started → update status label."""
    global _last_sync_time
    p = event.payload
    _update_issue_labels(
        task_id=p.get("task_id", ""),
        status="IN_PROGRESS",
    )
    _last_sync_time = time.time()


def _on_task_completed(event):
    """Handle task.completed → close issue."""
    global _last_sync_time
    p = event.payload
    _close_issue(
        task_id=p.get("task_id", ""),
        result=p.get("result", ""),
    )
    _last_sync_time = time.time()


# ──────────────────────────────────────────────────────────
# Labels setup
# ──────────────────────────────────────────────────────────

def _ensure_labels():
    """Create GitHub labels if they don't exist. Runs once at startup."""
    all_labels = []
    for label_map in [AGENT_LABEL_MAP, STATUS_LABEL_MAP, SOURCE_LABEL_MAP]:
        all_labels.extend(label_map.values())
    all_labels.extend(PRIORITY_LABEL_MAP.values())

    for label in all_labels:
        color = "ededed"
        for prefix, c in _LABEL_COLORS.items():
            if label.startswith(prefix):
                color = c
                break
        _gh_run([
            "label", "create", label,
            "--repo", REPO,
            "--color", color,
            "--force",
        ])


# ──────────────────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────────────────

_registered = False


def register_github_sync():
    """Register GitHub sync listeners on the EventBus."""
    global _registered, _issue_map

    if not _gh_available():
        logger.warning("gh CLI not available — GitHub sync disabled")
        return

    from .event_bus import (
        get_event_bus, TASK_CREATED, TASK_ASSIGNED,
        TASK_STARTED, TASK_COMPLETED,
    )

    # Load existing map
    with _map_lock:
        _issue_map.update(_load_sync_map())

    # Setup labels (background, non-blocking)
    threading.Thread(target=_ensure_labels, daemon=True, name="gh-labels-setup").start()

    bus = get_event_bus()
    bus.on(TASK_CREATED, _on_task_created)
    bus.on(TASK_ASSIGNED, _on_task_assigned)
    bus.on(TASK_STARTED, _on_task_started)
    bus.on(TASK_COMPLETED, _on_task_completed)
    _registered = True
    logger.info("GitHub Issues sync registered")


def unregister_github_sync():
    """Unregister GitHub sync listeners. For testing."""
    global _registered
    from .event_bus import (
        get_event_bus, TASK_CREATED, TASK_ASSIGNED,
        TASK_STARTED, TASK_COMPLETED,
    )
    bus = get_event_bus()
    bus.off(TASK_CREATED, _on_task_created)
    bus.off(TASK_ASSIGNED, _on_task_assigned)
    bus.off(TASK_STARTED, _on_task_started)
    bus.off(TASK_COMPLETED, _on_task_completed)
    _registered = False


def get_sync_status() -> dict:
    """Return current GitHub sync status."""
    with _map_lock:
        synced = len(_issue_map)
    return {
        "registered": _registered,
        "synced_tasks": synced,
        "last_sync_time": _last_sync_time,
        "repo": REPO,
    }
