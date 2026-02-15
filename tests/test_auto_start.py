"""Tests for Auto-Start — automatic agent execution on task unblock."""

import threading
from unittest.mock import MagicMock, patch

import pytest

from src.event_bus import Event, TASK_UNBLOCKED, get_event_bus, reset_event_bus
from src.auto_start import (
    MAX_CONCURRENT_AUTO,
    _active_auto_tasks,
    _active_lock,
    _on_task_unblocked,
    _execute_auto_task,
    _semaphore,
    get_auto_start_status,
    register_auto_start,
    unregister_auto_start,
)


@pytest.fixture(autouse=True)
def _clean_state():
    """Reset EventBus and auto-start state before each test."""
    reset_event_bus()
    with _active_lock:
        _active_auto_tasks.clear()
    # Reset semaphore to MAX_CONCURRENT_AUTO
    while _semaphore._value < MAX_CONCURRENT_AUTO:
        _semaphore.release()
    while _semaphore._value > MAX_CONCURRENT_AUTO:
        _semaphore.acquire(blocking=False)
    yield
    reset_event_bus()
    with _active_lock:
        _active_auto_tasks.clear()


def _make_unblocked_event(task_id="t1", assignee="smm", title="Write post"):
    return Event(TASK_UNBLOCKED, {
        "task_id": task_id,
        "assignee": assignee,
        "title": title,
        "unblocked_by": "t0",
    })


# ── Registration ──


class TestRegistration:
    def test_register_subscribes_to_bus(self):
        bus = get_event_bus()
        assert bus.subscriber_count(TASK_UNBLOCKED) == 0
        register_auto_start()
        assert bus.subscriber_count(TASK_UNBLOCKED) == 1

    def test_unregister_removes_listener(self):
        register_auto_start()
        bus = get_event_bus()
        assert bus.subscriber_count(TASK_UNBLOCKED) == 1
        unregister_auto_start()
        assert bus.subscriber_count(TASK_UNBLOCKED) == 0


# ── Event handling ──


class TestOnTaskUnblocked:
    @patch("src.auto_start.threading.Thread")
    @patch("src.agent_mutex.is_busy", return_value=False)
    def test_with_assignee_starts_thread(self, mock_busy, mock_thread_cls):
        mock_thread = MagicMock()
        mock_thread_cls.return_value = mock_thread

        event = _make_unblocked_event(task_id="t1", assignee="smm")
        _on_task_unblocked(event)

        mock_thread_cls.assert_called_once()
        mock_thread.start.assert_called_once()
        assert "t1" in _active_auto_tasks

    def test_without_assignee_skips(self):
        event = _make_unblocked_event(assignee="")
        _on_task_unblocked(event)
        assert len(_active_auto_tasks) == 0

    @patch("src.auto_start.threading.Thread")
    @patch("src.agent_mutex.is_busy", return_value=False)
    def test_duplicate_task_id_skips(self, mock_busy, mock_thread_cls):
        mock_thread = MagicMock()
        mock_thread_cls.return_value = mock_thread

        with _active_lock:
            _active_auto_tasks.add("t1")

        event = _make_unblocked_event(task_id="t1")
        _on_task_unblocked(event)
        mock_thread_cls.assert_not_called()

    @patch("src.agent_mutex.is_busy", return_value=True)
    def test_agent_busy_skips(self, mock_busy):
        event = _make_unblocked_event(task_id="t1", assignee="smm")
        _on_task_unblocked(event)
        assert "t1" not in _active_auto_tasks

    @patch("src.auto_start.threading.Thread")
    @patch("src.agent_mutex.is_busy", return_value=False)
    def test_max_concurrent_skips(self, mock_busy, mock_thread_cls):
        mock_thread = MagicMock()
        mock_thread_cls.return_value = mock_thread

        # Exhaust semaphore
        for _ in range(MAX_CONCURRENT_AUTO):
            _semaphore.acquire(blocking=False)

        event = _make_unblocked_event(task_id="t99")
        _on_task_unblocked(event)
        mock_thread_cls.assert_not_called()

        # Release semaphore back
        for _ in range(MAX_CONCURRENT_AUTO):
            _semaphore.release()


# ── Execution ──


class TestExecuteAutoTask:
    def test_successful_execution(self):
        mock_start = MagicMock(return_value=MagicMock(id="t1"))
        mock_run = MagicMock(return_value="Post written")
        mock_complete = MagicMock()

        _semaphore.acquire(blocking=False)
        with _active_lock:
            _active_auto_tasks.add("t1")

        with patch.dict("sys.modules", {}):
            import src.auto_start as mod
            with patch.object(mod, "_execute_auto_task", wraps=mod._execute_auto_task):
                # Patch at the source module level
                with patch("src.task_pool.start_task", mock_start), \
                     patch("src.flows.run_task", mock_run), \
                     patch("src.task_pool.complete_task", mock_complete):
                    _execute_auto_task("t1", "smm", "Write post")

        mock_start.assert_called_once_with("t1")
        mock_run.assert_called_once_with(
            task_description="Write post",
            agent_name="smm",
            use_memory=True,
            task_type="chat",
        )
        assert "t1" not in _active_auto_tasks

    def test_start_fails_skips_execution(self):
        _semaphore.acquire(blocking=False)
        with _active_lock:
            _active_auto_tasks.add("t1")

        with patch("src.task_pool.start_task", return_value=None):
            _execute_auto_task("t1", "smm", "Write post")

        assert "t1" not in _active_auto_tasks

    def test_error_releases_semaphore(self):
        initial_value = _semaphore._value
        _semaphore.acquire(blocking=False)
        with _active_lock:
            _active_auto_tasks.add("t1")

        with patch("src.task_pool.start_task", return_value=MagicMock(id="t1")), \
             patch("src.flows.run_task", side_effect=RuntimeError("LLM error")):
            _execute_auto_task("t1", "smm", "Write post")

        assert "t1" not in _active_auto_tasks
        assert _semaphore._value == initial_value


# ── Status ──


class TestAutoStartStatus:
    def test_empty_status(self):
        status = get_auto_start_status()
        assert status["active_tasks"] == []
        assert status["active_count"] == 0
        assert status["max_concurrent"] == MAX_CONCURRENT_AUTO
        assert status["available_slots"] == MAX_CONCURRENT_AUTO

    def test_with_active_tasks(self):
        with _active_lock:
            _active_auto_tasks.add("t1")
            _active_auto_tasks.add("t2")

        status = get_auto_start_status()
        assert status["active_count"] == 2
        assert status["available_slots"] == MAX_CONCURRENT_AUTO - 2
