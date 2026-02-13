"""Tests for Proactive Planner module."""

import time
import pytest
from unittest.mock import patch, MagicMock

from src.proactive_planner import (
    ActionItem,
    store_action,
    get_action,
    set_action_status,
    get_pending_actions,
    get_next_pending_action,
    get_actions_summary,
    cleanup_expired_actions,
    clear_all_actions,
    generate_morning_plan,
    generate_midday_check,
    generate_evening_review,
    format_morning_message,
    format_midday_message,
    format_evening_message,
    AGENT_METHOD_MAP,
    ACTION_TTL,
)


@pytest.fixture(autouse=True)
def clean_actions():
    """Clear action store before each test."""
    clear_all_actions()
    yield
    clear_all_actions()


class TestActionItem:
    """Test ActionItem dataclass."""

    def test_auto_generates_id(self):
        a = ActionItem(title="Test")
        assert a.id.startswith("act_")
        assert len(a.id) == 12  # "act_" + 8 hex chars

    def test_auto_generates_timestamp(self):
        a = ActionItem(title="Test")
        assert a.created_at > 0

    def test_default_status_pending(self):
        a = ActionItem(title="Test")
        assert a.status == "pending"

    def test_default_priority_medium(self):
        a = ActionItem(title="Test")
        assert a.priority == 3

    def test_custom_fields(self):
        a = ActionItem(
            title="Custom",
            target_agent="smm",
            agent_method="run_generate_post",
            method_kwargs={"topic": "AI"},
            priority=1,
            category="content",
        )
        assert a.target_agent == "smm"
        assert a.agent_method == "run_generate_post"
        assert a.method_kwargs == {"topic": "AI"}
        assert a.priority == 1
        assert a.category == "content"


class TestActionStore:
    """Test in-memory action store."""

    def test_store_and_get(self):
        a = ActionItem(title="Test")
        store_action(a)
        result = get_action(a.id)
        assert result is not None
        assert result.title == "Test"

    def test_get_nonexistent_returns_none(self):
        assert get_action("nonexistent") is None

    def test_set_action_status(self):
        a = ActionItem(title="Test")
        store_action(a)
        set_action_status(a.id, "completed")
        result = get_action(a.id)
        assert result.status == "completed"

    def test_set_status_idempotent(self):
        a = ActionItem(title="Test")
        store_action(a)
        set_action_status(a.id, "launched")
        set_action_status(a.id, "launched")
        assert get_action(a.id).status == "launched"

    def test_set_status_nonexistent_no_error(self):
        set_action_status("nope", "completed")  # Should not raise


class TestPendingActions:
    """Test pending action queries."""

    def test_get_pending_returns_only_pending(self):
        a1 = ActionItem(title="Pending", priority=2)
        a2 = ActionItem(title="Completed", priority=1)
        store_action(a1)
        store_action(a2)
        set_action_status(a2.id, "completed")
        pending = get_pending_actions()
        assert len(pending) == 1
        assert pending[0].title == "Pending"

    def test_pending_sorted_by_priority(self):
        a1 = ActionItem(title="Low", priority=4)
        a2 = ActionItem(title="High", priority=1)
        a3 = ActionItem(title="Med", priority=2)
        store_action(a1)
        store_action(a2)
        store_action(a3)
        pending = get_pending_actions()
        assert pending[0].title == "High"
        assert pending[1].title == "Med"
        assert pending[2].title == "Low"

    def test_get_next_pending(self):
        a1 = ActionItem(title="Low", priority=4)
        a2 = ActionItem(title="High", priority=1)
        store_action(a1)
        store_action(a2)
        result = get_next_pending_action()
        assert result.title == "High"

    def test_get_next_pending_empty(self):
        assert get_next_pending_action() is None


