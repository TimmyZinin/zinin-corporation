"""
📋 Zinin Corp — Task Extractor

Extracts action items from agent responses and chat messages.
Stores dynamic tasks in a local JSON file (alongside activity_log).
"""

import re
import json
import os
import logging
import threading
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Agent name patterns for assignee detection
# ──────────────────────────────────────────────────────────
AGENT_PATTERNS = {
    "manager": ["алексей", "алексею", "алексея"],
    "accountant": ["маттиас", "маттиасу", "маттиаса"],
    "automator": ["мартин", "мартину", "мартина"],
    "smm": ["юки"],
}

# Action verb patterns (Russian imperative forms)
ACTION_VERBS = [
    r"сделай\w*",
    r"подготовь\w*",
    r"проверь\w*",
    r"создай\w*",
    r"обнови\w*",
    r"опубликуй\w*",
    r"проанализируй\w*",
    r"напиши\w*",
    r"отправь\w*",
    r"настрой\w*",
]

# Deadline patterns
DEADLINE_PATTERNS = [
    (r"до\s+(пятницы|понедельника|вторника|среды|четверга|субботы|воскресенья)", "до {0}"),
    (r"к\s+(понедельнику|вторнику|среде|четвергу|пятнице|субботе|воскресенью)", "к {0}"),
    (r"до\s+конца\s+дня", "до конца дня"),
    (r"на\s+этой\s+неделе", "на этой неделе"),
    (r"сегодня", "сегодня"),
    (r"завтра", "завтра"),
]

_lock = threading.Lock()


# ──────────────────────────────────────────────────────────
# Task storage
# ──────────────────────────────────────────────────────────

def _tasks_path() -> str:
    """Get path for task queue JSON file."""
    for p in ["/app/data/task_queue.json", "data/task_queue.json"]:
        parent = os.path.dirname(p)
        if os.path.isdir(parent):
            return p
    return "data/task_queue.json"


def load_task_queue() -> List[Dict]:
    """Load the task queue from disk."""
    path = _tasks_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as e:
            logger.warning(f"Failed to load task queue: {e}")
    return []


def save_task_queue(tasks: List[Dict]) -> bool:
    """Save the task queue to disk. Returns True on success."""
    path = _tasks_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2, default=str)
        return True
    except Exception as e:
        logger.warning(f"Failed to save task queue: {e}")
        return False


def add_tasks(new_tasks: List[Dict]) -> int:
    """Add extracted tasks to the queue. Returns number of tasks added."""
    if not new_tasks:
        return 0
    with _lock:
        queue = load_task_queue()
        queue.extend(new_tasks)
        # Keep last 100 tasks
        if len(queue) > 100:
            queue = queue[-100:]
        save_task_queue(queue)
    return len(new_tasks)


def complete_task(task_index: int) -> bool:
    """Mark a task as completed by index."""
    with _lock:
        queue = load_task_queue()
        if 0 <= task_index < len(queue):
            queue[task_index]["status"] = "completed"
            queue[task_index]["completed_at"] = datetime.now().isoformat()
            save_task_queue(queue)
            return True
    return False


def get_pending_tasks() -> List[Dict]:
    """Get only pending (not completed) tasks."""
    return [t for t in load_task_queue() if t.get("status") != "completed"]


# ──────────────────────────────────────────────────────────
# Extraction logic
# ──────────────────────────────────────────────────────────

def extract_tasks_from_message(content: str, source_agent: str = "") -> List[Dict]:
    """Extract action items from a message.

    Returns list of dicts with keys:
        action, assignee, deadline, source_agent, created_at, status
    """
    tasks = []
    lines = content.split("\n")

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped or len(line_stripped) < 10:
            continue

        assignee = _detect_assignee(line_stripped)
        has_action = _has_action_verb(line_stripped)

        if assignee and has_action:
            deadline = _detect_deadline(line_stripped)
            # Clean up the action text (remove list numbering)
            action = re.sub(r"^\d+[\.\)\-]\s*", "", line_stripped)
            tasks.append({
                "action": action,
                "assignee": assignee,
                "deadline": deadline,
                "source_agent": source_agent,
                "created_at": datetime.now().isoformat(),
                "status": "pending",
            })

    return tasks


def extract_and_store(content: str, source_agent: str = "") -> List[Dict]:
    """Extract tasks from a message and add them to the queue.

    Returns the list of extracted tasks.
    """
    tasks = extract_tasks_from_message(content, source_agent)
    if tasks:
        add_tasks(tasks)
        logger.info(f"Extracted {len(tasks)} task(s) from {source_agent}")
    return tasks


def _detect_assignee(text: str) -> str:
    """Detect which agent is being addressed in the text."""
    text_lower = text.lower()
    for agent_key, patterns in AGENT_PATTERNS.items():
        for pattern in patterns:
            if pattern in text_lower:
                return agent_key
    return ""


def _has_action_verb(text: str) -> bool:
    """Check if text contains a Russian action verb."""
    text_lower = text.lower()
    for pattern in ACTION_VERBS:
        if re.search(pattern, text_lower):
            return True
    return False


def _detect_deadline(text: str) -> str:
    """Detect deadline expressions in text."""
    text_lower = text.lower()
    for pattern, fmt in DEADLINE_PATTERNS:
        match = re.search(pattern, text_lower)
        if match:
            if match.groups():
                return fmt.format(match.group(1))
            return fmt
    return ""
