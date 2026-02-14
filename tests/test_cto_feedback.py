"""Tests for CTO → CEO feedback approval flow.

Round 1: Testing callback handlers, _find_and_update_proposal,
keyboard behavior, and error handling.
"""

import asyncio
import json
import os
import tempfile
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from src.telegram_ceo.callback_factory import CtoCB


# ──────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────

def _make_proposals_data(proposals=None):
    """Create a proposals data structure with given proposals list."""
    return {
        "proposals": proposals or [],
        "stats": {"total_generated": 0, "approved": 0, "rejected": 0, "conditions": 0},
        "last_run": None,
    }


def _make_proposal(proposal_id="prop_test_001", status="pending", target_agent="yuki"):
    """Create a sample proposal dict."""
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
    """Create a mock CallbackQuery object."""
    callback = AsyncMock()
    callback.data = callback_data
    callback.from_user = MagicMock()
    callback.from_user.id = user_id
    callback.message = AsyncMock()
    callback.message.edit_text = AsyncMock()
    callback.message.edit_reply_markup = AsyncMock()
    callback.answer = AsyncMock()
    return callback


# ──────────────────────────────────────────────────────────
# Test: _find_and_update_proposal
# ──────────────────────────────────────────────────────────

class TestFindAndUpdateProposal:
    """Test the core _find_and_update_proposal function."""

    def test_returns_none_for_missing_proposal(self):
        from src.telegram_ceo.handlers.callbacks import _find_and_update_proposal

        data = _make_proposals_data([_make_proposal("p1")])
        with patch("src.tools.improvement_advisor._load_proposals", return_value=data):
            with patch("src.tools.improvement_advisor._save_proposals"):
                result = _find_and_update_proposal("nonexistent", {"status": "approved"})
                assert result is None

    def test_updates_status_to_approved(self):
        from src.telegram_ceo.handlers.callbacks import _find_and_update_proposal

        data = _make_proposals_data([_make_proposal("p1")])
        saved_data = {}

        def capture_save(d):
            saved_data.update(d)

        with patch("src.tools.improvement_advisor._load_proposals", return_value=data):
            with patch("src.tools.improvement_advisor._save_proposals", side_effect=capture_save):
                result = _find_and_update_proposal("p1", {"status": "approved"})
                assert result is not None
                assert result["status"] == "approved"
                assert result["reviewed_at"] is not None

    def test_updates_status_to_rejected(self):
        from src.telegram_ceo.handlers.callbacks import _find_and_update_proposal

        data = _make_proposals_data([_make_proposal("p1")])
        with patch("src.tools.improvement_advisor._load_proposals", return_value=data):
            with patch("src.tools.improvement_advisor._save_proposals"):
                result = _find_and_update_proposal("p1", {"status": "rejected"})
                assert result["status"] == "rejected"

    def test_increments_stats_on_approve(self):
        from src.telegram_ceo.handlers.callbacks import _find_and_update_proposal

        data = _make_proposals_data([_make_proposal("p1")])
        data["stats"]["approved"] = 5
        saved_data = {}

        def capture_save(d):
            saved_data.update(d)

        with patch("src.tools.improvement_advisor._load_proposals", return_value=data):
            with patch("src.tools.improvement_advisor._save_proposals", side_effect=capture_save):
                _find_and_update_proposal("p1", {"status": "approved"})
                assert saved_data["stats"]["approved"] == 6

    def test_increments_stats_on_reject(self):
        from src.telegram_ceo.handlers.callbacks import _find_and_update_proposal

        data = _make_proposals_data([_make_proposal("p1")])
        data["stats"]["rejected"] = 2
        saved_data = {}

        def capture_save(d):
            saved_data.update(d)

        with patch("src.tools.improvement_advisor._load_proposals", return_value=data):
            with patch("src.tools.improvement_advisor._save_proposals", side_effect=capture_save):
                _find_and_update_proposal("p1", {"status": "rejected"})
                assert saved_data["stats"]["rejected"] == 3

    def test_increments_stats_on_conditions(self):
        from src.telegram_ceo.handlers.callbacks import _find_and_update_proposal

        data = _make_proposals_data([_make_proposal("p1")])
        saved_data = {}

        def capture_save(d):
            saved_data.update(d)

        with patch("src.tools.improvement_advisor._load_proposals", return_value=data):
            with patch("src.tools.improvement_advisor._save_proposals", side_effect=capture_save):
                _find_and_update_proposal(
                    "p1", {"status": "conditions", "conditions": "Do X first"}
                )
                assert saved_data["stats"]["conditions"] == 1

    def test_double_approve_does_not_increment_stats(self):
        """FIX: double-clicking approve should NOT increment stats again."""
        from src.telegram_ceo.handlers.callbacks import _find_and_update_proposal

        data = _make_proposals_data([_make_proposal("p1", status="approved")])
        data["stats"]["approved"] = 1
        saved_data = {}

        def capture_save(d):
            saved_data.update(d)

        with patch("src.tools.improvement_advisor._load_proposals", return_value=data):
            with patch("src.tools.improvement_advisor._save_proposals", side_effect=capture_save):
                _find_and_update_proposal("p1", {"status": "approved"})
                # FIX: stats["approved"] should NOT increment if already approved
                assert saved_data["stats"]["approved"] == 1

    def test_sets_reviewed_at(self):
        from src.telegram_ceo.handlers.callbacks import _find_and_update_proposal

        data = _make_proposals_data([_make_proposal("p1")])
        with patch("src.tools.improvement_advisor._load_proposals", return_value=data):
            with patch("src.tools.improvement_advisor._save_proposals"):
                result = _find_and_update_proposal("p1", {"status": "approved"})
                assert result["reviewed_at"] is not None
                # Should be a valid ISO timestamp
                datetime.fromisoformat(result["reviewed_at"])


