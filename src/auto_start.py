"""
⚡ Zinin Corp — Auto-Start (v1.0)

Automatically executes agents when tasks get unblocked by the Dependency Engine.
Subscribes to EventBus "task.unblocked" events.

Safety mechanisms:
- Semaphore limits concurrent auto-executions (default: 3)
- Duplicate task prevention via active set
- Agent mutex integration (skip if agent is busy)
- Daemon threads (won't block shutdown)
"""

import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)

# Safety: max concurrent auto-executions
MAX_CONCURRENT_AUTO = 3
_semaphore = threading.Semaphore(MAX_CONCURRENT_AUTO)
_active_auto_tasks: set[str] = set()
_active_lock = threading.Lock()


def _on_task_unblocked(event) -> None:
    """Sync callback for task.unblocked events.

    Spawns a daemon thread to run the agent because:
    1. emit() is called from sync context (task_pool)
    2. Agent execution is blocking (CrewAI runs synchronously)
    """
    payload = event.payload
    task_id = payload.get("task_id", "")
    assignee = payload.get("assignee", "")
    title = payload.get("title", "")

    if not assignee:
        logger.info(f"Auto-start skipped: task {task_id} has no assignee")
        return

    # Prevent duplicate execution
    with _active_lock:
        if task_id in _active_auto_tasks:
            logger.warning(f"Auto-start skipped: task {task_id} already executing")
            return

    # Check if agent is busy
    try:
        from .agent_mutex import is_busy
        if is_busy(assignee):
            logger.info(
                f"Auto-start deferred: agent {assignee} is busy "
                f"(task {task_id} stays ASSIGNED)"
            )
            return
    except ImportError:
        pass

    # Check semaphore (non-blocking)
    if not _semaphore.acquire(blocking=False):
        logger.warning(
            f"Auto-start skipped: max concurrent ({MAX_CONCURRENT_AUTO}) reached "
            f"for task {task_id}"
        )
        return

    with _active_lock:
        _active_auto_tasks.add(task_id)

    # Spawn background thread for execution
    thread = threading.Thread(
        target=_execute_auto_task,
        args=(task_id, assignee, title),
        daemon=True,
        name=f"auto-start-{task_id}",
    )
    thread.start()
    logger.info(f"Auto-start: launched {assignee} for task {task_id}: {title[:60]}")


def _execute_auto_task(task_id: str, assignee: str, title: str) -> None:
    """Run agent execution in a background thread."""
    try:
        from .task_pool import start_task, complete_task
        from .flows import run_task

        # Move task to IN_PROGRESS
        task = start_task(task_id)
        if not task:
            logger.warning(f"Auto-start: could not start task {task_id}")
            return

        # Execute agent
        result = run_task(
            task_description=title,
            agent_name=assignee,
            use_memory=True,
            task_type="chat",
        )

        # Complete the task
        complete_task(task_id, result=result[:500] if result else "")
        logger.info(f"Auto-start completed: task {task_id} by {assignee}")

    except Exception as e:
        logger.error(f"Auto-start failed for task {task_id}: {e}", exc_info=True)
    finally:
        _semaphore.release()
        with _active_lock:
            _active_auto_tasks.discard(task_id)


def register_auto_start() -> None:
    """Register the auto-start listener on the global EventBus."""
    from .event_bus import get_event_bus, TASK_UNBLOCKED
    bus = get_event_bus()
    bus.on(TASK_UNBLOCKED, _on_task_unblocked)
    logger.info("Auto-start listener registered")


def unregister_auto_start() -> None:
    """Unregister the auto-start listener. For testing."""
    from .event_bus import get_event_bus, TASK_UNBLOCKED
    bus = get_event_bus()
    bus.off(TASK_UNBLOCKED, _on_task_unblocked)


def get_auto_start_status() -> dict:
    """Return current auto-start status for monitoring."""
    with _active_lock:
        active = list(_active_auto_tasks)
    return {
        "active_tasks": active,
        "active_count": len(active),
        "max_concurrent": MAX_CONCURRENT_AUTO,
        "available_slots": MAX_CONCURRENT_AUTO - len(active),
    }
