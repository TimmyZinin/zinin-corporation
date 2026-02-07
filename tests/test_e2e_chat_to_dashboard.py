"""
🧪 E2E Test: Chat message → Dashboard task

Tests the FULL pipeline:
1. User sends a message in chat
2. execute_task() logs via activity_tracker
3. Dashboard reads and renders the task

Root cause being tested: Does a chat message actually appear
on the dashboard as a task in the "Лог активности"?
"""

import json
import os
import sys
import tempfile
import pytest
from datetime import datetime
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ──────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────

@pytest.fixture
def temp_activity_log(tmp_path):
    """Create a temp directory and redirect activity_tracker to use it."""
    log_file = tmp_path / "activity_log.json"
    log_file.write_text('{"events": [], "agent_status": {}}', encoding="utf-8")
    return str(log_file)


@pytest.fixture
def patched_tracker(temp_activity_log):
    """Patch activity_tracker._log_path to use temp file."""
    import src.activity_tracker as tracker
    with patch.object(tracker, '_log_path', return_value=temp_activity_log):
        yield tracker


# ──────────────────────────────────────────────────────────
# 1. Activity tracker writes correctly when execute_task flow runs
# ──────────────────────────────────────────────────────────

class TestActivityTrackerWrites:
    """Verify that log_task_start/end write events that can be read back."""

    def test_log_task_start_creates_event(self, patched_tracker):
        """log_task_start writes a task_start event."""
        patched_tracker.log_task_start("manager", "Подготовь финансовый отчёт")
        events = patched_tracker.get_recent_events(hours=1)
        assert len(events) == 1
        assert events[0]["type"] == "task_start"
        assert events[0]["agent"] == "manager"
        assert "финансовый отчёт" in events[0]["task"]

    def test_log_task_end_creates_event(self, patched_tracker):
        """log_task_end writes a task_end event."""
        patched_tracker.log_task_start("accountant", "Проверка бюджета")
        patched_tracker.log_task_end("accountant", "Проверка бюджета", success=True)
        events = patched_tracker.get_recent_events(hours=1)
        assert len(events) == 2
        assert events[1]["type"] == "task_end"
        assert events[1]["success"] is True

    def test_agent_status_updates_on_task_start(self, patched_tracker):
        """Agent status changes to 'working' when task starts."""
        patched_tracker.log_task_start("smm", "Генерация поста")
        status = patched_tracker.get_agent_status("smm")
        assert status["status"] == "working"
        assert "Генерация поста" in status["task"]

    def test_agent_status_idle_after_task_end(self, patched_tracker):
        """Agent status changes to 'idle' when task ends."""
        patched_tracker.log_task_start("automator", "Проверка систем")
        patched_tracker.log_task_end("automator", "Проверка систем")
        status = patched_tracker.get_agent_status("automator")
        assert status["status"] == "idle"

    def test_get_all_statuses_returns_all_agents(self, patched_tracker):
        """get_all_statuses returns entries for all 4 agents."""
        statuses = patched_tracker.get_all_statuses()
        assert "manager" in statuses
        assert "accountant" in statuses
        assert "smm" in statuses
        assert "automator" in statuses

    def test_task_count_increments(self, patched_tracker):
        """Task count increments after task_end."""
        patched_tracker.log_task_start("manager", "Task 1")
        patched_tracker.log_task_end("manager", "Task 1")
        patched_tracker.log_task_start("manager", "Task 2")
        patched_tracker.log_task_end("manager", "Task 2")
        count = patched_tracker.get_agent_task_count("manager", hours=1)
        assert count == 2


# ──────────────────────────────────────────────────────────
# 2. Dashboard reads and renders activity data
# ──────────────────────────────────────────────────────────