# ──────────────────────────────────────────────────────────
# Test: on_cto_approve callback handler
# ──────────────────────────────────────────────────────────

class TestOnCtoApprove:
    """Test the approval callback handler."""

    @pytest.mark.asyncio
    async def test_approve_updates_message(self):
        from src.telegram_ceo.handlers.callbacks import on_cto_approve

        proposal = _make_proposal("prop_test_001")
        callback = _make_callback_query("cto_approve:prop_test_001")

        with patch(
            "src.telegram_ceo.handlers.callbacks._find_and_update_proposal",
            return_value=proposal,
        ):
            await on_cto_approve(callback, CtoCB(action="approve", id="prop_test_001"))

        # Now calls edit_text multiple times: "⏳ ПРИМЕНЯЮ" then result
        assert callback.message.edit_text.call_count >= 2
        # First call is "applying..." status
        first_text = callback.message.edit_text.call_args_list[0][0][0]
        assert "ПРИМЕНЯЮ" in first_text
        # Last call has final status
        last_text = callback.message.edit_text.call_args_list[-1][0][0]
        assert "ОДОБРЕНО" in last_text
        callback.answer.assert_called_once_with("Одобрено! Применяю...")

    @pytest.mark.asyncio
    async def test_approve_not_found_shows_alert(self):
        from src.telegram_ceo.handlers.callbacks import on_cto_approve

        callback = _make_callback_query("cto_approve:nonexistent")

        with patch(
            "src.telegram_ceo.handlers.callbacks._find_and_update_proposal",
            return_value=None,
        ):
            await on_cto_approve(callback, CtoCB(action="approve", id="nonexistent"))

        callback.answer.assert_called_once_with(
            "Предложение не найдено", show_alert=True
        )
        callback.message.edit_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_approve_removes_keyboard(self):
        """FIX: After approving, keyboard buttons should be removed."""
        from src.telegram_ceo.handlers.callbacks import on_cto_approve

        proposal = _make_proposal("prop_test_001")
        callback = _make_callback_query("cto_approve:prop_test_001")

        with patch(
            "src.telegram_ceo.handlers.callbacks._find_and_update_proposal",
            return_value=proposal,
        ):
            await on_cto_approve(callback, CtoCB(action="approve", id="prop_test_001"))

        # Check that edit_text was called with reply_markup=None to remove keyboard
        call_kwargs = callback.message.edit_text.call_args
        assert call_kwargs.kwargs.get("reply_markup") is None, (
            "edit_text should pass reply_markup=None to remove keyboard"
        )

    @pytest.mark.asyncio
    async def test_approve_handles_edit_text_error(self):
        """FIX: If edit_text fails, callback.answer should still be called."""
        from src.telegram_ceo.handlers.callbacks import on_cto_approve

        proposal = _make_proposal("prop_test_001")
        callback = _make_callback_query("cto_approve:prop_test_001")

        # Simulate Telegram API error (e.g., "message is not modified")
        callback.message.edit_text = AsyncMock(
            side_effect=Exception("Bad Request: message is not modified")
        )

        with patch(
            "src.telegram_ceo.handlers.callbacks._find_and_update_proposal",
            return_value=proposal,
        ):
            # Should NOT raise — error is caught internally
            await on_cto_approve(callback, CtoCB(action="approve", id="prop_test_001"))

        # callback.answer should be called even if edit_text fails
        callback.answer.assert_called_once_with("Одобрено! Применяю...")

    @pytest.mark.asyncio
    async def test_approve_includes_agent_name(self):
        from src.telegram_ceo.handlers.callbacks import on_cto_approve

        proposal = _make_proposal("prop_test_001", target_agent="yuki")
        callback = _make_callback_query("cto_approve:prop_test_001")

        with patch(
            "src.telegram_ceo.handlers.callbacks._find_and_update_proposal",
            return_value=proposal,
        ):
            await on_cto_approve(callback, CtoCB(action="approve", id="prop_test_001"))

        text = callback.message.edit_text.call_args[0][0]
        assert "Юки" in text


