"""Tests for CTO → CEO feedback — Round 2.

Verifies fixes work correctly + deeper edge cases + regression testing.
"""

import json
import os
import tempfile
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.telegram_ceo.callback_factory import CtoCB


# ──────────────────────────────────────────────────────────
# Helpers (same as round 1)
# ──────────────────────────────────────────────────────────

def _make_proposals_data(proposals=None):
    return {
        "proposals": proposals or [],
        "stats": {"total_generated": 0, "approved": 0, "rejected": 0, "conditions": 0},
        "last_run": None,
    }


def _make_proposal(proposal_id="prop_test_001", status="pending", target_agent="yuki"):
    return {
        "id": proposal_id,
        "created_at": "2026-02-08T15:30:00",
        "target_agent": target_agent,
        "proposal_type": "prompt",
        "title": "Улучшить goal для Юки",
        "description": "Описание улучшения",
        "current_state": "Текущее состояние",
        "proposed_change": "Предлагаемое изменение",
        "confidence_score": 0.85,
        "status": status,
        "conditions": "",
        "reviewed_at": None,
    }


def _make_callback_query(callback_data: str, user_id: int = 123):
    callback = AsyncMock()
    callback.data = callback_data
    callback.from_user = MagicMock()
    callback.from_user.id = user_id
    callback.message = AsyncMock()
    callback.message.edit_text = AsyncMock()
    callback.message.edit_reply_markup = AsyncMock()
    callback.message.text = "Original message text"
    callback.answer = AsyncMock()
    return callback


# ──────────────────────────────────────────────────────────
# Test: reply_markup=None is explicitly passed (verify fix #1)
# ──────────────────────────────────────────────────────────

class TestReplyMarkupRemoval:
    """Verify that keyboard buttons are removed after approve/reject/conditions."""

    @pytest.mark.asyncio
    async def test_approve_passes_reply_markup_none(self):
        from src.telegram_ceo.handlers.callbacks import on_cto_approve

        proposal = _make_proposal("p1")
        callback = _make_callback_query("cto_approve:p1")

        with patch(
            "src.telegram_ceo.handlers.callbacks._find_and_update_proposal",
            return_value=proposal,
        ):
            await on_cto_approve(callback, CtoCB(action="approve", id="p1"))

        _, kwargs = callback.message.edit_text.call_args
        assert "reply_markup" in kwargs
        assert kwargs["reply_markup"] is None

    @pytest.mark.asyncio
    async def test_reject_passes_reply_markup_none(self):
        from src.telegram_ceo.handlers.callbacks import on_cto_reject

        proposal = _make_proposal("p1")
        callback = _make_callback_query("cto_reject:p1")

        with patch(
            "src.telegram_ceo.handlers.callbacks._find_and_update_proposal",
            return_value=proposal,
        ):
            await on_cto_reject(callback, CtoCB(action="reject", id="p1"))

        _, kwargs = callback.message.edit_text.call_args
        assert "reply_markup" in kwargs
        assert kwargs["reply_markup"] is None

    @pytest.mark.asyncio
    async def test_conditions_passes_reply_markup_none(self):
        from src.telegram_ceo.handlers.callbacks import on_cto_conditions, _conditions_state

        proposal = _make_proposal("p1")
        data = _make_proposals_data([proposal])
        callback = _make_callback_query("cto_conditions:p1", user_id=888)

        with patch("src.tools.improvement_advisor._load_proposals", return_value=data):
            await on_cto_conditions(callback, CtoCB(action="conditions", id="p1"))

        _, kwargs = callback.message.edit_text.call_args
        assert "reply_markup" in kwargs
        assert kwargs["reply_markup"] is None
        # Cleanup
        _conditions_state.pop(888, None)

    @pytest.mark.asyncio
    async def test_detail_keeps_keyboard(self):
        """Detail view should KEEP the keyboard for further actions."""
        from src.telegram_ceo.handlers.callbacks import on_cto_detail

        proposal = _make_proposal("p1")
        data = _make_proposals_data([proposal])
        callback = _make_callback_query("cto_detail:p1")

        with patch("src.tools.improvement_advisor._load_proposals", return_value=data):
            await on_cto_detail(callback, CtoCB(action="detail", id="p1"))

        _, kwargs = callback.message.edit_text.call_args
        assert "reply_markup" in kwargs
        assert kwargs["reply_markup"] is not None


