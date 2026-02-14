"""Tests for Voice Brain Dump Pipeline — Sprint 9."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.telegram_ceo.callback_factory import VoiceBrainCB
from src.telegram_ceo.voice_brain_state import (
    VoiceBrainSession,
    _voice_brain_state,
    is_in_voice_brain_mode,
    get_voice_brain_session,
    start_voice_brain_session,
    update_voice_brain_session,
    end_voice_brain_session,
    can_iterate,
    MAX_ITERATIONS,
)


# ═══════════════════════════════════════════════════════════════
# VoiceBrainState CRUD — 10 tests
# ═══════════════════════════════════════════════════════════════

class TestVoiceBrainState:
    def setup_method(self):
        _voice_brain_state.clear()

    def test_not_in_mode_by_default(self):
        assert not is_in_voice_brain_mode(123)

    def test_start_session(self):
        session = start_voice_brain_session(123, raw_text="hello")
        assert is_in_voice_brain_mode(123)
        assert session.raw_text == "hello"
        assert session.iteration == 0

    def test_get_session(self):
        start_voice_brain_session(123, raw_text="hi", proposals=[{"text": "a"}])
        session = get_voice_brain_session(123)
        assert session is not None
        assert session.proposals == [{"text": "a"}]

    def test_get_session_none(self):
        assert get_voice_brain_session(999) is None

    def test_end_session(self):
        start_voice_brain_session(123, raw_text="test")
        session = end_voice_brain_session(123)
        assert session is not None
        assert not is_in_voice_brain_mode(123)

    def test_end_session_none(self):
        assert end_voice_brain_session(999) is None

    def test_update_session_increments_iteration(self):
        start_voice_brain_session(123, raw_text="v1")
        updated = update_voice_brain_session(123, raw_text="v2")
        assert updated.raw_text == "v2"
        assert updated.iteration == 1

    def test_update_nonexistent(self):
        assert update_voice_brain_session(999, raw_text="x") is None

    def test_user_isolation(self):
        start_voice_brain_session(1, raw_text="user1")
        start_voice_brain_session(2, raw_text="user2")
        assert get_voice_brain_session(1).raw_text == "user1"
        assert get_voice_brain_session(2).raw_text == "user2"
        end_voice_brain_session(1)
        assert not is_in_voice_brain_mode(1)
        assert is_in_voice_brain_mode(2)

    def test_can_iterate(self):
        start_voice_brain_session(123, raw_text="test")
        assert can_iterate(123)
        for _ in range(MAX_ITERATIONS):
            update_voice_brain_session(123)
        assert not can_iterate(123)


# ═══════════════════════════════════════════════════════════════
# Analysis helpers — 6 tests
# ═══════════════════════════════════════════════════════════════

class TestAnalysis:
    def test_analyze_brain_dump(self):
        from src.telegram_ceo.handlers.messages import _analyze_voice_input
        text = (
            "1. Проверить API статус всех сервисов\n"
            "2. Обновить документацию по деплою\n"
            "3. Написать тесты для нового модуля\n"
        ) * 5  # Make it > 300 chars
        tasks, proposals, summary = _analyze_voice_input(text)
        assert len(tasks) > 0
        assert len(proposals) == 0

    def test_analyze_proposals_multiline(self):
        from src.telegram_ceo.handlers.messages import _extract_proposals
        text = "Обновить сайт\nСделать редизайн\nДобавить блог"
        proposals = _extract_proposals(text)
        assert len(proposals) == 3
        assert proposals[0]["text"] == "Обновить сайт"

    def test_analyze_proposals_sentences(self):
        from src.telegram_ceo.handlers.messages import _extract_proposals
        text = "Обновить сайт. Сделать редизайн. Добавить блог."
        proposals = _extract_proposals(text)
        assert len(proposals) == 3

    def test_analyze_proposals_strips_markers(self):
        from src.telegram_ceo.handlers.messages import _extract_proposals
        text = "1. Первый пункт\n2. Второй пункт\n3. Третий пункт"
        proposals = _extract_proposals(text)
        assert proposals[0]["text"] == "Первый пункт"

    def test_analyze_short_text_no_brain_dump(self):
        from src.telegram_ceo.handlers.messages import _analyze_voice_input
        tasks, proposals, summary = _analyze_voice_input("Привет, как дела?")
        assert len(tasks) == 0
        assert len(proposals) >= 1

    def test_format_proposals_empty(self):
        from src.telegram_ceo.handlers.messages import _format_proposals
        result = _format_proposals("hello", [])
        assert "hello" in result


# ═══════════════════════════════════════════════════════════════
# Keyboard — 4 tests
# ═══════════════════════════════════════════════════════════════

class TestVoiceBrainKeyboard:
    def test_confirm_keyboard_structure(self):
        from src.telegram_ceo.keyboards import voice_brain_confirm_keyboard
        kb = voice_brain_confirm_keyboard()
        assert len(kb.inline_keyboard) == 1
        assert len(kb.inline_keyboard[0]) == 3

    def test_confirm_keyboard_data(self):
        from src.telegram_ceo.keyboards import voice_brain_confirm_keyboard
        kb = voice_brain_confirm_keyboard()
        data_values = [btn.callback_data for btn in kb.inline_keyboard[0]]
        assert VoiceBrainCB(action="confirm").pack() in data_values
        assert VoiceBrainCB(action="correct").pack() in data_values
        assert VoiceBrainCB(action="cancel").pack() in data_values

    def test_confirm_keyboard_labels(self):
        from src.telegram_ceo.keyboards import voice_brain_confirm_keyboard
        kb = voice_brain_confirm_keyboard()
        texts = [btn.text for btn in kb.inline_keyboard[0]]
        assert any("Да" in t for t in texts)
        assert any("Уточнить" in t for t in texts)
        assert any("Отмена" in t for t in texts)

    def test_confirm_keyboard_is_inline(self):
        from src.telegram_ceo.keyboards import voice_brain_confirm_keyboard
        from aiogram.types import InlineKeyboardMarkup
        kb = voice_brain_confirm_keyboard()
        assert isinstance(kb, InlineKeyboardMarkup)


# ═══════════════════════════════════════════════════════════════
# Callbacks — 6 tests
# ═══════════════════════════════════════════════════════════════

class TestVoiceBrainCallbacks:
    def setup_method(self):
        _voice_brain_state.clear()

    def _make_callback(self, data: str, user_id: int = 123):
        callback = AsyncMock()
        callback.data = data
        callback.from_user = MagicMock()
        callback.from_user.id = user_id
        callback.message = AsyncMock()
        callback.message.edit_text = AsyncMock()
        callback.message.answer = AsyncMock()
        callback.answer = AsyncMock()
        return callback

    @pytest.mark.asyncio
    async def test_vb_confirm_with_tasks(self):
        from src.telegram_ceo.handlers.callbacks import on_vb_confirm
        task_mock = MagicMock()
        start_voice_brain_session(123, raw_text="test", parsed_tasks=[task_mock, task_mock])
        callback = self._make_callback("vb:confirm")
        await on_vb_confirm(callback, VoiceBrainCB(action="confirm"))
        callback.message.edit_text.assert_called_once()
        assert "2 задач" in callback.message.edit_text.call_args[0][0]
        assert not is_in_voice_brain_mode(123)

    @pytest.mark.asyncio
    async def test_vb_confirm_with_proposals(self):
        from src.telegram_ceo.handlers.callbacks import on_vb_confirm
        proposals = [{"text": "Обновить сайт"}, {"text": "Добавить блог"}]
        start_voice_brain_session(123, raw_text="test", proposals=proposals)
        callback = self._make_callback("vb:confirm")
        with patch("src.task_pool.create_task") as mock_create:
            mock_create.return_value = MagicMock()
            await on_vb_confirm(callback, VoiceBrainCB(action="confirm"))
            assert mock_create.call_count == 2

    @pytest.mark.asyncio
    async def test_vb_confirm_expired(self):
        from src.telegram_ceo.handlers.callbacks import on_vb_confirm
        callback = self._make_callback("vb:confirm")
        await on_vb_confirm(callback, VoiceBrainCB(action="confirm"))
        callback.answer.assert_called_with("Сессия истекла", show_alert=True)

    @pytest.mark.asyncio
    async def test_vb_correct(self):
        from src.telegram_ceo.handlers.callbacks import on_vb_correct
        start_voice_brain_session(123, raw_text="test")
        callback = self._make_callback("vb:correct")
        await on_vb_correct(callback, VoiceBrainCB(action="correct"))
        callback.message.edit_text.assert_called_once()
        assert "уточнение" in callback.message.edit_text.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_vb_correct_expired(self):
        from src.telegram_ceo.handlers.callbacks import on_vb_correct
        callback = self._make_callback("vb:correct")
        await on_vb_correct(callback, VoiceBrainCB(action="correct"))
        callback.answer.assert_called_with("Сессия истекла", show_alert=True)

    @pytest.mark.asyncio
    async def test_vb_cancel(self):
        from src.telegram_ceo.handlers.callbacks import on_vb_cancel
        start_voice_brain_session(123, raw_text="test")
        callback = self._make_callback("vb:cancel")
        await on_vb_cancel(callback, VoiceBrainCB(action="cancel"))
        assert not is_in_voice_brain_mode(123)
        callback.message.edit_text.assert_called_once()
        assert "отменён" in callback.message.edit_text.call_args[0][0].lower()


# ═══════════════════════════════════════════════════════════════
# Flow — 5 tests
# ═══════════════════════════════════════════════════════════════

class TestVoiceBrainFlow:
    def setup_method(self):
        _voice_brain_state.clear()

    def _make_message(self, text: str = "", user_id: int = 123):
        msg = AsyncMock()
        msg.text = text
        msg.from_user = MagicMock()
        msg.from_user.id = user_id
        msg.answer = AsyncMock()
        msg.bot = AsyncMock()
        msg.chat = MagicMock()
        msg.chat.id = 456
        return msg

    @pytest.mark.asyncio
    async def test_text_intercept_in_voice_mode(self):
        """When in voice brain mode, text goes to correction handler."""
        from src.telegram_ceo.handlers.messages import handle_text
        start_voice_brain_session(123, raw_text="оригинал", proposals=[{"text": "test", "index": 0}])
        msg = self._make_message("уточнение к предыдущему")
        await handle_text(msg)
        # Session should still be active (correction doesn't end it)
        assert is_in_voice_brain_mode(123)
        # Should show updated analysis
        msg.answer.assert_called()

    @pytest.mark.asyncio
    async def test_text_correction_updates_session(self):
        from src.telegram_ceo.handlers.messages import _handle_voice_brain_correction
        start_voice_brain_session(123, raw_text="первый текст")
        msg = self._make_message("второй текст")
        await _handle_voice_brain_correction(msg, "второй текст")
        session = get_voice_brain_session(123)
        assert "второй текст" in session.raw_text
        assert session.iteration == 1

    @pytest.mark.asyncio
    async def test_max_iterations_ends_session(self):
        from src.telegram_ceo.handlers.messages import _handle_voice_brain_correction
        start_voice_brain_session(123, raw_text="test")
        for _ in range(MAX_ITERATIONS):
            update_voice_brain_session(123)
        msg = self._make_message("correction")
        await _handle_voice_brain_correction(msg, "correction")
        assert not is_in_voice_brain_mode(123)

    @pytest.mark.asyncio
    async def test_correction_shows_keyboard(self):
        from src.telegram_ceo.handlers.messages import _handle_voice_brain_correction
        start_voice_brain_session(123, raw_text="первое")
        msg = self._make_message("уточнение")
        await _handle_voice_brain_correction(msg, "уточнение")
        call_kwargs = msg.answer.call_args
        assert call_kwargs.kwargs.get("reply_markup") is not None

    @pytest.mark.asyncio
    async def test_voice_correction_combined_text(self):
        """Voice correction should combine original + correction text."""
        from src.telegram_ceo.handlers.messages import _handle_voice_brain_correction
        start_voice_brain_session(123, raw_text="задача один")
        msg = self._make_message("добавить пункт два")
        await _handle_voice_brain_correction(msg, "добавить пункт два")
        session = get_voice_brain_session(123)
        assert "задача один" in session.raw_text
        assert "пункт два" in session.raw_text


# ═══════════════════════════════════════════════════════════════
# Integration — 4 tests
# ═══════════════════════════════════════════════════════════════

class TestVoiceBrainIntegration:
    def setup_method(self):
        _voice_brain_state.clear()

    @pytest.mark.asyncio
    async def test_confirm_creates_pool_tasks(self):
        from src.telegram_ceo.handlers.callbacks import on_vb_confirm
        proposals = [{"text": "Сделать API"}, {"text": "Написать тесты"}]
        start_voice_brain_session(123, raw_text="test", proposals=proposals)

        callback = AsyncMock()
        callback.data = "vb:confirm"
        callback.from_user = MagicMock()
        callback.from_user.id = 123
        callback.message = AsyncMock()
        callback.answer = AsyncMock()

        with patch("src.task_pool.create_task") as mock_create:
            mock_create.return_value = MagicMock()
            await on_vb_confirm(callback, VoiceBrainCB(action="confirm"))
            assert mock_create.call_count == 2

    @pytest.mark.asyncio
    async def test_cancel_cleans_state(self):
        from src.telegram_ceo.handlers.callbacks import on_vb_cancel
        start_voice_brain_session(1, raw_text="a")
        start_voice_brain_session(2, raw_text="b")

        callback = AsyncMock()
        callback.data = "vb:cancel"
        callback.from_user = MagicMock()
        callback.from_user.id = 1
        callback.message = AsyncMock()
        callback.answer = AsyncMock()

        await on_vb_cancel(callback, VoiceBrainCB(action="cancel"))
        assert not is_in_voice_brain_mode(1)
        assert is_in_voice_brain_mode(2)

    def test_session_dataclass_defaults(self):
        s = VoiceBrainSession()
        assert s.raw_text == ""
        assert s.parsed_tasks == []
        assert s.proposals == []
        assert s.summary_text == ""
        assert s.message_id == 0
        assert s.iteration == 0

    def test_update_partial_fields(self):
        start_voice_brain_session(123, raw_text="original", proposals=[{"text": "x"}])
        update_voice_brain_session(123, summary_text="new summary")
        session = get_voice_brain_session(123)
        assert session.raw_text == "original"  # unchanged
        assert session.proposals == [{"text": "x"}]  # unchanged
        assert session.summary_text == "new summary"  # updated
        assert session.iteration == 1