# ──────────────────────────────────────────────────────────
# Test: on_cto_reject callback handler
# ──────────────────────────────────────────────────────────

class TestOnCtoReject:
    """Test the rejection callback handler."""

    @pytest.mark.asyncio
    async def test_reject_updates_message(self):
        from src.telegram_ceo.handlers.callbacks import on_cto_reject

        proposal = _make_proposal("prop_test_001")
        callback = _make_callback_query("cto_reject:prop_test_001")

        with patch(
            "src.telegram_ceo.handlers.callbacks._find_and_update_proposal",
            return_value=proposal,
        ):
            await on_cto_reject(callback, CtoCB(action="reject", id="prop_test_001"))

        text = callback.message.edit_text.call_args[0][0]
        assert "ОТКЛОНЕНО" in text
        callback.answer.assert_called_once_with("Отклонено")

    @pytest.mark.asyncio
    async def test_reject_removes_keyboard(self):
        """FIX: After rejecting, keyboard buttons should be removed."""
        from src.telegram_ceo.handlers.callbacks import on_cto_reject

        proposal = _make_proposal("prop_test_001")
        callback = _make_callback_query("cto_reject:prop_test_001")

        with patch(
            "src.telegram_ceo.handlers.callbacks._find_and_update_proposal",
            return_value=proposal,
        ):
            await on_cto_reject(callback, CtoCB(action="reject", id="prop_test_001"))

        call_kwargs = callback.message.edit_text.call_args
        assert call_kwargs.kwargs.get("reply_markup") is None, (
            "edit_text should pass reply_markup=None to remove keyboard"
        )

    @pytest.mark.asyncio
    async def test_reject_handles_edit_text_error(self):
        """FIX: If edit_text fails, callback.answer should still be called."""
        from src.telegram_ceo.handlers.callbacks import on_cto_reject

        proposal = _make_proposal("prop_test_001")
        callback = _make_callback_query("cto_reject:prop_test_001")
        callback.message.edit_text = AsyncMock(
            side_effect=Exception("Bad Request: message is not modified")
        )

        with patch(
            "src.telegram_ceo.handlers.callbacks._find_and_update_proposal",
            return_value=proposal,
        ):
            # Should NOT raise
            await on_cto_reject(callback, CtoCB(action="reject", id="prop_test_001"))

        callback.answer.assert_called_once_with("Отклонено")


