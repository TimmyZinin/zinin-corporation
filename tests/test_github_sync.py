"""Tests for GitHub Issues Sync — one-way task_pool → GitHub Issues."""

import json
import os
import threading
from unittest.mock import MagicMock, patch, call

import pytest

from src.event_bus import (
    Event, TASK_CREATED, TASK_ASSIGNED, TASK_STARTED, TASK_COMPLETED,
    get_event_bus, reset_event_bus,
)
from src.github_sync import (
    AGENT_LABEL_MAP,
    REPO,
    SOURCE_LABEL_MAP,
    STATUS_LABEL_MAP,
    _add_issue_comment,
    _build_labels,
    _close_issue,
    _create_issue,
    _gh_run,
    _issue_map,
    _map_lock,
    _on_task_assigned,
    _on_task_completed,
    _on_task_created,
    _on_task_started,
    _update_issue_labels,
    get_sync_status,
    register_github_sync,
    unregister_github_sync,
)


@pytest.fixture(autouse=True)
def _clean_state():
    """Reset EventBus and issue map before each test."""
    reset_event_bus()
    with _map_lock:
        _issue_map.clear()
    yield
    reset_event_bus()
    with _map_lock:
        _issue_map.clear()


# ── gh CLI wrapper ──


class TestGhRun:
    @patch("src.github_sync.subprocess.run")
    def test_successful_command(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="output\n", stderr="")
        ok, out = _gh_run(["issue", "list"])
        assert ok is True
        assert out == "output"
        mock_run.assert_called_once()

    @patch("src.github_sync.subprocess.run")
    def test_failed_command(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error msg")
        ok, out = _gh_run(["issue", "create"])
        assert ok is False
        assert "error msg" in out

    @patch("src.github_sync.subprocess.run", side_effect=FileNotFoundError)
    def test_gh_not_found(self, mock_run):
        ok, out = _gh_run(["auth", "status"])
        assert ok is False
        assert "not found" in out

    @patch("src.github_sync.subprocess.run", side_effect=Exception("subprocess error"))
    def test_generic_error(self, mock_run):
        ok, out = _gh_run(["issue", "list"])
        assert ok is False


# ── Label building ──


class TestBuildLabels:
    def test_basic_labels(self):
        labels = _build_labels(assignee="smm", status="TODO", source="telegram")
        assert "status:todo" in labels
        assert "agent:smm" in labels
        assert "source:telegram" in labels

    def test_empty_values(self):
        labels = _build_labels()
        assert "status:todo" in labels  # default status
        assert len(labels) == 1

    def test_unknown_agent(self):
        labels = _build_labels(assignee="unknown_agent", status="ASSIGNED")
        assert "status:assigned" in labels
        assert not any(l.startswith("agent:") for l in labels)


# ── Issue creation ──


class TestCreateIssue:
    @patch("src.github_sync._gh_run")
    @patch("src.github_sync._save_sync_map")
    def test_creates_issue_and_maps(self, mock_save, mock_gh):
        mock_gh.return_value = (True, "https://github.com/TimmyZinin/zinin-corporation/issues/42")
        result = _create_issue("abc123", "Test task", assignee="smm",
                               tags=["content"], status="TODO", source="telegram")
        assert result == 42
        assert _issue_map["abc123"] == 42
        mock_save.assert_called_once()
        # Check gh arguments
        args = mock_gh.call_args[0][0]
        assert "issue" in args
        assert "create" in args
        assert "[abc123] Test task" in args

    @patch("src.github_sync._gh_run")
    def test_create_failure_returns_none(self, mock_gh):
        mock_gh.return_value = (False, "error")
        result = _create_issue("abc123", "Test task")
        assert result is None
        assert "abc123" not in _issue_map

    @patch("src.github_sync._gh_run")
    def test_unparseable_url_returns_none(self, mock_gh):
        mock_gh.return_value = (True, "something unexpected")
        result = _create_issue("abc123", "Test task")
        assert result is None


# ── Issue update ──


class TestUpdateIssueLabels:
    @patch("src.github_sync._gh_run")
    def test_updates_status_label(self, mock_gh):
        mock_gh.return_value = (True, "")
        with _map_lock:
            _issue_map["t1"] = 10

        _update_issue_labels("t1", status="IN_PROGRESS")

        # Should have called remove for old status labels + add for new
        calls = mock_gh.call_args_list
        assert len(calls) > 0
        # Find the add-label call
        add_calls = [c for c in calls if "--add-label" in str(c)]
        assert len(add_calls) >= 1

    @patch("src.github_sync._gh_run")
    def test_unknown_task_id_skips(self, mock_gh):
        _update_issue_labels("nonexistent", status="TODO")
        mock_gh.assert_not_called()

    @patch("src.github_sync._gh_run")
    def test_updates_agent_label(self, mock_gh):
        mock_gh.return_value = (True, "")
        with _map_lock:
            _issue_map["t1"] = 10

        _update_issue_labels("t1", assignee="accountant")
        calls = mock_gh.call_args_list
        # Should have an add-label call with agent:cfo
        add_args = [str(c) for c in calls if "--add-label" in str(c)]
        assert any("agent:cfo" in a for a in add_args)


# ── Issue close ──


class TestCloseIssue:
    @patch("src.github_sync._gh_run")
    def test_closes_with_comment(self, mock_gh):
        mock_gh.return_value = (True, "")
        with _map_lock:
            _issue_map["t1"] = 10

        _close_issue("t1", result="Task done successfully")

        calls = mock_gh.call_args_list
        # Should have comment call + close call
        assert len(calls) == 2
        comment_call = calls[0][0][0]
        close_call = calls[1][0][0]
        assert "comment" in comment_call
        assert "close" in close_call

    @patch("src.github_sync._gh_run")
    def test_close_without_result_skips_comment(self, mock_gh):
        mock_gh.return_value = (True, "")
        with _map_lock:
            _issue_map["t1"] = 10

        _close_issue("t1", result="")

        calls = mock_gh.call_args_list
        assert len(calls) == 1  # only close, no comment

    @patch("src.github_sync._gh_run")
    def test_close_unknown_task_skips(self, mock_gh):
        _close_issue("nonexistent")
        mock_gh.assert_not_called()


# ── Issue comment ──


class TestAddIssueComment:
    @patch("src.github_sync._gh_run")
    def test_adds_comment(self, mock_gh):
        mock_gh.return_value = (True, "")
        with _map_lock:
            _issue_map["t1"] = 10

        _add_issue_comment("t1", "Test comment")
        mock_gh.assert_called_once()
        args = mock_gh.call_args[0][0]
        assert "comment" in args
        assert "Test comment" in args

    @patch("src.github_sync._gh_run")
    def test_comment_unknown_task_skips(self, mock_gh):
        _add_issue_comment("nonexistent", "comment")
        mock_gh.assert_not_called()


# ── EventBus callbacks ──


class TestEventCallbacks:
    @patch("src.github_sync._create_issue")
    def test_on_task_created(self, mock_create):
        mock_create.return_value = 1
        event = Event(TASK_CREATED, {
            "task_id": "t1", "title": "Write post",
            "assignee": "smm", "tags": ["content"],
            "status": "TODO", "source": "telegram",
        })
        _on_task_created(event)
        mock_create.assert_called_once_with(
            task_id="t1", title="Write post", assignee="smm",
            tags=["content"], status="TODO", source="telegram",
        )

    @patch("src.github_sync._update_issue_labels")
    def test_on_task_assigned(self, mock_update):
        event = Event(TASK_ASSIGNED, {
            "task_id": "t1", "assignee": "smm", "status": "ASSIGNED",
        })
        _on_task_assigned(event)
        mock_update.assert_called_once_with(
            task_id="t1", status="ASSIGNED", assignee="smm",
        )

    @patch("src.github_sync._update_issue_labels")
    def test_on_task_started(self, mock_update):
        event = Event(TASK_STARTED, {
            "task_id": "t1", "assignee": "smm",
        })
        _on_task_started(event)
        mock_update.assert_called_once_with(task_id="t1", status="IN_PROGRESS")

    @patch("src.github_sync._close_issue")
    def test_on_task_completed(self, mock_close):
        event = Event(TASK_COMPLETED, {
            "task_id": "t1", "result": "Done",
        })
        _on_task_completed(event)
        mock_close.assert_called_once_with(task_id="t1", result="Done")


# ── Registration ──


class TestRegistration:
    @patch("src.github_sync._gh_available", return_value=True)
    @patch("src.github_sync._load_sync_map", return_value={})
    @patch("src.github_sync._ensure_labels")
    def test_register_subscribes(self, mock_labels, mock_load, mock_avail):
        bus = get_event_bus()
        initial = bus.subscriber_count()
        register_github_sync()
        assert bus.subscriber_count() == initial + 4
        unregister_github_sync()
        assert bus.subscriber_count() == initial

    @patch("src.github_sync._gh_available", return_value=False)
    def test_register_skips_when_gh_unavailable(self, mock_avail):
        bus = get_event_bus()
        initial = bus.subscriber_count()
        register_github_sync()
        assert bus.subscriber_count() == initial  # no new subscribers


# ── Sync status ──


class TestSyncStatus:
    def test_empty_status(self):
        status = get_sync_status()
        assert status["synced_tasks"] == 0
        assert status["repo"] == REPO

    def test_with_synced_tasks(self):
        with _map_lock:
            _issue_map["t1"] = 10
            _issue_map["t2"] = 11
        status = get_sync_status()
        assert status["synced_tasks"] == 2


# ── Sync map persistence ──


class TestSyncMapPersistence:
    @patch("src.github_sync._sync_file_path")
    def test_load_save_roundtrip(self, mock_path, tmp_path):
        sync_file = str(tmp_path / "github_sync.json")
        mock_path.return_value = sync_file

        from src.github_sync import _load_sync_map, _save_sync_map

        with _map_lock:
            _issue_map["t1"] = 10
            _issue_map["t2"] = 20
        _save_sync_map()

        loaded = _load_sync_map()
        assert loaded == {"t1": 10, "t2": 20}

    @patch("src.github_sync._sync_file_path", return_value="/nonexistent/path.json")
    def test_load_missing_file(self, mock_path):
        from src.github_sync import _load_sync_map
        result = _load_sync_map()
        assert result == {}
