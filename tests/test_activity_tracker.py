"""Tests for src/activity_tracker.py — Agent activity logging."""

import sys
import os
import json
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.activity_tracker import (
    AGENT_NAMES,
    AGENT_EMOJI,
    log_task_start,
    log_task_end,
    log_communication,
    log_communication_end,
    get_agent_status,
    get_all_statuses,
    get_recent_events,
    get_agent_task_count,
    get_task_progress,
    _trim_events,
)


def _tmp_log():
    """Create a temp file and patch _log_path to use it."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    f.write('{"events": [], "agent_status": {}}')
    f.close()
    return f.name


# ── Agent Registry ───────────────────────────────────────

class TestAgentRegistry:
    def test_four_agents_in_names(self):
        assert len(AGENT_NAMES) == 4

    def test_four_agents_in_emoji(self):
        assert len(AGENT_EMOJI) == 4

    def test_same_keys(self):
        assert set(AGENT_NAMES.keys()) == set(AGENT_EMOJI.keys())

    def test_expected_agents(self):
        expected = {"manager", "accountant", "smm", "automator"}
        assert set(AGENT_NAMES.keys()) == expected

    def test_names_are_russian(self):
        for name in AGENT_NAMES.values():
            assert any(ord(c) > 127 for c in name), f"{name} is not Russian"


# ── Task Logging ─────────────────────────────────────────

class TestTaskLogging:
    def test_log_task_start(self):
        path = _tmp_log()
        with patch("src.activity_tracker._log_path", return_value=path):
            log_task_start("manager", "Test task")
            status = get_agent_status("manager")
            assert status["status"] == "working"
            assert status["task"] == "Test task"
            assert status["started_at"] is not None
        os.unlink(path)

    def test_log_task_end_success(self):
        path = _tmp_log()
        with patch("src.activity_tracker._log_path", return_value=path):
            log_task_start("smm", "Write post")
            log_task_end("smm", "Write post", success=True)
            status = get_agent_status("smm")
            assert status["status"] == "idle"
            assert status["last_task"] == "Write post"
            assert status["last_task_success"] is True
        os.unlink(path)

    def test_log_task_end_failure(self):
        path = _tmp_log()
        with patch("src.activity_tracker._log_path", return_value=path):
            log_task_start("automator", "API call")
            log_task_end("automator", "API call", success=False)
            status = get_agent_status("automator")
            assert status["last_task_success"] is False
        os.unlink(path)

    def test_task_description_truncation(self):
        path = _tmp_log()
        with patch("src.activity_tracker._log_path", return_value=path):
            long_desc = "A" * 200
            log_task_start("manager", long_desc)
            status = get_agent_status("manager")
            assert len(status["task"]) == 120
        os.unlink(path)


# ── Communication Logging ────────────────────────────────

class TestCommunication:
    def test_log_communication(self):
        path = _tmp_log()
        with patch("src.activity_tracker._log_path", return_value=path):
            log_task_start("manager", "Delegating")
            log_task_start("smm", "Receiving")
            log_communication("manager", "smm", "Context pass")
            events = get_recent_events(hours=1, limit=10)
            comm_events = [e for e in events if e["type"] == "communication"]
            assert len(comm_events) >= 1
            assert comm_events[-1]["from_agent"] == "manager"
            assert comm_events[-1]["to_agent"] == "smm"
        os.unlink(path)

    def test_log_communication_end(self):
        path = _tmp_log()
        with patch("src.activity_tracker._log_path", return_value=path):
            log_task_start("manager", "Delegating")
            log_communication("manager", "smm", "Pass")
            log_communication_end("manager")
            status = get_agent_status("manager")
            assert status.get("communicating_with") is None
        os.unlink(path)


# ── Status Queries ───────────────────────────────────────

class TestStatusQueries:
    def test_get_agent_status_idle_default(self):
        path = _tmp_log()
        with patch("src.activity_tracker._log_path", return_value=path):
            status = get_agent_status("manager")
            assert status["status"] == "idle"
            assert status["task"] is None
        os.unlink(path)

    def test_get_all_statuses_returns_all_agents(self):
        path = _tmp_log()
        with patch("src.activity_tracker._log_path", return_value=path):
            statuses = get_all_statuses()
            assert set(statuses.keys()) == set(AGENT_NAMES.keys())
        os.unlink(path)

    def test_get_all_statuses_default_idle(self):
        path = _tmp_log()
        with patch("src.activity_tracker._log_path", return_value=path):
            statuses = get_all_statuses()
            for key, st in statuses.items():
                assert st["status"] == "idle"
        os.unlink(path)


# ── Events ───────────────────────────────────────────────

class TestEvents:
    def test_get_recent_events_empty(self):
        path = _tmp_log()
        with patch("src.activity_tracker._log_path", return_value=path):
            events = get_recent_events(hours=1)
            assert events == []
        os.unlink(path)

    def test_get_recent_events_after_logging(self):
        path = _tmp_log()
        with patch("src.activity_tracker._log_path", return_value=path):
            log_task_start("manager", "Task A")
            log_task_end("manager", "Task A")
            events = get_recent_events(hours=1)
            assert len(events) == 2
            assert events[0]["type"] == "task_start"
            assert events[1]["type"] == "task_end"
        os.unlink(path)

    def test_get_agent_task_count(self):
        path = _tmp_log()
        with patch("src.activity_tracker._log_path", return_value=path):
            log_task_start("smm", "Post 1")
            log_task_end("smm", "Post 1")
            log_task_start("smm", "Post 2")
            log_task_end("smm", "Post 2")
            count = get_agent_task_count("smm", hours=1)
            assert count == 2
        os.unlink(path)

    def test_task_count_per_agent(self):
        path = _tmp_log()
        with patch("src.activity_tracker._log_path", return_value=path):
            log_task_start("manager", "Task")
            log_task_end("manager", "Task")
            log_task_start("smm", "Post")
            log_task_end("smm", "Post")
            assert get_agent_task_count("manager", hours=1) == 1
            assert get_agent_task_count("smm", hours=1) == 1
            assert get_agent_task_count("automator", hours=1) == 0
        os.unlink(path)


# ── Progress Estimation ─────────────────────────────────

class TestProgress:
    def test_idle_agent_returns_none(self):
        path = _tmp_log()
        with patch("src.activity_tracker._log_path", return_value=path):
            progress = get_task_progress("manager")
            assert progress is None
        os.unlink(path)

    def test_working_agent_returns_float(self):
        path = _tmp_log()
        with patch("src.activity_tracker._log_path", return_value=path):
            log_task_start("manager", "Working on something")
            progress = get_task_progress("manager")
            assert progress is not None
            assert isinstance(progress, float)
            assert 0.0 <= progress <= 0.95
        os.unlink(path)

    def test_progress_capped_at_95(self):
        path = _tmp_log()
        with patch("src.activity_tracker._log_path", return_value=path):
            log_task_start("manager", "Old task")
            # Even if a long time passes, cap at 95%
            progress = get_task_progress("manager")
            assert progress <= 0.95
        os.unlink(path)


# ── Trim Events ─────────────────────────────────────────

class TestTrimEvents:
    def test_trim_keeps_max(self):
        data = {"events": [{"id": i} for i in range(600)]}
        _trim_events(data, max_events=500)
        assert len(data["events"]) == 500

    def test_trim_keeps_latest(self):
        data = {"events": [{"id": i} for i in range(600)]}
        _trim_events(data, max_events=500)
        assert data["events"][0]["id"] == 100
        assert data["events"][-1]["id"] == 599

    def test_trim_no_op_when_under_limit(self):
        data = {"events": [{"id": i} for i in range(10)]}
        _trim_events(data, max_events=500)
        assert len(data["events"]) == 10