# ──────────────────────────────────────────────────────────
# Test: on_cto_conditions callback handler
# ──────────────────────────────────────────────────────────

class TestOnCtoConditions:
    """Test the conditions entry mode."""

    @pytest.mark.asyncio
    async def test_conditions_enters_mode(self):
        from src.telegram_ceo.handlers.callbacks import (
            on_cto_conditions,
            is_in_conditions_mode,
            _conditions_state,
        )

        proposal = _make_proposal("prop_test_001")
        data = _make_proposals_data([proposal])
        callback = _make_callback_query("cto_conditions:prop_test_001", user_id=999)

        with patch("src.tools.improvement_advisor._load_proposals", return_value=data):
            await on_cto_conditions(callback, CtoCB(action="conditions", id="prop_test_001"))

        assert is_in_conditions_mode(999)
        # Clean up
        _conditions_state.pop(999, None)

    @pytest.mark.asyncio
    async def test_conditions_not_found(self):
        from src.telegram_ceo.handlers.callbacks import on_cto_conditions

        data = _make_proposals_data([])
        callback = _make_callback_query("cto_conditions:nonexistent", user_id=999)

        with patch("src.tools.improvement_advisor._load_proposals", return_value=data):
            await on_cto_conditions(callback, CtoCB(action="conditions", id="nonexistent"))

        callback.answer.assert_called_once_with(
            "Предложение не найдено", show_alert=True
        )

    @pytest.mark.asyncio
    async def test_conditions_text_received(self):
        """Test that conditions text is properly saved via message handler."""
        from src.telegram_ceo.handlers.callbacks import (
            _conditions_state,
            get_conditions_proposal_id,
            is_in_conditions_mode,
        )

        _conditions_state[777] = "prop_test_001"
        assert is_in_conditions_mode(777)

        pid = get_conditions_proposal_id(777)
        assert pid == "prop_test_001"
        assert not is_in_conditions_mode(777)  # cleared after get


# ──────────────────────────────────────────────────────────
# Test: on_cto_detail callback handler
# ──────────────────────────────────────────────────────────

