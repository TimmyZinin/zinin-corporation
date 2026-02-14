"""Agent Mutex — prevents concurrent access to the same agent.

Each agent gets its own asyncio.Lock. When an agent is busy processing
a request, subsequent requests see a "busy" status and can wait or skip.
"""

import asyncio
import time
import logging

logger = logging.getLogger(__name__)

_locks: dict[str, asyncio.Lock] = {}
_active: dict[str, float] = {}  # agent_key -> start timestamp


def get_lock(agent_key: str) -> asyncio.Lock:
    """Get or create a lock for the given agent."""
    if agent_key not in _locks:
        _locks[agent_key] = asyncio.Lock()
    return _locks[agent_key]


def is_busy(agent_key: str) -> bool:
    """Check if agent is currently processing a request."""
    lock = _locks.get(agent_key)
    return lock is not None and lock.locked()


def get_busy_agents() -> list[str]:
    """Return list of agent keys that are currently busy."""
    return [k for k, lock in _locks.items() if lock.locked()]


def set_active(agent_key: str):
    """Record when an agent starts working."""
    _active[agent_key] = time.time()


def clear_active(agent_key: str):
    """Clear the active timestamp when agent finishes."""
    _active.pop(agent_key, None)


def get_active_duration(agent_key: str) -> float | None:
    """How many seconds has the agent been active? None if idle."""
    start = _active.get(agent_key)
    if start is None:
        return None
    return time.time() - start


def reset_all():
    """Reset all locks and active states. For testing only."""
    _locks.clear()
    _active.clear()