# ──────────────────────────────────────────────────────────
# Test: Error handling — callback.answer always called (verify fix #2)
# ──────────────────────────────────────────────────────────

class TestErrorHandling:
    """Verify callback.answer() is always called even when edit_text fails."""

    @pytest.mark.asyncio
    async def test_approve_answer_called_on_edit_error(self):
        from src.telegram_ceo.handlers.callbacks import on_cto_approve

        proposal = _make_proposal("p1")
        callback = _make_callback_query("cto_approve:p1")
        callback.message.edit_text = AsyncMock(
            side_effect=Exception("Bad Request: message is not modified")
        )

        with patch(
            "src.telegram_ceo.handlers.callbacks._find_and_update_proposal",
            return_value=proposal,
        ):
            await on_cto_approve(callback, CtoCB(action="approve", id="p1"))

        callback.answer.assert_called_once_with("Одобрено! Применяю...")

    @pytest.mark.asyncio
    async def test_reject_answer_called_on_edit_error(self):
        from src.telegram_ceo.handlers.callbacks import on_cto_reject

        proposal = _make_proposal("p1")
        callback = _make_callback_query("cto_reject:p1")
        callback.message.edit_text = AsyncMock(
            side_effect=Exception("Bad Request: message is not modified")
        )

        with patch(
            "src.telegram_ceo.handlers.callbacks._find_and_update_proposal",
            return_value=proposal,
        ):
            await on_cto_reject(callback, CtoCB(action="reject", id="p1"))

        callback.answer.assert_called_once_with("Отклонено")

    @pytest.mark.asyncio
    async def test_conditions_answer_called_on_edit_error(self):
        from src.telegram_ceo.handlers.callbacks import on_cto_conditions, _conditions_state

        proposal = _make_proposal("p1")
        data = _make_proposals_data([proposal])
        callback = _make_callback_query("cto_conditions:p1", user_id=889)
        callback.message.edit_text = AsyncMock(
            side_effect=Exception("Bad Request: message is not modified")
        )

        with patch("src.tools.improvement_advisor._load_proposals", return_value=data):
            await on_cto_conditions(callback, CtoCB(action="conditions", id="p1"))

        callback.answer.assert_called_once()
        _conditions_state.pop(889, None)

    @pytest.mark.asyncio
    async def test_detail_error_handling(self):
        """FIX: on_cto_detail now handles edit_text errors."""
        from src.telegram_ceo.handlers.callbacks import on_cto_detail

        proposal = _make_proposal("p1")
        data = _make_proposals_data([proposal])
        callback = _make_callback_query("cto_detail:p1")
        callback.message.edit_text = AsyncMock(
            side_effect=Exception("Bad Request: message is not modified")
        )

        with patch("src.tools.improvement_advisor._load_proposals", return_value=data):
            # Should NOT raise — error is caught
            await on_cto_detail(callback, CtoCB(action="detail", id="p1"))

        callback.answer.assert_called_once()


# ──────────────────────────────────────────────────────────
# Test: Stats double-counting prevention (verify fix #3)
# ──────────────────────────────────────────────────────────

