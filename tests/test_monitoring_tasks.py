"""
🧪 Group 2: Monitoring tests

Tests that monitoring accurately tracks delegated tasks.
When Alexey delegates to Matthias, Matthias should show
a real task count > 0 in monitoring.
"""

import pytest
import sys
import os
import json
import tempfile
import threading
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture(autouse=True)
def isolate_activity_log(tmp_path):
    """Use a temp file for activity_log.json so tests don't interfere."""
    log_file = str(tmp_path / "activity_log.json")
    with patch("src.activity_tracker._log_path", return_value=log_file):
        # Reset the lock to avoid cross-test contamination
        import src.activity_tracker as at
        at._lock = threading.Lock()
        yield log_file


class TestLogDelegation:
    """Tests for log_delegation() — new event type."""

    def test_log_delegation_exists(self):
        """log_delegation function must exist in activity_tracker."""
        from src.activity_tracker import log_delegation
        assert callable(log_delegation)

    def test_log_delegation_creates_event(self):
        """log_delegation creates a delegation event in the log."""
        from src.activity_tracker import log_delegation, _load_log
        log_delegation("manager", "accountant", "Подготовить бюджет")
        data = _load_log()
        events = data.get("events", [])
        assert len(events) >= 1
        evt = events[-1]
        assert evt["type"] == "delegation"
        assert evt["from_agent"] == "manager"
        assert evt["to_agent"] == "accountant"
        assert "бюджет" in evt["description"].lower()

    def test_log_delegation_has_timestamp(self):
        """Delegation event has a timestamp."""
        from src.activity_tracker import log_delegation, _load_log
        log_delegation("manager", "automator", "Настроить API")
        data = _load_log()
        evt = data["events"][-1]
        assert "timestamp" in evt
        assert len(evt["timestamp"]) > 10  # ISO format

    def test_log_delegation_truncates_description(self):
        """Description is truncated to 120 chars."""
        from src.activity_tracker import log_delegation, _load_log
        long_desc = "A" * 200
        log_delegation("manager", "accountant", long_desc)
        data = _load_log()
        evt = data["events"][-1]
        assert len(evt["description"]) <= 120

    def test_log_multiple_delegations(self):
        """Multiple delegations create multiple events."""
        from src.activity_tracker import log_delegation, get_recent_events
        log_delegation("manager", "accountant", "Task 1")
        log_delegation("manager", "automator", "Task 2")
        log_delegation("manager", "smm", "Task 3")
        events = get_recent_events(hours=1)
        delegation_events = [e for e in events if e["type"] == "delegation"]
        assert len(delegation_events) == 3


class TestGetAgentTaskCount:
    """Tests for get_agent_task_count() with delegation support."""

    def test_counts_task_end_events(self):
        """get_agent_task_count counts task_end events."""
        from src.activity_tracker import log_task_start, log_task_end, get_agent_task_count
        log_task_start("accountant", "Подготовить отчёт")
        log_task_end("accountant", "Подготовить отчёт", success=True)
        count = get_agent_task_count("accountant", hours=24)
        assert count >= 1

    def test_counts_delegation_events(self):
        """get_agent_task_count also counts delegation events for the target agent."""
        from src.activity_tracker import log_delegation, get_agent_task_count
        log_delegation("manager", "accountant", "Подготовить бюджет")
        log_delegation("manager", "accountant", "Проанализировать расходы")
        count = get_agent_task_count("accountant", hours=24)
        assert count >= 2

    def test_counts_both_task_end_and_delegation(self):
        """Task count includes both task_end and delegation events."""
        from src.activity_tracker import (
            log_task_start, log_task_end, log_delegation, get_agent_task_count,
        )
        log_task_start("automator", "Настроить webhook")
        log_task_end("automator", "Настроить webhook", success=True)
        log_delegation("manager", "automator", "Проверить API")
        count = get_agent_task_count("automator", hours=24)
        assert count >= 2

    def test_does_not_count_other_agent_events(self):
        """Events for other agents are not counted."""
        from src.activity_tracker import log_delegation, get_agent_task_count
        log_delegation("manager", "accountant", "Task for accountant")
        count = get_agent_task_count("automator", hours=24)
        assert count == 0

    def test_zero_for_no_events(self):
        """Returns 0 when no events exist."""
        from src.activity_tracker import get_agent_task_count
        count = get_agent_task_count("accountant", hours=24)
        assert count == 0


class TestGetAgentStatusQueued:
    """Tests for get_agent_status() with queued_tasks field."""

    def test_status_has_queued_tasks_field(self):
        """Agent status includes queued_tasks field."""
        from src.activity_tracker import get_agent_status
        status = get_agent_status("accountant")
        assert "queued_tasks" in status

    def test_idle_agent_zero_queued(self):
        """Idle agent with no delegations has 0 queued_tasks."""
        from src.activity_tracker import get_agent_status
        status = get_agent_status("accountant")
        assert status["queued_tasks"] == 0

    def test_queued_tasks_after_delegation(self):
        """Agent has queued_tasks > 0 after delegation."""
        from src.activity_tracker import log_delegation, get_agent_status
        log_delegation("manager", "accountant", "Подготовить бюджет")
        status = get_agent_status("accountant")
        assert status["queued_tasks"] >= 1


class TestRecentEventsIncludesDelegation:
    """Tests that get_recent_events includes delegation events."""

    def test_delegation_in_recent_events(self):
        """Delegation events appear in get_recent_events."""
        from src.activity_tracker import log_delegation, get_recent_events
        log_delegation("manager", "accountant", "Test task")
        events = get_recent_events(hours=1)
        types = [e["type"] for e in events]
        assert "delegation" in types

    def test_delegation_after_task_events(self):
        """Delegation events are properly ordered with task events."""
        from src.activity_tracker import (
            log_task_start, log_task_end, log_delegation, get_recent_events,
        )
        log_task_start("manager", "Review")
        log_task_end("manager", "Review", success=True)
        log_delegation("manager", "accountant", "Budget")
        events = get_recent_events(hours=1)
        assert len(events) >= 3
        assert events[-1]["type"] == "delegation"


class TestMonitoringIntegration:
    """Integration tests: delegation → monitoring shows correct data."""

    def test_delegation_flow_updates_monitoring(self):
        """After delegation from Alexey to Matthias, monitoring shows task for Matthias."""
        from src.activity_tracker import (
            log_delegation, log_communication,
            get_agent_task_count, get_agent_status,
        )
        # Simulate: Alexey delegates to Matthias
        log_delegation("manager", "accountant", "Подготовить финансовый отчёт")
        log_communication("manager", "accountant", "Делегация задачи")

        # Check Matthias has tasks
        count = get_agent_task_count("accountant", hours=24)
        assert count >= 1

        # Check Matthias status shows queued_tasks
        status = get_agent_status("accountant")
        assert status["queued_tasks"] >= 1

    def test_multiple_delegations_accumulate(self):
        """Multiple delegations to same agent accumulate in count."""
        from src.activity_tracker import (
            log_delegation, get_agent_task_count,
        )
        log_delegation("manager", "accountant", "Task 1")
        log_delegation("automator", "accountant", "Task 2")

        count = get_agent_task_count("accountant", hours=24)
        assert count >= 2
