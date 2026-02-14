"""Tests for Agent Mutex — asyncio.Lock per agent (Sprint 10)."""

import asyncio
import time

import pytest

from src.agent_mutex import (
    get_lock,
    is_busy,
    get_busy_agents,
    set_active,
    clear_active,
    get_active_duration,
    reset_all,
    _locks,
    _active,
)


class TestGetLock:
    def setup_method(self):
        reset_all()

    def test_returns_asyncio_lock(self):
        lock = get_lock("manager")
        assert isinstance(lock, asyncio.Lock)

    def test_same_lock_for_same_key(self):
        lock1 = get_lock("manager")
        lock2 = get_lock("manager")
        assert lock1 is lock2

    def test_different_locks_for_different_keys(self):
        lock1 = get_lock("manager")
        lock2 = get_lock("accountant")
        assert lock1 is not lock2

    def test_creates_lock_on_demand(self):
        assert "designer" not in _locks
        get_lock("designer")
        assert "designer" in _locks


class TestIsBusy:
    def setup_method(self):
        reset_all()

    def test_not_busy_by_default(self):
        assert is_busy("manager") is False

    def test_not_busy_without_lock(self):
        assert is_busy("nonexistent") is False

    @pytest.mark.asyncio
    async def test_busy_when_locked(self):
        lock = get_lock("manager")
        await lock.acquire()
        try:
            assert is_busy("manager") is True
        finally:
            lock.release()

    @pytest.mark.asyncio
    async def test_not_busy_after_release(self):
        lock = get_lock("manager")
        await lock.acquire()
        lock.release()
        assert is_busy("manager") is False


class TestGetBusyAgents:
    def setup_method(self):
        reset_all()

    def test_empty_when_none_busy(self):
        get_lock("a")
        get_lock("b")
        assert get_busy_agents() == []

    @pytest.mark.asyncio
    async def test_returns_busy_agents(self):
        lock_a = get_lock("a")
        get_lock("b")
        await lock_a.acquire()
        try:
            busy = get_busy_agents()
            assert "a" in busy
            assert "b" not in busy
        finally:
            lock_a.release()


class TestActiveTracking:
    def setup_method(self):
        reset_all()

    def test_set_active(self):
        set_active("manager")
        assert "manager" in _active

    def test_clear_active(self):
        set_active("manager")
        clear_active("manager")
        assert "manager" not in _active

    def test_clear_active_idempotent(self):
        clear_active("nonexistent")  # should not raise

    def test_get_active_duration_none(self):
        assert get_active_duration("manager") is None

    def test_get_active_duration_positive(self):
        _active["manager"] = time.time() - 5.0
        dur = get_active_duration("manager")
        assert dur is not None
        assert dur >= 4.5


class TestResetAll:
    def test_clears_everything(self):
        get_lock("a")
        set_active("b")
        reset_all()
        assert len(_locks) == 0
        assert len(_active) == 0