class TestActionsSummary:
    """Test get_actions_summary()."""

    def test_empty_summary(self):
        s = get_actions_summary()
        assert s["total"] == 0
        assert s["pending"] == 0

    def test_mixed_statuses(self):
        for title, status in [("A", "pending"), ("B", "completed"), ("C", "skipped"), ("D", "launched")]:
            a = ActionItem(title=title)
            store_action(a)
            set_action_status(a.id, status)
        s = get_actions_summary()
        assert s["total"] == 4
        assert s["pending"] == 1
        assert s["completed"] == 1
        assert s["skipped"] == 1
        assert s["launched"] == 1


class TestCleanupExpired:
    """Test TTL cleanup."""

    def test_removes_expired(self):
        a = ActionItem(title="Old")
        a.created_at = time.time() - ACTION_TTL - 1
        store_action(a)
        removed = cleanup_expired_actions()
        assert removed == 1
        assert get_action(a.id) is None

    def test_keeps_fresh(self):
        a = ActionItem(title="Fresh")
        store_action(a)
        removed = cleanup_expired_actions()
        assert removed == 0
        assert get_action(a.id) is not None

    def test_get_action_auto_removes_expired(self):
        a = ActionItem(title="Old")
        a.created_at = time.time() - ACTION_TTL - 1
        store_action(a)
        result = get_action(a.id)
        assert result is None


