"""
🧠 Zinin Corp — Brain Dump Processor

Parses long text messages into structured tasks in the Task Pool.
Auto-tags each task and suggests assignees via Agent Tag Router.
Integrated into CEO bot: messages >300 chars trigger brain dump prompt.
"""

import logging
import re
from typing import Optional

from .task_pool import create_task, suggest_assignee, PoolTask, TaskPriority

logger = logging.getLogger(__name__)

# Minimum length to consider a message as a brain dump
MIN_BRAIN_DUMP_LENGTH = 300

# Patterns that indicate task boundaries
_TASK_PATTERNS = [
    r"^\d+[\.\)]\s+",          # "1. " or "1) "
    r"^[-•●]\s+",              # "- " or "• "
    r"^(?:TODO|ЗАДАЧА|TASK):\s+",  # "TODO: " or "ЗАДАЧА: "
    r"^(?:Нужно|Надо|Сделать)\s+", # "Нужно ..."
]


def is_brain_dump(text: str) -> bool:
    """Check if a message looks like a brain dump (long + structured)."""
    if len(text) < MIN_BRAIN_DUMP_LENGTH:
        return False
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
    if len(lines) < 3:
        return False
    # Check if at least 2 lines match task patterns
    task_lines = sum(1 for l in lines if _is_task_line(l))
    return task_lines >= 2


def _is_task_line(line: str) -> bool:
    """Check if a line looks like a task item."""
    for pattern in _TASK_PATTERNS:
        if re.match(pattern, line, re.IGNORECASE):
            return True
    return False


def parse_brain_dump(text: str, source: str = "brain_dump") -> list[PoolTask]:
    """Parse a brain dump text into task items.

    Returns list of created PoolTask objects.
    """
    lines = text.strip().split("\n")
    tasks: list[PoolTask] = []
    current_title = ""

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if _is_task_line(line):
            # Save previous task if any
            if current_title:
                task = _create_from_line(current_title, source)
                if task:
                    tasks.append(task)
            # Clean up the new line
            current_title = re.sub(r"^\d+[\.\)]\s+|^[-•●]\s+|^(?:TODO|ЗАДАЧА|TASK):\s+|^(?:Нужно|Надо|Сделать)\s+", "", line, flags=re.IGNORECASE).strip()
        elif current_title:
            # Continuation of previous task
            current_title += " " + line
        else:
            # Non-task line (preamble/context), skip
            pass

    # Don't forget the last task
    if current_title:
        task = _create_from_line(current_title, source)
        if task:
            tasks.append(task)

    logger.info(f"Brain dump parsed: {len(tasks)} tasks from {len(lines)} lines")
    return tasks


def _create_from_line(title: str, source: str) -> Optional[PoolTask]:
    """Create a task from a cleaned title line."""
    title = title.strip()
    if len(title) < 5:
        return None

    # Detect priority from keywords
    priority = _detect_priority(title)

    return create_task(
        title=title,
        priority=priority,
        source=source,
        assigned_by="tim",
    )


def _detect_priority(title: str) -> int:
    """Detect task priority from keywords in title."""
    title_lower = title.lower()
    critical_words = ["срочно", "critical", "asap", "немедленно", "блокер", "blocker"]
    high_words = ["важно", "important", "high", "приоритет"]
    low_words = ["потом", "когда-нибудь", "low", "minor", "мелочь", "nice to have"]

    for w in critical_words:
        if w in title_lower:
            return TaskPriority.CRITICAL
    for w in high_words:
        if w in title_lower:
            return TaskPriority.HIGH
    for w in low_words:
        if w in title_lower:
            return TaskPriority.LOW
    return TaskPriority.MEDIUM


def format_brain_dump_result(tasks: list[PoolTask]) -> str:
    """Format brain dump results for Telegram display."""
    if not tasks:
        return "Не удалось извлечь задачи из текста."

    from .task_pool import format_task_summary

    lines = [f"🧠 Brain Dump → {len(tasks)} задач:\n"]
    for task in tasks:
        lines.append(format_task_summary(task))
        suggestion = suggest_assignee(task.tags)
        if suggestion:
            best, conf = suggestion[0]
            lines.append(f"   💡 → {best} ({conf:.0%})")
        lines.append("")

    return "\n".join(lines)
