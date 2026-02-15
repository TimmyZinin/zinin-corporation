"""
⚡ Zinin Corp — Auto-Start (v1.1)

Automatically executes agents when tasks get unblocked by the Dependency Engine.
Subscribes to EventBus "task.unblocked" and "task.approved" events.

Safety mechanisms:
- Semaphore limits concurrent auto-executions (default: 3)
- Duplicate task prevention via active set
- Agent mutex integration (skip if agent is busy)
- Daemon threads (won't block shutdown)
- Checkpoint logging to GitHub Issues (via github_sync)
- Retry on failure (max 2 retries)
"""

import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)

# Safety: max concurrent auto-executions
MAX_CONCURRENT_AUTO = 3
MAX_RETRIES = 2

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


# ──────────────────────────────────────────────────────────
# Checkpoint helpers
# ──────────────────────────────────────────────────────────

def _set_checkpoint(task_id: str, checkpoint: str) -> None:
    """Update checkpoint in task_pool."""
    try:
        from .task_pool import set_checkpoint
        set_checkpoint(task_id, checkpoint)
    except Exception as e:
        logger.debug(f"Checkpoint set failed for {task_id}: {e}")


def _log_checkpoint(task_id: str, stage: str, message: str) -> None:
    """Log checkpoint as GitHub Issue comment (if github_sync active)."""
    try:
        from .github_sync import _add_issue_comment
        _add_issue_comment(task_id, f"**[{stage.upper()}]** {message}")
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"Checkpoint log failed for {task_id}: {e}")


# ──────────────────────────────────────────────────────────
# Execution with checkpoints
# ──────────────────────────────────────────────────────────

def _execute_auto_task(task_id: str, assignee: str, title: str) -> None:
    """Run agent execution in a background thread with checkpoint logging."""
    try:
        from .task_pool import start_task, complete_task
        from .flows import run_task

        # Checkpoint 1: start
        task = start_task(task_id)
        if not task:
            logger.warning(f"Auto-start: could not start task {task_id}")
            return
        _set_checkpoint(task_id, "started")
        _log_checkpoint(task_id, "started", f"Agent {assignee} начал выполнение")

        # Checkpoint 2: executing
        _set_checkpoint(task_id, "executing")
        result = run_task(
            task_description=title,
            agent_name=assignee,
            use_memory=True,
            task_type="chat",
        )
        _log_checkpoint(task_id, "executing", f"Результат получен ({len(result or '')} chars)")

        # Checkpoint 3: done
        complete_task(task_id, result=result[:500] if result else "")
        _set_checkpoint(task_id, "done")
        _log_checkpoint(task_id, "done", "Задача завершена")
        logger.info(f"Auto-start completed: task {task_id} by {assignee}")

    except Exception as e:
        logger.error(f"Auto-start failed for task {task_id}: {e}", exc_info=True)
        _set_checkpoint(task_id, f"failed:{str(e)[:100]}")
        _log_checkpoint(task_id, "failed", str(e)[:200])
        _maybe_retry(task_id, assignee, title)
    finally:
        _semaphore.release()
        with _active_lock:
            _active_auto_tasks.discard(task_id)


def _maybe_retry(task_id: str, assignee: str, title: str) -> None:
    """Retry task if retry_count < MAX_RETRIES."""
    try:
        from .task_pool import increment_retry, assign_task
        from .event_bus import get_event_bus, TASK_RETRY

        retry_count = increment_retry(task_id)
        if retry_count < 0:
            return  # task not found

        if retry_count <= MAX_RETRIES:
            logger.info(f"Auto-start retry {retry_count}/{MAX_RETRIES} for task {task_id}")
            # Re-assign to make it eligible for auto-start again
            assign_task(task_id, assignee, assigned_by="auto-retry")
            get_event_bus().emit(TASK_RETRY, {
                "task_id": task_id,
                "assignee": assignee,
                "title": title,
                "retry_count": retry_count,
            })
        else:
            logger.warning(
                f"Auto-start: max retries ({MAX_RETRIES}) exceeded for task {task_id}"
            )
            _log_checkpoint(task_id, "max_retries",
                            f"Превышено максимальное число попыток ({MAX_RETRIES})")
    except Exception as e:
        logger.error(f"Auto-start retry failed for {task_id}: {e}")


def _on_task_retry(event) -> None:
    """Handle task.retry events — re-trigger execution."""
    _on_task_unblocked(event)


def _on_task_approved(event) -> None:
    """Handle task.approved events — reuse unblocked logic to start execution."""
    _on_task_unblocked(event)


def register_auto_start() -> None:
    """Register the auto-start listener on the global EventBus."""
    from .event_bus import get_event_bus, TASK_UNBLOCKED, TASK_APPROVED, TASK_RETRY
    bus = get_event_bus()
    bus.on(TASK_UNBLOCKED, _on_task_unblocked)
    bus.on(TASK_APPROVED, _on_task_approved)
    bus.on(TASK_RETRY, _on_task_retry)
    logger.info("Auto-start listener registered")


def unregister_auto_start() -> None:
    """Unregister the auto-start listener. For testing."""
    from .event_bus import get_event_bus, TASK_UNBLOCKED, TASK_APPROVED, TASK_RETRY
    bus = get_event_bus()
    bus.off(TASK_UNBLOCKED, _on_task_unblocked)
    bus.off(TASK_APPROVED, _on_task_approved)
    bus.off(TASK_RETRY, _on_task_retry)


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