class TestOnCtoDetail:
    """Test the proposal detail view."""

    @pytest.mark.asyncio
    async def test_detail_shows_full_info(self):
        from src.telegram_ceo.handlers.callbacks import on_cto_detail

        proposal = _make_proposal("prop_test_001")
        data = _make_proposals_data([proposal])
        callback = _make_callback_query("cto_detail:prop_test_001")

        with patch("src.tools.improvement_advisor._load_proposals", return_value=data):
            await on_cto_detail(callback, CtoCB(action="detail", id="prop_test_001"))

        text = callback.message.edit_text.call_args[0][0]
        assert "Улучшить goal для Юки" in text
        assert "Уверенность: 85%" in text
        callback.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_detail_includes_keyboard(self):
        """Detail view should include the proposal keyboard for further actions."""
        from src.telegram_ceo.handlers.callbacks import on_cto_detail

        proposal = _make_proposal("prop_test_001")
        data = _make_proposals_data([proposal])
        callback = _make_callback_query("cto_detail:prop_test_001")

        with patch("src.tools.improvement_advisor._load_proposals", return_value=data):
            await on_cto_detail(callback, CtoCB(action="detail", id="prop_test_001"))

        call_kwargs = callback.message.edit_text.call_args.kwargs
        assert "reply_markup" in call_kwargs
        assert call_kwargs["reply_markup"] is not None

    @pytest.mark.asyncio
    async def test_detail_not_found(self):
        from src.telegram_ceo.handlers.callbacks import on_cto_detail

        data = _make_proposals_data([])
        callback = _make_callback_query("cto_detail:nonexistent")

        with patch("src.tools.improvement_advisor._load_proposals", return_value=data):
            await on_cto_detail(callback, CtoCB(action="detail", id="nonexistent"))

        callback.answer.assert_called_once_with(
            "Предложение не найдено", show_alert=True
        )

    @pytest.mark.asyncio
    async def test_detail_truncates_long_text(self):
        from src.telegram_ceo.handlers.callbacks import on_cto_detail

        proposal = _make_proposal("prop_test_001")
        proposal["description"] = "A" * 5000  # Very long description
        data = _make_proposals_data([proposal])
        callback = _make_callback_query("cto_detail:prop_test_001")

        with patch("src.tools.improvement_advisor._load_proposals", return_value=data):
            await on_cto_detail(callback, CtoCB(action="detail", id="prop_test_001"))

        text = callback.message.edit_text.call_args[0][0]
        assert len(text) <= 4003  # 4000 + "..."


# ──────────────────────────────────────────────────────────
# Test: proposal_keyboard
# ──────────────────────────────────────────────────────────

class TestProposalKeyboard:
    def test_keyboard_has_4_buttons(self):
        from src.telegram_ceo.keyboards import proposal_keyboard

        kb = proposal_keyboard("prop_test_001")
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        assert len(all_buttons) == 4

    def test_keyboard_callback_data(self):
        from src.telegram_ceo.keyboards import proposal_keyboard

        kb = proposal_keyboard("prop_test_001")
        assert kb.inline_keyboard[0][0].callback_data == CtoCB(action="approve", id="prop_test_001").pack()
        assert kb.inline_keyboard[0][1].callback_data == CtoCB(action="reject", id="prop_test_001").pack()
        assert kb.inline_keyboard[1][0].callback_data == CtoCB(action="conditions", id="prop_test_001").pack()
        assert kb.inline_keyboard[1][1].callback_data == CtoCB(action="detail", id="prop_test_001").pack()

    def test_keyboard_button_labels(self):
        from src.telegram_ceo.keyboards import proposal_keyboard

        kb = proposal_keyboard("prop_test_001")
        assert "Одобрить" in kb.inline_keyboard[0][0].text
        assert "Отклонить" in kb.inline_keyboard[0][1].text
        assert "Условия" in kb.inline_keyboard[1][0].text
        assert "Подробнее" in kb.inline_keyboard[1][1].text

    def test_callback_data_length_within_telegram_limit(self):
        """Telegram callback_data max is 64 bytes."""
        from src.telegram_ceo.keyboards import proposal_keyboard

        # Worst case proposal ID
        long_id = "prop_20260208_1530_automator"
        kb = proposal_keyboard(long_id)
        for row in kb.inline_keyboard:
            for btn in row:
                assert len(btn.callback_data.encode("utf-8")) <= 64, (
                    f"callback_data too long: {btn.callback_data} "
                    f"({len(btn.callback_data.encode('utf-8'))} bytes)"
                )


# ──────────────────────────────────────────────────────────
# Test: Full flow integration
# ──────────────────────────────────────────────────────────