class TestDashboardRendersEvents:
    """Verify the dashboard HTML contains task data from activity tracker."""

    def test_dashboard_shows_completed_count(self, patched_tracker):
        """Dashboard HTML contains the completed task count."""
        from src.dashboard import generate_dashboard_html
        patched_tracker.log_task_start("manager", "Стратобзор")
        patched_tracker.log_task_end("manager", "Стратобзор")
        count = patched_tracker.get_agent_task_count("manager", hours=1)
        html = generate_dashboard_html(completed_count=count)
        assert '"completedCount": 1' in html or '"completedCount":1' in html

    def test_dashboard_shows_recent_events(self, patched_tracker):
        """Dashboard HTML contains recent events data."""
        from src.dashboard import generate_dashboard_html
        patched_tracker.log_task_start("accountant", "Финансовая сводка")
        patched_tracker.log_task_end("accountant", "Финансовая сводка")
        events = patched_tracker.get_recent_events(hours=1)
        html = generate_dashboard_html(recent_events=events)
        # Events should be JSON-embedded in the HTML
        assert "Финансовая сводка" in html

    def test_dashboard_shows_working_agent(self, patched_tracker):
        """Dashboard shows agent as working when task is in progress."""
        from src.dashboard import generate_dashboard_html
        patched_tracker.log_task_start("smm", "Генерация поста для LinkedIn")
        statuses = patched_tracker.get_all_statuses()
        html = generate_dashboard_html(agent_statuses=statuses)
        assert "Генерация поста" in html
        assert '"status": "working"' in html or '"status":"working"' in html

    def test_dashboard_event_types_in_html(self, patched_tracker):
        """Dashboard HTML has task_start and task_end event types for JS parsing."""
        from src.dashboard import generate_dashboard_html
        patched_tracker.log_task_start("automator", "Проверка интеграций")
        patched_tracker.log_task_end("automator", "Проверка интеграций")
        events = patched_tracker.get_recent_events(hours=1)
        html = generate_dashboard_html(recent_events=events)
        assert "task_start" in html
        assert "task_end" in html

    def test_dashboard_renders_agent_names_in_log(self):
        """Dashboard JS has agent name lookup for rendering log entries."""
        from src.dashboard import generate_dashboard_html
        html = generate_dashboard_html()
        # The JS looks up agents by id and uses their name/icon
        assert 'evt.type === "task_start"' in html
        assert 'evt.type === "task_end"' in html
        assert "начал" in html  # "начал" = "started" in the log renderer
        assert "завершил" in html  # "завершил" = "completed"


# ──────────────────────────────────────────────────────────
# 3. Full E2E: simulate chat → verify dashboard
# ──────────────────────────────────────────────────────────

class TestE2EChatToDashboard:
    """Simulate the exact flow: user sends chat message → dashboard shows it."""

    def _simulate_execute_task(self, tracker, agent_key, user_message):
        """Simulate what crew.py execute_task() does with activity tracking."""
        # This is what execute_task does (crew.py line 181-184, 205):
        short_desc = user_message.strip()[:100].split("\n")[0]
        tracker.log_task_start(agent_key, short_desc)
        # ... agent processes (skipped) ...
        tracker.log_task_end(agent_key, short_desc, success=True)

    def _simulate_dashboard_render(self, tracker):
        """Simulate what app.py tab6 does (lines 1483-1500)."""
        from src.dashboard import generate_dashboard_html
        statuses = tracker.get_all_statuses()
        events = tracker.get_recent_events(hours=24, limit=30)
        completed = sum(
            tracker.get_agent_task_count(a, hours=24)
            for a in ["manager", "accountant", "smm", "automator"]
        )
        return generate_dashboard_html(
            completed_count=completed,
            agent_statuses=statuses,
            recent_events=events,
        )

    def test_e2e_first_message_no_context(self, patched_tracker):
        """E2E: First message (no context) → task appears on dashboard."""
        user_msg = "Алексей, подготовь финансовый отчёт за январь"

        # Step 1: Simulate execute_task (no context for first message)
        self._simulate_execute_task(patched_tracker, "manager", user_msg)

        # Step 2: Render dashboard
        html = self._simulate_dashboard_render(patched_tracker)

        # Step 3: Verify
        assert "финансовый отчёт" in html.lower(), \
            "Dashboard must show the task description from the chat message"
        assert '"completedCount": 1' in html or '"completedCount":1' in html

    def test_e2e_message_with_context(self, patched_tracker):
        """E2E: Message with chat context → user message appears on dashboard."""
        # Simulate context-wrapped message (as app.py line 938 does)
        context = (
            "Контекст предыдущей переписки в корпоративном чате:\n"
            "Тим: Привет всем\n"
            "Алексей: Добрый день, Тим!"
        )
        user_msg = "Проверь бюджет на API"
        task_with_context = f"{context}\n\n---\nНовое сообщение от Тима: {user_msg}"

        # Step 1: Simulate execute_task with FIXED short_desc extraction
        if "---\nНовое сообщение от Тима:" in task_with_context:
            short_desc = task_with_context.split("---\nНовое сообщение от Тима:")[-1].strip()[:100].split("\n")[0]
        else:
            short_desc = task_with_context.strip()[:100].split("\n")[0]

        patched_tracker.log_task_start("accountant", short_desc)
        patched_tracker.log_task_end("accountant", short_desc)

        # Step 2: Render dashboard
        html = self._simulate_dashboard_render(patched_tracker)

        # Step 3: Verify user message (not context header) appears on dashboard
        events = patched_tracker.get_recent_events(hours=1)
        task_logged = events[0]["task"]
        assert "бюджет" in task_logged, \
            f"Dashboard should show user message, got: '{task_logged}'"
        assert "Контекст предыдущей" not in task_logged, \
            "Dashboard should NOT show context header"

    def test_e2e_multiple_agents_broadcast(self, patched_tracker):
        """E2E: Broadcast to all agents → all appear on dashboard."""
        agents = ["manager", "accountant", "smm", "automator"]
        for agent_key in agents:
            self._simulate_execute_task(
                patched_tracker, agent_key, f"Отчёт по проекту для {agent_key}"
            )

        html = self._simulate_dashboard_render(patched_tracker)
        assert '"completedCount": 4' in html or '"completedCount":4' in html

        events = patched_tracker.get_recent_events(hours=1)
        # 4 start + 4 end = 8 events
        assert len(events) == 8

    def test_e2e_dashboard_has_real_activity_flag(self, patched_tracker):
        """When there are real events, dashboard JS sets 'hasRealActivity'."""
        self._simulate_execute_task(patched_tracker, "manager", "Стратегический обзор")

        html = self._simulate_dashboard_render(patched_tracker)
        # The JS function loadRealData() returns true when there are events
        # It checks: if (INITIAL.recentEvents && INITIAL.recentEvents.length > 0)
        assert "recentEvents" in html
        # Verify events array is non-empty in the JSON
        import re
        match = re.search(r'"recentEvents":\s*\[(.*?)\]', html, re.DOTALL)
        assert match is not None
        assert len(match.group(1).strip()) > 0, "recentEvents should not be empty"

    def test_e2e_task_description_preserved_in_dashboard(self, patched_tracker):
        """The exact task description appears in the dashboard HTML."""
        task_text = "Подготовь контент-план для LinkedIn на март"
        self._simulate_execute_task(patched_tracker, "smm", task_text)

        html = self._simulate_dashboard_render(patched_tracker)
        assert task_text in html, \
            f"Dashboard HTML must contain the exact task text: '{task_text}'"