class TestStatsProtection:
    """Verify stats are only incremented on actual status changes."""

    def test_pending_to_approved_increments(self):
        from src.telegram_ceo.handlers.callbacks import _find_and_update_proposal

        data = _make_proposals_data([_make_proposal("p1", status="pending")])
        saved = {}

        with patch("src.tools.improvement_advisor._load_proposals", return_value=data):
            with patch("src.tools.improvement_advisor._save_proposals", side_effect=lambda d: saved.update(d)):
                _find_and_update_proposal("p1", {"status": "approved"})
                assert saved["stats"]["approved"] == 1

    def test_approved_to_approved_does_not_increment(self):
        from src.telegram_ceo.handlers.callbacks import _find_and_update_proposal

        data = _make_proposals_data([_make_proposal("p1", status="approved")])
        data["stats"]["approved"] = 3
        saved = {}

        with patch("src.tools.improvement_advisor._load_proposals", return_value=data):
            with patch("src.tools.improvement_advisor._save_proposals", side_effect=lambda d: saved.update(d)):
                _find_and_update_proposal("p1", {"status": "approved"})
                assert saved["stats"]["approved"] == 3  # unchanged

    def test_rejected_to_rejected_does_not_increment(self):
        from src.telegram_ceo.handlers.callbacks import _find_and_update_proposal

        data = _make_proposals_data([_make_proposal("p1", status="rejected")])
        data["stats"]["rejected"] = 2
        saved = {}

        with patch("src.tools.improvement_advisor._load_proposals", return_value=data):
            with patch("src.tools.improvement_advisor._save_proposals", side_effect=lambda d: saved.update(d)):
                _find_and_update_proposal("p1", {"status": "rejected"})
                assert saved["stats"]["rejected"] == 2  # unchanged

    def test_pending_to_rejected_increments(self):
        from src.telegram_ceo.handlers.callbacks import _find_and_update_proposal

        data = _make_proposals_data([_make_proposal("p1", status="pending")])
        saved = {}

        with patch("src.tools.improvement_advisor._load_proposals", return_value=data):
            with patch("src.tools.improvement_advisor._save_proposals", side_effect=lambda d: saved.update(d)):
                _find_and_update_proposal("p1", {"status": "rejected"})
                assert saved["stats"]["rejected"] == 1

    def test_approved_to_rejected_increments_rejected(self):
        """Changing from approved to rejected should increment rejected."""
        from src.telegram_ceo.handlers.callbacks import _find_and_update_proposal

        data = _make_proposals_data([_make_proposal("p1", status="approved")])
        data["stats"]["approved"] = 1
        data["stats"]["rejected"] = 0
        saved = {}

        with patch("src.tools.improvement_advisor._load_proposals", return_value=data):
            with patch("src.tools.improvement_advisor._save_proposals", side_effect=lambda d: saved.update(d)):
                _find_and_update_proposal("p1", {"status": "rejected"})
                # Should increment rejected but NOT decrement approved
                assert saved["stats"]["rejected"] == 1
                assert saved["stats"]["approved"] == 1

    def test_conditions_to_approved_increments(self):
        from src.telegram_ceo.handlers.callbacks import _find_and_update_proposal

        data = _make_proposals_data([_make_proposal("p1", status="conditions")])
        saved = {}

        with patch("src.tools.improvement_advisor._load_proposals", return_value=data):
            with patch("src.tools.improvement_advisor._save_proposals", side_effect=lambda d: saved.update(d)):
                _find_and_update_proposal("p1", {"status": "approved"})
                assert saved["stats"]["approved"] == 1


# ──────────────────────────────────────────────────────────
# Test: Status transitions
# ──────────────────────────────────────────────────────────

class TestStatusTransitions:
    """Test all valid status transitions."""

    def test_pending_to_conditions(self):
        from src.telegram_ceo.handlers.callbacks import _find_and_update_proposal

        data = _make_proposals_data([_make_proposal("p1", status="pending")])
        with patch("src.tools.improvement_advisor._load_proposals", return_value=data):
            with patch("src.tools.improvement_advisor._save_proposals"):
                result = _find_and_update_proposal(
                    "p1", {"status": "conditions", "conditions": "Только после тестов"}
                )
                assert result["status"] == "conditions"
                assert result["conditions"] == "Только после тестов"

    def test_conditions_text_preserved(self):
        from src.telegram_ceo.handlers.callbacks import _find_and_update_proposal

        data = _make_proposals_data([_make_proposal("p1", status="pending")])
        saved = {}

        with patch("src.tools.improvement_advisor._load_proposals", return_value=data):
            with patch("src.tools.improvement_advisor._save_proposals", side_effect=lambda d: saved.update(d)):
                _find_and_update_proposal(
                    "p1", {"status": "conditions", "conditions": "Test conditions text"}
                )
                p = saved["proposals"][0]
                assert p["conditions"] == "Test conditions text"

    def test_update_without_status_does_not_change_stats(self):
        from src.telegram_ceo.handlers.callbacks import _find_and_update_proposal

        data = _make_proposals_data([_make_proposal("p1")])
        saved = {}

        with patch("src.tools.improvement_advisor._load_proposals", return_value=data):
            with patch("src.tools.improvement_advisor._save_proposals", side_effect=lambda d: saved.update(d)):
                _find_and_update_proposal("p1", {"conditions": "Some text"})
                assert saved["stats"]["approved"] == 0
                assert saved["stats"]["rejected"] == 0


# ──────────────────────────────────────────────────────────
# Test: Full roundtrip with file I/O (verify fix persists)
# ──────────────────────────────────────────────────────────

