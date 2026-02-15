"""
🤖 Zinin Corp — Auto-Claim (v1.0)

Competing consumers: when a task is created without an assignee,
automatically match it to the best agent using tag-based routing.

Tasks with HITL tags (publish, finance, external) require Tim's approval
before execution.
"""

import logging

logger = logging.getLogger(__name__)

# Minimum confidence from suggest_assignee() to auto-claim
CLAIM_CONFIDENCE_THRESHOLD = 0.5

# Tags that require human approval before agent execution
HITL_TAGS = frozenset({"hitl", "publish", "finance", "external"})


def _on_task_created(event) -> None:
    """Handle task.created — auto-assign if no assignee and good match."""
    payload = event.payload
    task_id = payload.get("task_id", "")
    assignee = payload.get("assignee", "")
    tags = payload.get("tags", [])
    title = payload.get("title", "")
    status = payload.get("status", "TODO")

    # Skip if already assigned or blocked
    if assignee:
        return
    if status == "BLOCKED":
        return

    # Find best agent
    from .task_pool import suggest_assignee, assign_task
    suggestions = suggest_assignee(tags)
    if not suggestions:
        logger.debug(f"Auto-claim: no agent match for task {task_id} (tags={tags})")
        return

    best_agent, confidence = suggestions[0]
    if confidence < CLAIM_CONFIDENCE_THRESHOLD:
        logger.info(
            f"Auto-claim skipped: best match {best_agent} "
            f"({confidence:.2f}) < threshold ({CLAIM_CONFIDENCE_THRESHOLD}) "
            f"for task {task_id}"
        )
        return

    # Assign the task
    result = assign_task(task_id, best_agent, assigned_by="auto-claim")
    if not result:
        logger.warning(f"Auto-claim: assign_task failed for {task_id} → {best_agent}")
        return

    logger.info(f"Auto-claim: {task_id} → {best_agent} (confidence={confidence:.2f})")

    # Check if task needs approval (HITL tags)
    tag_set = set(tags)
    needs_approval = bool(tag_set & HITL_TAGS)

    if needs_approval:
        from .event_bus import get_event_bus, TASK_APPROVAL_REQUIRED
        get_event_bus().emit(TASK_APPROVAL_REQUIRED, {
            "task_id": task_id,
            "assignee": best_agent,
            "title": title,
            "tags": tags,
            "reason": f"Tags require approval: {tag_set & HITL_TAGS}",
        })
        logger.info(f"Auto-claim: approval required for task {task_id} (HITL tags)")


def register_auto_claim() -> None:
    """Register auto-claim listener on the EventBus."""
    from .event_bus import get_event_bus, TASK_CREATED
    get_event_bus().on(TASK_CREATED, _on_task_created)
    logger.info("Auto-claim listener registered")


def unregister_auto_claim() -> None:
    """Unregister auto-claim listener. For testing."""
    from .event_bus import get_event_bus, TASK_CREATED
    get_event_bus().off(TASK_CREATED, _on_task_created)