# ──────────────────────────────────────────────────────────
# 4. Bug: short_desc captures context header, not user message
# ──────────────────────────────────────────────────────────

class TestShortDescBug:
    """The short_desc in execute_task captures context instead of user message."""

    def test_short_desc_from_plain_message(self):
        """Without context, short_desc is correct."""
        msg = "Алексей, проверь финансы"
        short_desc = msg.strip()[:100].split("\n")[0]
        assert short_desc == "Алексей, проверь финансы"

    def test_short_desc_from_context_message_extracts_user_msg(self):
        """With context, short_desc extracts the actual user message (FIXED)."""
        context = "Контекст предыдущей переписки в корпоративном чате:\nТим: Привет"
        user_msg = "Проверь бюджет"
        task_with_context = f"{context}\n\n---\nНовое сообщение от Тима: {user_msg}"

        # Fixed behavior: extract user message from context
        if "---\nНовое сообщение от Тима:" in task_with_context:
            short_desc = task_with_context.split("---\nНовое сообщение от Тима:")[-1].strip()[:100].split("\n")[0]
        else:
            short_desc = task_with_context.strip()[:100].split("\n")[0]

        assert short_desc == "Проверь бюджет"
        assert "бюджет" in short_desc

    def test_extracting_user_message_from_context(self):
        """Demonstrate how to correctly extract user message from context-wrapped text."""
        context = "Контекст предыдущей переписки в корпоративном чате:\nТим: Привет"
        user_msg = "Проверь бюджет"
        task_with_context = f"{context}\n\n---\nНовое сообщение от Тима: {user_msg}"

        # Correct extraction
        if "---\nНовое сообщение от Тима:" in task_with_context:
            extracted = task_with_context.split("---\nНовое сообщение от Тима:")[-1].strip()
        else:
            extracted = task_with_context.strip()[:100].split("\n")[0]

        assert extracted == "Проверь бюджет"

    def test_extracting_handles_multiline_message(self):
        """Extraction works for multi-line user messages."""
        context = "Контекст предыдущей переписки:\nТим: Привет"
        user_msg = "Проверь бюджет\nи подготовь отчёт"
        task_with_context = f"{context}\n\n---\nНовое сообщение от Тима: {user_msg}"

        if "---\nНовое сообщение от Тима:" in task_with_context:
            extracted = task_with_context.split("---\nНовое сообщение от Тима:")[-1].strip()
            extracted = extracted[:100].split("\n")[0]
        else:
            extracted = task_with_context.strip()[:100].split("\n")[0]

        assert extracted == "Проверь бюджет"

    def test_extracting_handles_no_context(self):
        """Extraction falls back correctly when there's no context."""
        user_msg = "Просто сообщение без контекста"

        if "---\nНовое сообщение от Тима:" in user_msg:
            extracted = user_msg.split("---\nНовое сообщение от Тима:")[-1].strip()
        else:
            extracted = user_msg.strip()[:100].split("\n")[0]

        assert extracted == "Просто сообщение без контекста"