class TestFullRoundtripFixed:
    """Test that fixes work end-to-end with actual file operations."""

    def test_approve_then_double_approve_stats_correct(self):
        """Stats should be 1 after approve, then still 1 after double-approve."""
        from src.tools.improvement_advisor import _save_proposals, _load_proposals
        from src.telegram_ceo.handlers.callbacks import _find_and_update_proposal

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "cto_proposals.json")
            with patch("src.tools.improvement_advisor._proposals_path", return_value=path):
                data = _make_proposals_data([_make_proposal("p1")])
                _save_proposals(data)

                # First approve
                _find_and_update_proposal("p1", {"status": "approved"})
                loaded = _load_proposals()
                assert loaded["stats"]["approved"] == 1

                # Double approve — stats should NOT change
                _find_and_update_proposal("p1", {"status": "approved"})
                loaded = _load_proposals()
                assert loaded["stats"]["approved"] == 1  # Still 1, not 2

    def test_approve_then_reject_stats_correct(self):
        from src.tools.improvement_advisor import _save_proposals, _load_proposals
        from src.telegram_ceo.handlers.callbacks import _find_and_update_proposal

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "cto_proposals.json")
            with patch("src.tools.improvement_advisor._proposals_path", return_value=path):
                data = _make_proposals_data([_make_proposal("p1")])
                _save_proposals(data)

                # Approve first
                _find_and_update_proposal("p1", {"status": "approved"})
                loaded = _load_proposals()
                assert loaded["stats"]["approved"] == 1

                # Then reject (changing mind)
                _find_and_update_proposal("p1", {"status": "rejected"})
                loaded = _load_proposals()
                assert loaded["stats"]["approved"] == 1  # unchanged
                assert loaded["stats"]["rejected"] == 1  # incremented

    def test_multiple_proposals_independent_updates(self):
        from src.tools.improvement_advisor import _save_proposals, _load_proposals
        from src.telegram_ceo.handlers.callbacks import _find_and_update_proposal

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "cto_proposals.json")
            with patch("src.tools.improvement_advisor._proposals_path", return_value=path):
                data = _make_proposals_data([
                    _make_proposal("p1", target_agent="yuki"),
                    _make_proposal("p2", target_agent="accountant"),
                ])
                _save_proposals(data)

                _find_and_update_proposal("p1", {"status": "approved"})
                _find_and_update_proposal("p2", {"status": "rejected"})

                loaded = _load_proposals()
                assert loaded["proposals"][0]["status"] == "approved"
                assert loaded["proposals"][1]["status"] == "rejected"
                assert loaded["stats"]["approved"] == 1
                assert loaded["stats"]["rejected"] == 1


# ──────────────────────────────────────────────────────────
# Test: Conditions text entry via message handler
# ──────────────────────────────────────────────────────────

class TestConditionsViaMessage:
    """Test the conditions text entry flow (from messages.py)."""

    @pytest.mark.asyncio
    async def test_conditions_message_saves_text(self):
        from src.telegram_ceo.handlers.callbacks import (
            _conditions_state,
            _find_and_update_proposal,
        )

        proposal = _make_proposal("p1")
        _conditions_state[777] = "p1"

        with patch(
            "src.telegram_ceo.handlers.callbacks._find_and_update_proposal",
            return_value={**proposal, "status": "conditions", "conditions": "Do X"},
        ) as mock_update:
            # Simulate what messages.py does
            from src.telegram_ceo.handlers.callbacks import (
                is_in_conditions_mode,
                get_conditions_proposal_id,
            )

            assert is_in_conditions_mode(777)
            pid = get_conditions_proposal_id(777)
            assert pid == "p1"
            assert not is_in_conditions_mode(777)

    @pytest.mark.asyncio
    async def test_conditions_state_cleared_after_get(self):
        from src.telegram_ceo.handlers.callbacks import (
            _conditions_state,
            is_in_conditions_mode,
            get_conditions_proposal_id,
        )

        _conditions_state[555] = "p1"
        assert is_in_conditions_mode(555)
        get_conditions_proposal_id(555)
        assert not is_in_conditions_mode(555)
        # Second get returns empty
        assert get_conditions_proposal_id(555) == ""


# ──────────────────────────────────────────────────────────
# Test: Agent labels resolution
# ──────────────────────────────────────────────────────────