class TestFullFlow:
    """Test the complete proposal → approve flow end to end."""

    def test_proposal_roundtrip_with_file(self):
        """Save proposal, then find and update it via file IO."""
        from src.tools.improvement_advisor import _save_proposals, _load_proposals

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "cto_proposals.json")
            with patch(
                "src.tools.improvement_advisor._proposals_path", return_value=path
            ):
                # Save initial proposal
                data = _make_proposals_data([_make_proposal("p1")])
                _save_proposals(data)

                # Load and verify
                loaded = _load_proposals()
                assert loaded["proposals"][0]["id"] == "p1"
                assert loaded["proposals"][0]["status"] == "pending"

                # Update status
                from src.telegram_ceo.handlers.callbacks import (
                    _find_and_update_proposal,
                )

                result = _find_and_update_proposal("p1", {"status": "approved"})
                assert result["status"] == "approved"

                # Reload and verify persisted
                reloaded = _load_proposals()
                assert reloaded["proposals"][0]["status"] == "approved"
                assert reloaded["stats"]["approved"] == 1

    @pytest.mark.asyncio
    async def test_scheduler_sends_proposal_with_keyboard(self):
        """Verify scheduler sends proposal message with inline keyboard."""
        from src.telegram_ceo.keyboards import proposal_keyboard

        proposal = _make_proposal("prop_test_001")
        kb = proposal_keyboard(proposal["id"])

        # Verify keyboard is constructed correctly
        assert kb.inline_keyboard[0][0].text == "✅ Одобрить"
        assert CtoCB(action="approve", id="prop_test_001").pack() in kb.inline_keyboard[0][0].callback_data


# ──────────────────────────────────────────────────────────
# Test: Edge cases
# ──────────────────────────────────────────────────────────

class TestEdgeCases:
    """Test edge cases and error scenarios."""

    def test_empty_proposals_file(self):
        """_find_and_update_proposal with empty proposals list."""
        from src.telegram_ceo.handlers.callbacks import _find_and_update_proposal

        data = _make_proposals_data([])
        with patch("src.tools.improvement_advisor._load_proposals", return_value=data):
            with patch("src.tools.improvement_advisor._save_proposals"):
                result = _find_and_update_proposal("p1", {"status": "approved"})
                assert result is None

    def test_corrupted_proposal_missing_fields(self):
        """Proposal dict missing expected fields should not crash."""
        from src.telegram_ceo.handlers.callbacks import _find_and_update_proposal

        data = _make_proposals_data([{"id": "p1"}])  # Minimal proposal
        with patch("src.tools.improvement_advisor._load_proposals", return_value=data):
            with patch("src.tools.improvement_advisor._save_proposals"):
                result = _find_and_update_proposal("p1", {"status": "approved"})
                assert result is not None
                assert result["status"] == "approved"

    @pytest.mark.asyncio
    async def test_approve_with_unknown_target_agent(self):
        """Proposal with unknown target_agent should not crash.
        Now on_cto_approve auto-applies, so unknown agent triggers apply error.
        """
        from src.telegram_ceo.handlers.callbacks import on_cto_approve

        proposal = _make_proposal("prop_test_001", target_agent="unknown_agent")
        callback = _make_callback_query("cto_approve:prop_test_001")

        with patch(
            "src.telegram_ceo.handlers.callbacks._find_and_update_proposal",
            return_value=proposal,
        ):
            await on_cto_approve(callback, CtoCB(action="approve", id="prop_test_001"))

        # Called at least twice: "⏳ ПРИМЕНЯЮ" + error/result message
        assert callback.message.edit_text.call_count >= 2
        callback.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiple_proposals_finds_correct_one(self):
        """With multiple proposals, should find and update the right one."""
        from src.telegram_ceo.handlers.callbacks import _find_and_update_proposal

        data = _make_proposals_data([
            _make_proposal("p1", target_agent="yuki"),
            _make_proposal("p2", target_agent="accountant"),
            _make_proposal("p3", target_agent="manager"),
        ])

        with patch("src.tools.improvement_advisor._load_proposals", return_value=data):
            with patch("src.tools.improvement_advisor._save_proposals"):
                result = _find_and_update_proposal("p2", {"status": "rejected"})
                assert result["target_agent"] == "accountant"
                assert result["status"] == "rejected"
