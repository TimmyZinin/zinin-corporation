"""
🔔 Zinin Corp — EventBus (v1.0)

Lightweight in-process pub/sub for event-driven agent orchestration.
Thread-safe, supports both sync and async callbacks. Zero external dependencies.

Usage:
    bus = get_event_bus()
    bus.on("task.completed", my_callback)
    bus.emit("task.completed", {"task_id": "abc123"})
"""

import asyncio
import logging
import threading
import time
from collections import deque
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Event type constants
# ──────────────────────────────────────────────────────────

TASK_CREATED = "task.created"
TASK_ASSIGNED = "task.assigned"
TASK_STARTED = "task.started"
TASK_COMPLETED = "task.completed"
TASK_UNBLOCKED = "task.unblocked"

AGENT_EXECUTION_STARTED = "agent.execution.started"
AGENT_EXECUTION_COMPLETED = "agent.execution.completed"

QUALITY_SCORED = "quality.scored"

TASK_APPROVAL_REQUIRED = "task.approval.required"
TASK_APPROVED = "task.approved"
TASK_REJECTED = "task.rejected"
TASK_RETRY = "task.retry"


# ──────────────────────────────────────────────────────────
# Event record
# ──────────────────────────────────────────────────────────

class Event:
    """Immutable event record with type, payload, and timestamp."""

    __slots__ = ("type", "payload", "timestamp")

    def __init__(self, event_type: str, payload: dict):
        self.type = event_type
        self.payload = payload
        self.timestamp = time.time()

    def __repr__(self) -> str:
        return f"Event({self.type!r}, payload_keys={list(self.payload.keys())})"


# ──────────────────────────────────────────────────────────
# EventBus
# ──────────────────────────────────────────────────────────

class EventBus:
    """In-process pub/sub bus.

    - Thread-safe via threading.Lock
    - Supports both sync and async callbacks
    - Fire-and-forget: emit() never raises from subscriber errors
    - Optional event history (last N events) for debugging
    """

    def __init__(self, history_size: int = 100):
        self._subscribers: dict[str, list[Callable]] = {}
        self._lock = threading.Lock()
        self._history: deque[Event] = deque(maxlen=history_size)

    def on(self, event_type: str, callback: Callable) -> None:
        """Subscribe to an event type."""
        with self._lock:
            self._subscribers.setdefault(event_type, []).append(callback)

    def off(self, event_type: str, callback: Callable) -> None:
        """Unsubscribe from an event type."""
        with self._lock:
            subs = self._subscribers.get(event_type, [])
            try:
                subs.remove(callback)
            except ValueError:
                pass

    def emit(self, event_type: str, payload: dict | None = None) -> None:
        """Emit an event. Calls all subscribers. Never raises from subscriber errors."""
        event = Event(event_type, payload or {})

        with self._lock:
            self._history.append(event)
            # Copy subscriber list under lock to avoid mutation during iteration
            subs = list(self._subscribers.get(event_type, []))

        # Call subscribers OUTSIDE lock to prevent deadlocks with task_pool._lock
        for cb in subs:
            try:
                if asyncio.iscoroutinefunction(cb):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(cb(event))
                    except RuntimeError:
                        logger.debug(
                            f"EventBus: async callback {cb.__name__} skipped "
                            f"(no running event loop)"
                        )
                else:
                    cb(event)
            except Exception as e:
                logger.warning(
                    f"EventBus subscriber error for '{event_type}': {e}",
                    exc_info=True,
                )

    def get_history(
        self,
        event_type: str | None = None,
        limit: int = 50,
    ) -> list[Event]:
        """Get recent events, optionally filtered by type."""
        with self._lock:
            events = list(self._history)
        if event_type:
            events = [e for e in events if e.type == event_type]
        return events[-limit:]

    def subscriber_count(self, event_type: str | None = None) -> int:
        """Count subscribers, optionally for a specific event type."""
        with self._lock:
            if event_type:
                return len(self._subscribers.get(event_type, []))
            return sum(len(subs) for subs in self._subscribers.values())

    def clear(self) -> None:
        """Clear all subscribers and history. For testing."""
        with self._lock:
            self._subscribers.clear()
            self._history.clear()


# ──────────────────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────────────────

_bus: Optional[EventBus] = None
_bus_lock = threading.Lock()


def get_event_bus() -> EventBus:
    """Get or create the global EventBus singleton."""
    global _bus
    if _bus is None:
        with _bus_lock:
            if _bus is None:
                _bus = EventBus()
    return _bus


def reset_event_bus() -> None:
    """Reset the global EventBus. For testing only."""
    global _bus
    with _bus_lock:
        if _bus:
            _bus.clear()
        _bus = None