class TestAgentLabels:
    """Test that agent labels resolve correctly in callback messages."""

    @pytest.mark.asyncio
    async def test_approve_shows_yuki_label(self):
        from src.telegram_ceo.handlers.callbacks import on_cto_approve

        callback = _make_callback_query("cto_approve:p1")
        proposal = _make_proposal("p1", target_agent="yuki")

        with patch(
            "src.telegram_ceo.handlers.callbacks._find_and_update_proposal",
            return_value=proposal,
        ):
            await on_cto_approve(callback, CtoCB(action="approve", id="p1"))

        text = callback.message.edit_text.call_args[0][0]
        assert "Юки" in text

    @pytest.mark.asyncio
    async def test_approve_shows_accountant_label(self):
        from src.telegram_ceo.handlers.callbacks import on_cto_approve

        callback = _make_callback_query("cto_approve:p1")
        proposal = _make_proposal("p1", target_agent="accountant")

        with patch(
            "src.telegram_ceo.handlers.callbacks._find_and_update_proposal",
            return_value=proposal,
        ):
            await on_cto_approve(callback, CtoCB(action="approve", id="p1"))

        text = callback.message.edit_text.call_args[0][0]
        assert "Маттиас" in text

    @pytest.mark.asyncio
    async def test_approve_shows_manager_label(self):
        from src.telegram_ceo.handlers.callbacks import on_cto_approve

        callback = _make_callback_query("cto_approve:p1")
        proposal = _make_proposal("p1", target_agent="manager")

        with patch(
            "src.telegram_ceo.handlers.callbacks._find_and_update_proposal",
            return_value=proposal,
        ):
            await on_cto_approve(callback, CtoCB(action="approve", id="p1"))

        text = callback.message.edit_text.call_args[0][0]
        assert "Алексей" in text

    @pytest.mark.asyncio
    async def test_approve_shows_automator_label(self):
        from src.telegram_ceo.handlers.callbacks import on_cto_approve

        callback = _make_callback_query("cto_approve:p1")
        proposal = _make_proposal("p1", target_agent="automator")

        with patch(
            "src.telegram_ceo.handlers.callbacks._find_and_update_proposal",
            return_value=proposal,
        ):
            await on_cto_approve(callback, CtoCB(action="approve", id="p1"))

        text = callback.message.edit_text.call_args[0][0]
        assert "Мартин" in text

    @pytest.mark.asyncio
    async def test_approve_unknown_agent_shows_raw_key(self):
        from src.telegram_ceo.handlers.callbacks import on_cto_approve

        callback = _make_callback_query("cto_approve:p1")
        proposal = _make_proposal("p1", target_agent="unknown_agent")

        with patch(
            "src.telegram_ceo.handlers.callbacks._find_and_update_proposal",
            return_value=proposal,
        ):
            await on_cto_approve(callback, CtoCB(action="approve", id="p1"))

        text = callback.message.edit_text.call_args[0][0]
        assert "unknown_agent" in text


# ──────────────────────────────────────────────────────────
# Test: Regression — existing tests still pass
# ──────────────────────────────────────────────────────────

class TestRegression:
    """Make sure the fixes don't break anything else."""

    def test_proposal_keyboard_still_works(self):
        from src.telegram_ceo.keyboards import proposal_keyboard

        kb = proposal_keyboard("test_id")
        assert len(kb.inline_keyboard) == 2
        assert kb.inline_keyboard[0][0].text == "✅ Одобрить"

    def test_diagnostic_keyboard_still_works(self):
        from src.telegram_ceo.keyboards import diagnostic_keyboard

        kb = diagnostic_keyboard("diag_id")
        assert len(kb.inline_keyboard) == 2
        assert "Перепроверить" in kb.inline_keyboard[0][0].text

    def test_conditions_state_module_level(self):
        """_conditions_state should persist across handler calls."""
        from src.telegram_ceo.handlers.callbacks import _conditions_state

        _conditions_state[999] = "test"
        assert _conditions_state[999] == "test"
        del _conditions_state[999]

    def test_load_proposals_returns_default_on_missing_file(self):
        from src.tools.improvement_advisor import _load_proposals

        with patch(
            "src.tools.improvement_advisor._proposals_path",
            return_value="/nonexistent/path.json",
        ):
            data = _load_proposals()
            assert data["proposals"] == []
            assert "stats" in data

    def test_save_proposals_creates_directory(self):
        from src.tools.improvement_advisor import _save_proposals

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "subdir", "cto_proposals.json")
            with patch(
                "src.tools.improvement_advisor._proposals_path", return_value=path
            ):
                _save_proposals(_make_proposals_data())
                assert os.path.exists(path)
