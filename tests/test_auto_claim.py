"""Tests for Auto-Claim — competing consumers with HITL approval gate."""

from unittest.mock import MagicMock, patch

import pytest

from src.event_bus import (
    Event, TASK_CREATED, TASK_APPROVAL_REQUIRED,
    get_event_bus, reset_event_bus,
)
from src.auto_claim import (
    CLAIM_CONFIDENCE_THRESHOLD,
    HITL_TAGS,
    _on_task_created,
    register_auto_claim,
    unregister_auto_claim,
)


@pytest.fixture(autouse=True)
def _clean_state():
    """Reset EventBus before each test."""
    reset_event_bus()
    yield
    reset_event_bus()


def _make_created_event(task_id="t1", title="Write post", assignee="",
                        tags=None, status="TODO"):
    return Event(TASK_CREATED, {
        "task_id": task_id,
        "title": title,
        "assignee": assignee,
        "tags": tags or [],
        "status": status,
        "source": "manual",
    })


# ── Registration ──


class TestRegistration:
    def test_register_subscribes(self):
        bus = get_event_bus()
        assert bus.subscriber_count(TASK_CREATED) == 0
        register_auto_claim()
        assert bus.subscriber_count(TASK_CREATED) == 1

    def test_unregister_removes(self):
        register_auto_claim()
        bus = get_event_bus()
        assert bus.subscriber_count(TASK_CREATED) == 1
        unregister_auto_claim()
        assert bus.subscriber_count(TASK_CREATED) == 0


# ── Auto-claim logic ──


class TestAutoClaim:
    @patch("src.task_pool.assign_task")
    @patch("src.task_pool.suggest_assignee", return_value=[("smm", 0.8)])
    def test_claims_when_no_assignee_high_confidence(self, mock_suggest, mock_assign):
        mock_assign.return_value = MagicMock()
        event = _make_created_event(tags=["content"])
        _on_task_created(event)
        mock_assign.assert_called_once_with("t1", "smm", assigned_by="auto-claim")

    def test_skips_when_already_assigned(self):
        event = _make_created_event(assignee="accountant")
        # Should not raise or call anything
        _on_task_created(event)

    def test_skips_when_blocked(self):
        event = _make_created_event(status="BLOCKED")
        _on_task_created(event)

    @patch("src.task_pool.suggest_assignee", return_value=[])
    def test_skips_when_no_match(self, mock_suggest):
        event = _make_created_event(tags=["unknown_tag"])
        _on_task_created(event)

    @patch("src.task_pool.suggest_assignee", return_value=[("smm", 0.3)])
    def test_skips_when_low_confidence(self, mock_suggest):
        event = _make_created_event(tags=["content"])
        _on_task_created(event)

    @patch("src.task_pool.assign_task")
    @patch("src.task_pool.suggest_assignee", return_value=[("smm", 0.8)])
    def test_assign_failure_handled(self, mock_suggest, mock_assign):
        mock_assign.return_value = None  # assign failed
        event = _make_created_event(tags=["content"])
        _on_task_created(event)  # should not raise


# ── HITL approval ──


class TestHITLApproval:
    @patch("src.task_pool.assign_task")
    @patch("src.task_pool.suggest_assignee", return_value=[("accountant", 0.9)])
    def test_hitl_tags_emit_approval(self, mock_suggest, mock_assign):
        mock_assign.return_value = MagicMock()
        received = []
        bus = get_event_bus()
        bus.on(TASK_APPROVAL_REQUIRED, lambda e: received.append(e))

        event = _make_created_event(tags=["finance", "revenue"])
        _on_task_created(event)

        mock_assign.assert_called_once()
        assert len(received) == 1
        assert received[0].payload["task_id"] == "t1"
        assert received[0].payload["assignee"] == "accountant"

    @patch("src.task_pool.assign_task")
    @patch("src.task_pool.suggest_assignee", return_value=[("smm", 0.8)])
    def test_non_hitl_tags_no_approval(self, mock_suggest, mock_assign):
        mock_assign.return_value = MagicMock()
        received = []
        bus = get_event_bus()
        bus.on(TASK_APPROVAL_REQUIRED, lambda e: received.append(e))

        event = _make_created_event(tags=["content", "social"])
        _on_task_created(event)

        mock_assign.assert_called_once()
        assert len(received) == 0  # no approval needed

    @patch("src.task_pool.assign_task")
    @patch("src.task_pool.suggest_assignee", return_value=[("smm", 0.8)])
    def test_publish_tag_requires_approval(self, mock_suggest, mock_assign):
        mock_assign.return_value = MagicMock()
        received = []
        bus = get_event_bus()
        bus.on(TASK_APPROVAL_REQUIRED, lambda e: received.append(e))

        event = _make_created_event(tags=["content", "publish"])
        _on_task_created(event)

        assert len(received) == 1

    @patch("src.task_pool.assign_task")
    @patch("src.task_pool.suggest_assignee", return_value=[("automator", 0.7)])
    def test_external_tag_requires_approval(self, mock_suggest, mock_assign):
        mock_assign.return_value = MagicMock()
        received = []
        bus = get_event_bus()
        bus.on(TASK_APPROVAL_REQUIRED, lambda e: received.append(e))

        event = _make_created_event(tags=["api", "external"])
        _on_task_created(event)

        assert len(received) == 1


# ── Constants ──


class TestConstants:
    def test_threshold_is_reasonable(self):
        assert 0.0 < CLAIM_CONFIDENCE_THRESHOLD < 1.0

    def test_hitl_tags_exist(self):
        assert "hitl" in HITL_TAGS
        assert "finance" in HITL_TAGS
        assert "publish" in HITL_TAGS
        assert "external" in HITL_TAGS
