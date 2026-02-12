"""
Telegram MCP Server — Task Pool bridge for Agent Teams.

Exposes Task Pool CRUD operations so Agent Teams teammates
can create, query, assign, and complete tasks.

Run: python run_telegram_mcp.py
"""

import logging

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "telegram-mcp",
    instructions="Task Pool bridge for CEO Алексей — create, query, assign, complete tasks",
)


@mcp.tool()
def telegram_create_task(
    title: str,
    priority: int = 3,
    tags: str = "",
) -> str:
    """Create a new task in the Shared Task Pool.

    Args:
        title: Task title (will be auto-tagged if tags not provided)
        priority: 1=critical, 2=high, 3=medium, 4=low
        tags: Comma-separated tags (e.g. "finance,revenue"). Empty = auto-tag.
    """
    from ..task_pool import create_task, format_task_summary, suggest_assignee

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    task = create_task(title, priority=priority, tags=tag_list, source="mcp")

    suggestion = suggest_assignee(task.tags)
    result = format_task_summary(task)
    if suggestion:
        best, conf = suggestion[0]
        result += f"\n💡 Suggested: {best} ({conf:.0%})"
    return result


@mcp.tool()
def telegram_get_tasks(status: str = "", assignee: str = "") -> str:
    """Get tasks from the pool, optionally filtered by status or assignee.

    Args:
        status: Filter by status: TODO, ASSIGNED, IN_PROGRESS, DONE, BLOCKED (empty=all)
        assignee: Filter by agent key: accountant, automator, smm, designer, cpo (empty=all)
    """
    from ..task_pool import (
        get_all_tasks, get_tasks_by_status, get_tasks_by_assignee,
        format_task_summary, TaskStatus,
    )

    if assignee:
        tasks = get_tasks_by_assignee(assignee)
    elif status:
        try:
            ts = TaskStatus(status.upper())
            tasks = get_tasks_by_status(ts)
        except ValueError:
            return f"Unknown status: {status}. Use: TODO, ASSIGNED, IN_PROGRESS, DONE, BLOCKED"
    else:
        tasks = get_all_tasks()

    if not tasks:
        return "No tasks found."

    return "\n\n".join(format_task_summary(t) for t in tasks[:20])


@mcp.tool()
def telegram_get_task(task_id: str) -> str:
    """Get details of a specific task by ID.

    Args:
        task_id: 8-char task ID
    """
    from ..task_pool import get_task, format_task_summary

    task = get_task(task_id)
    if not task:
        return f"Task {task_id} not found."
    return format_task_summary(task)


@mcp.tool()
def telegram_assign_task(task_id: str, assignee: str) -> str:
    """Assign a task to an agent.

    Args:
        task_id: 8-char task ID
        assignee: Agent key: accountant, automator, smm, designer, cpo
    """
    from ..task_pool import assign_task, format_task_summary

    task = assign_task(task_id, assignee=assignee, assigned_by="agent-teams")
    if not task:
        return f"Failed to assign task {task_id}. Check status and ID."
    return f"Assigned → {assignee}\n\n{format_task_summary(task)}"


@mcp.tool()
def telegram_complete_task(task_id: str, result: str = "") -> str:
    """Mark a task as completed.

    Args:
        task_id: 8-char task ID
        result: Optional result/notes text
    """
    from ..task_pool import complete_task, format_task_summary

    task = complete_task(task_id, result=result)
    if not task:
        return f"Failed to complete task {task_id}. Must be ASSIGNED or IN_PROGRESS."
    return f"Completed!\n\n{format_task_summary(task)}"


@mcp.tool()
def telegram_get_pool_summary() -> str:
    """Get task pool summary — count by status."""
    from ..task_pool import format_pool_summary
    return format_pool_summary()