class TestGenerateMorningPlan:
    """Test morning plan generation with mocked dependencies."""

    def test_returns_list_of_actions(self):
        with patch("src.revenue_tracker.get_gap", return_value=500), \
             patch("src.revenue_tracker.get_days_left", return_value=10), \
             patch("src.revenue_tracker.format_revenue_summary", return_value=""), \
             patch("src.content_calendar.get_today", return_value=[]), \
             patch("src.content_calendar.get_overdue", return_value=[]), \
             patch("src.task_pool.get_tasks_by_status", return_value=[]):
            actions = generate_morning_plan()
        assert isinstance(actions, list)

    def test_adds_cfo_action_when_gap_high(self):
        with patch("src.revenue_tracker.get_gap", return_value=2000), \
             patch("src.revenue_tracker.get_days_left", return_value=10), \
             patch("src.revenue_tracker.format_revenue_summary", return_value=""), \
             patch("src.content_calendar.get_today", return_value=[]), \
             patch("src.content_calendar.get_overdue", return_value=[]), \
             patch("src.task_pool.get_tasks_by_status", return_value=[]):
            actions = generate_morning_plan()
        cfo_actions = [a for a in actions if a.target_agent == "accountant"]
        assert len(cfo_actions) >= 1

    def test_no_cfo_action_when_gap_low(self):
        with patch("src.revenue_tracker.get_gap", return_value=500), \
             patch("src.revenue_tracker.get_days_left", return_value=10), \
             patch("src.revenue_tracker.format_revenue_summary", return_value=""), \
             patch("src.content_calendar.get_today", return_value=[]), \
             patch("src.content_calendar.get_overdue", return_value=[]), \
             patch("src.task_pool.get_tasks_by_status", return_value=[]):
            actions = generate_morning_plan()
        cfo_actions = [a for a in actions if a.target_agent == "accountant"]
        assert len(cfo_actions) == 0

    def test_adds_content_actions_from_calendar(self):
        today_entries = [
            {"topic": "AI post", "author": "tim", "platform": "linkedin", "status": "planned"},
        ]
        with patch("src.revenue_tracker.get_gap", return_value=500), \
             patch("src.revenue_tracker.get_days_left", return_value=10), \
             patch("src.revenue_tracker.format_revenue_summary", return_value=""), \
             patch("src.content_calendar.get_today", return_value=today_entries), \
             patch("src.content_calendar.get_overdue", return_value=[]), \
             patch("src.task_pool.get_tasks_by_status", return_value=[]):
            actions = generate_morning_plan()
        content_actions = [a for a in actions if a.category == "content"]
        assert len(content_actions) >= 1

    def test_skips_done_calendar_entries(self):
        today_entries = [
            {"topic": "Done post", "author": "tim", "platform": "linkedin", "status": "done"},
        ]
        with patch("src.revenue_tracker.get_gap", return_value=500), \
             patch("src.revenue_tracker.get_days_left", return_value=10), \
             patch("src.revenue_tracker.format_revenue_summary", return_value=""), \
             patch("src.content_calendar.get_today", return_value=today_entries), \
             patch("src.content_calendar.get_overdue", return_value=[]), \
             patch("src.task_pool.get_tasks_by_status", return_value=[]):
            actions = generate_morning_plan()
        content_actions = [a for a in actions if a.category == "content"]
        assert len(content_actions) == 0

    def test_adds_overdue_actions(self):
        overdue = [
            {"topic": "Late post", "author": "kristina", "status": "planned"},
        ]
        with patch("src.revenue_tracker.get_gap", return_value=500), \
             patch("src.revenue_tracker.get_days_left", return_value=10), \
             patch("src.revenue_tracker.format_revenue_summary", return_value=""), \
             patch("src.content_calendar.get_today", return_value=[]), \
             patch("src.content_calendar.get_overdue", return_value=overdue), \
             patch("src.task_pool.get_tasks_by_status", return_value=[]):
            actions = generate_morning_plan()
        overdue_actions = [a for a in actions if "Просрочено" in a.title]
        assert len(overdue_actions) >= 1

    def test_adds_triage_action_when_many_todo(self):
        todo_tasks = [{"id": str(i)} for i in range(8)]
        with patch("src.revenue_tracker.get_gap", return_value=500), \
             patch("src.revenue_tracker.get_days_left", return_value=10), \
             patch("src.revenue_tracker.format_revenue_summary", return_value=""), \
             patch("src.content_calendar.get_today", return_value=[]), \
             patch("src.content_calendar.get_overdue", return_value=[]), \
             patch("src.task_pool.get_tasks_by_status", return_value=todo_tasks):
            actions = generate_morning_plan()
        triage = [a for a in actions if a.category == "ops"]
        assert len(triage) >= 1

    def test_caps_at_max_actions(self):
        # Create many overdue + today entries to exceed MAX
        overdue = [{"topic": f"Late {i}", "author": "tim"} for i in range(5)]
        today = [{"topic": f"Today {i}", "author": "tim", "platform": "linkedin", "status": "planned"} for i in range(5)]
        with patch("src.revenue_tracker.get_gap", return_value=2000), \
             patch("src.revenue_tracker.get_days_left", return_value=5), \
             patch("src.revenue_tracker.format_revenue_summary", return_value=""), \
             patch("src.content_calendar.get_today", return_value=today), \
             patch("src.content_calendar.get_overdue", return_value=overdue), \
             patch("src.task_pool.get_tasks_by_status", return_value=[{"id": str(i)} for i in range(10)]):
            actions = generate_morning_plan()
        assert len(actions) <= 5

    def test_actions_stored_in_store(self):
        with patch("src.revenue_tracker.get_gap", return_value=2000), \
             patch("src.revenue_tracker.get_days_left", return_value=10), \
             patch("src.revenue_tracker.format_revenue_summary", return_value=""), \
             patch("src.content_calendar.get_today", return_value=[]), \
             patch("src.content_calendar.get_overdue", return_value=[]), \
             patch("src.task_pool.get_tasks_by_status", return_value=[]):
            actions = generate_morning_plan()
        for action in actions:
            assert get_action(action.id) is not None

    def test_handles_all_exceptions_gracefully(self):
        with patch("src.revenue_tracker.get_gap", side_effect=ImportError), \
             patch("src.content_calendar.get_today", side_effect=ImportError), \
             patch("src.content_calendar.get_overdue", side_effect=ImportError), \
             patch("src.task_pool.get_tasks_by_status", side_effect=ImportError):
            actions = generate_morning_plan()
        assert isinstance(actions, list)


