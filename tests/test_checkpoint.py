"""Tests for Checkpoint Resume — checkpoint logging, retry logic."""

from unittest.mock import MagicMock, patch, call

import pytest

from src.event_bus import Event, TASK_RETRY, TASK_UNBLOCKED, get_event_bus, reset_event_bus
from src.auto_start import (
    MAX_RETRIES,
    _active_auto_tasks,
    _active_lock,
    _execute_auto_task,
    _log_checkpoint,
    _maybe_retry,
    _on_task_retry,
    _set_checkpoint,
    _semaphore,
    MAX_CONCURRENT_AUTO,
)


@pytest.fixture(autouse=True)
def _clean_state():
    """Reset EventBus and auto-start state before each test."""
    reset_event_bus()
    with _active_lock:
        _active_auto_tasks.clear()
    # Reset semaphore
    while _semaphore._value < MAX_CONCURRENT_AUTO:
        _semaphore.release()
    while _semaphore._value > MAX_CONCURRENT_AUTO:
        _semaphore.acquire(blocking=False)
    yield
    reset_event_bus()
    with _active_lock:
        _active_auto_tasks.clear()


# ── Checkpoint helpers ──


class TestSetCheckpoint:
    @patch("src.task_pool.set_checkpoint")
    def test_sets_checkpoint(self, mock_set):
        mock_set.return_value = True
        _set_checkpoint("t1", "started")
        mock_set.assert_called_once_with("t1", "started")

    @patch("src.task_pool.set_checkpoint", side_effect=Exception("DB error"))
    def test_error_does_not_raise(self, mock_set):
        _set_checkpoint("t1", "started")  # should not raise


class TestLogCheckpoint:
    @patch("src.github_sync._add_issue_comment")
    def test_logs_to_github(self, mock_comment):
        _log_checkpoint("t1", "started", "Agent smm начал выполнение")
        mock_comment.assert_called_once()
        args = mock_comment.call_args[0]
        assert "t1" in args
        assert "STARTED" in args[1]

    @patch("src.github_sync._add_issue_comment", side_effect=Exception("GH error"))
    def test_error_does_not_raise(self, mock_comment):
        _log_checkpoint("t1", "started", "test")  # should not raise


# ── Execution with checkpoints ──


class TestExecuteWithCheckpoints:
    @patch("src.github_sync._add_issue_comment")
    @patch("src.task_pool.set_checkpoint")
    def test_successful_execution_sets_3_checkpoints(self, mock_set_cp, mock_comment):
        mock_start = MagicMock(return_value=MagicMock(id="t1"))
        mock_run = MagicMock(return_value="Post written")
        mock_complete = MagicMock()

        _semaphore.acquire(blocking=False)
        with _active_lock:
            _active_auto_tasks.add("t1")

        with patch("src.task_pool.start_task", mock_start), \
             patch("src.flows.run_task", mock_run), \
             patch("src.task_pool.complete_task", mock_complete):
            _execute_auto_task("t1", "smm", "Write post")

        # Should have 3 checkpoints: started, executing, done
        checkpoint_calls = [c[0] for c in mock_set_cp.call_args_list]
        assert ("t1", "started") in checkpoint_calls
        assert ("t1", "executing") in checkpoint_calls
        assert ("t1", "done") in checkpoint_calls

    @patch("src.github_sync._add_issue_comment")
    @patch("src.task_pool.set_checkpoint")
    def test_failed_execution_sets_failed_checkpoint(self, mock_set_cp, mock_comment):
        mock_start = MagicMock(return_value=MagicMock(id="t1"))
        mock_run = MagicMock(side_effect=RuntimeError("LLM timeout"))

        _semaphore.acquire(blocking=False)
        with _active_lock:
            _active_auto_tasks.add("t1")

        with patch("src.task_pool.start_task", mock_start), \
             patch("src.flows.run_task", mock_run), \
             patch("src.auto_start._maybe_retry"):
            _execute_auto_task("t1", "smm", "Write post")

        # Should have failed checkpoint
        checkpoint_values = [c[0][1] for c in mock_set_cp.call_args_list]
        assert any("failed:" in v for v in checkpoint_values)


# ── Retry logic ──


class TestMaybeRetry:
    @patch("src.task_pool.assign_task")
    @patch("src.task_pool.increment_retry", return_value=1)
    def test_retries_when_under_limit(self, mock_inc, mock_assign):
        mock_assign.return_value = MagicMock()
        received = []
        bus = get_event_bus()
        bus.on(TASK_RETRY, lambda e: received.append(e))

        _maybe_retry("t1", "smm", "Write post")

        mock_assign.assert_called_once_with("t1", "smm", assigned_by="auto-retry")
        assert len(received) == 1
        assert received[0].payload["retry_count"] == 1

    @patch("src.task_pool.increment_retry", return_value=3)
    def test_stops_when_max_retries_exceeded(self, mock_inc):
        received = []
        bus = get_event_bus()
        bus.on(TASK_RETRY, lambda e: received.append(e))

        with patch("src.github_sync._add_issue_comment"):
            _maybe_retry("t1", "smm", "Write post")

        assert len(received) == 0  # no retry event

    @patch("src.task_pool.increment_retry", return_value=-1)
    def test_skips_when_task_not_found(self, mock_inc):
        _maybe_retry("nonexistent", "smm", "Write post")  # should not raise

    @patch("src.task_pool.increment_retry", return_value=2)
    @patch("src.task_pool.assign_task")
    def test_retry_at_boundary(self, mock_assign, mock_inc):
        """MAX_RETRIES=2, retry_count=2 should still retry."""
        mock_assign.return_value = MagicMock()
        received = []
        bus = get_event_bus()
        bus.on(TASK_RETRY, lambda e: received.append(e))

        _maybe_retry("t1", "smm", "Write post")

        assert len(received) == 1  # retry_count <= MAX_RETRIES


# ── Task retry event ──


class TestOnTaskRetry:
    @patch("src.auto_start.threading.Thread")
    @patch("src.agent_mutex.is_busy", return_value=False)
    def test_retry_starts_thread(self, mock_busy, mock_thread_cls):
        mock_thread = MagicMock()
        mock_thread_cls.return_value = mock_thread

        event = Event(TASK_RETRY, {
            "task_id": "t1",
            "assignee": "smm",
            "title": "Write post",
            "retry_count": 1,
        })
        _on_task_retry(event)

        mock_thread_cls.assert_called_once()
        mock_thread.start.assert_called_once()


# ── Constants ──


class TestCheckpointConstants:
    def test_max_retries_reasonable(self):
        assert 1 <= MAX_RETRIES <= 5