class TestGenerateMiddayCheck:
    """Test midday check generation."""

    def test_returns_list(self):
        actions = generate_midday_check()
        assert isinstance(actions, list)

    def test_reminds_pending_content(self):
        a = ActionItem(title="Write post", category="content", target_agent="smm",
                       agent_method="run_generate_post", method_kwargs={"topic": "AI"})
        store_action(a)
        result = generate_midday_check()
        assert len(result) >= 1
        assert "Напоминание" in result[0].title

    def test_caps_at_max(self):
        for i in range(5):
            a = ActionItem(title=f"Content {i}", category="content", target_agent="smm",
                           agent_method="run_generate_post", method_kwargs={})
            store_action(a)
        result = generate_midday_check()
        assert len(result) <= 2

    def test_revenue_fallback_when_no_pending(self):
        with patch("src.revenue_tracker.get_gap", return_value=2000):
            result = generate_midday_check()
        revenue_actions = [a for a in result if a.category == "revenue"]
        assert len(revenue_actions) >= 1


class TestGenerateEveningReview:
    """Test evening review generation."""

    def test_returns_tuple(self):
        summary, tomorrow = generate_evening_review()
        assert isinstance(summary, str)
        assert isinstance(tomorrow, list)

    def test_summary_contains_stats(self):
        a1 = ActionItem(title="A")
        a2 = ActionItem(title="B")
        store_action(a1)
        store_action(a2)
        set_action_status(a1.id, "completed")
        set_action_status(a2.id, "skipped")
        summary, _ = generate_evening_review()
        assert "1" in summary  # completed count
        assert "Итоги" in summary

    def test_summary_includes_revenue(self):
        with patch("src.revenue_tracker.get_revenue_summary", return_value={
            "total_mrr": 515, "target_mrr": 2500, "gap": 1985, "days_left": 17
        }):
            summary, _ = generate_evening_review()
        assert "MRR" in summary

    def test_tomorrow_from_calendar(self):
        from datetime import date, timedelta
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        entries = [{"topic": "Tomorrow post", "author": "tim"}]
        with patch("src.content_calendar.get_date", return_value=entries):
            _, tomorrow_actions = generate_evening_review()
        assert len(tomorrow_actions) >= 1


class TestFormatMessages:
    """Test Telegram message formatters."""

    def test_format_morning_empty(self):
        msg = format_morning_message([])
        assert "нет запланированных" in msg

    def test_format_morning_with_actions(self):
        actions = [ActionItem(title="Test action", priority=1)]
        with patch("src.revenue_tracker.format_revenue_summary", return_value="Revenue: $515"):
            msg = format_morning_message(actions)
        assert "Утренний план" in msg
        assert "Test action" in msg

    def test_format_midday(self):
        actions = [ActionItem(title="Midday task")]
        msg = format_midday_message(actions)
        assert "Дневная проверка" in msg
        assert "Midday task" in msg

    def test_format_evening(self):
        summary = "Итоги дня\nВыполнено: 3/5"
        tomorrow = [ActionItem(title="Tomorrow task")]
        msg = format_evening_message(summary, tomorrow)
        assert "Tomorrow task" in msg
        assert "Завтра" in msg

    def test_format_evening_no_tomorrow(self):
        msg = format_evening_message("Summary", [])
        assert "Summary" in msg
        assert "Завтра" not in msg


class TestAgentMethodMap:
    """Test AGENT_METHOD_MAP."""

    def test_contains_key_methods(self):
        assert "run_generate_post" in AGENT_METHOD_MAP
        assert "run_financial_report" in AGENT_METHOD_MAP
        assert "send_to_agent" in AGENT_METHOD_MAP

    def test_all_values_are_strings(self):
        for k, v in AGENT_METHOD_MAP.items():
            assert isinstance(v, str)
