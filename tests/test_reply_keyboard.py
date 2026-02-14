"""Tests for ReplyKeyboard and Sub-menus — Sprint 9."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup

from src.telegram_ceo.voice_brain_state import _voice_brain_state
from src.telegram_ceo.callback_factory import SubMenuCB


# ═══════════════════════════════════════════════════════════════
# ReplyKeyboard structure — 5 tests
# ═══════════════════════════════════════════════════════════════

class TestMainReplyKeyboard:
    def test_keyboard_type(self):
        from src.telegram_ceo.keyboards import main_reply_keyboard
        kb = main_reply_keyboard()
        assert isinstance(kb, ReplyKeyboardMarkup)

    def test_keyboard_3x2(self):
        from src.telegram_ceo.keyboards import main_reply_keyboard
        kb = main_reply_keyboard()
        assert len(kb.keyboard) == 2
        assert len(kb.keyboard[0]) == 3
        assert len(kb.keyboard[1]) == 3

    def test_keyboard_resize(self):
        from src.telegram_ceo.keyboards import main_reply_keyboard
        kb = main_reply_keyboard()
        assert kb.resize_keyboard is True

    def test_keyboard_persistent(self):
        from src.telegram_ceo.keyboards import main_reply_keyboard
        kb = main_reply_keyboard()
        assert kb.is_persistent is True

    def test_keyboard_button_texts(self):
        from src.telegram_ceo.keyboards import main_reply_keyboard
        kb = main_reply_keyboard()
        texts = []
        for row in kb.keyboard:
            for btn in row:
                texts.append(btn.text)
        assert "📋 Задачи" in texts
        assert "📊 Статус" in texts
        assert "📈 Аналитика" in texts
        assert "✍️ Контент" in texts
        assert "🖼 Галерея" in texts
        assert "❓ Помощь" in texts


# ═══════════════════════════════════════════════════════════════
# Button → command mapping — 7 tests
# ═══════════════════════════════════════════════════════════════

class TestReplyKeyboardMapping:
    def setup_method(self):
        _voice_brain_state.clear()

    def _make_message(self, text: str, user_id: int = 123):
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
    async def test_tasks_button(self):
        from src.telegram_ceo.handlers.messages import handle_text
        msg = self._make_message("📋 Задачи")
        with patch("src.telegram_ceo.handlers.commands.cmd_tasks") as mock:
            mock.return_value = None
            await handle_text(msg)
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_status_button(self):
        from src.telegram_ceo.handlers.messages import handle_text
        msg = self._make_message("📊 Статус")
        with patch("src.telegram_ceo.handlers.commands.cmd_status") as mock:
            mock.return_value = None
            await handle_text(msg)
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_analytics_button(self):
        from src.telegram_ceo.handlers.messages import handle_text
        msg = self._make_message("📈 Аналитика")
        with patch("src.telegram_ceo.handlers.commands.cmd_analytics") as mock:
            mock.return_value = None
            await handle_text(msg)
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_gallery_button(self):
        from src.telegram_ceo.handlers.messages import handle_text
        msg = self._make_message("🖼 Галерея")
        with patch("src.telegram_ceo.handlers.commands.cmd_gallery") as mock:
            mock.return_value = None
            await handle_text(msg)
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_help_button(self):
        from src.telegram_ceo.handlers.messages import handle_text
        msg = self._make_message("❓ Помощь")
        with patch("src.telegram_ceo.handlers.commands.cmd_help") as mock:
            mock.return_value = None
            await handle_text(msg)
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_content_button_shows_submenu(self):
        from src.telegram_ceo.handlers.messages import handle_text
        msg = self._make_message("✍️ Контент")
        await handle_text(msg)
        msg.answer.assert_called_once()
        call_args = msg.answer.call_args
        # reply_markup should be content_submenu_keyboard
        assert call_args.kwargs.get("reply_markup") is not None

    @pytest.mark.asyncio
    async def test_regular_text_not_intercepted(self):
        """Regular text should not be caught by reply keyboard mapping."""
        from src.telegram_ceo.handlers.messages import _REPLY_KB_MAP
        assert "привет алексей" not in _REPLY_KB_MAP


# ═══════════════════════════════════════════════════════════════
# Sub-menu keyboards — 6 tests
# ═══════════════════════════════════════════════════════════════

class TestSubMenuKeyboards:
    def test_content_submenu_type(self):
        from src.telegram_ceo.keyboards import content_submenu_keyboard
        kb = content_submenu_keyboard()
        assert isinstance(kb, InlineKeyboardMarkup)

    def test_content_submenu_buttons(self):
        from src.telegram_ceo.keyboards import content_submenu_keyboard
        kb = content_submenu_keyboard()
        assert len(kb.inline_keyboard) == 1
        assert len(kb.inline_keyboard[0]) == 3
        data = [btn.callback_data for btn in kb.inline_keyboard[0]]
        assert SubMenuCB(menu="content", action="post").pack() in data
        assert SubMenuCB(menu="content", action="calendar").pack() in data
        assert SubMenuCB(menu="content", action="linkedin").pack() in data

    def test_status_submenu_type(self):
        from src.telegram_ceo.keyboards import status_submenu_keyboard
        kb = status_submenu_keyboard()
        assert isinstance(kb, InlineKeyboardMarkup)

    def test_status_submenu_buttons(self):
        from src.telegram_ceo.keyboards import status_submenu_keyboard
        kb = status_submenu_keyboard()
        assert len(kb.inline_keyboard) == 1
        assert len(kb.inline_keyboard[0]) == 3
        data = [btn.callback_data for btn in kb.inline_keyboard[0]]
        assert SubMenuCB(menu="status", action="agents").pack() in data
        assert SubMenuCB(menu="status", action="tasks").pack() in data
        assert SubMenuCB(menu="status", action="revenue").pack() in data

    def test_content_submenu_labels(self):
        from src.telegram_ceo.keyboards import content_submenu_keyboard
        kb = content_submenu_keyboard()
        texts = [btn.text for btn in kb.inline_keyboard[0]]
        assert any("Пост" in t for t in texts)
        assert any("Календарь" in t for t in texts)
        assert any("LinkedIn" in t for t in texts)

    def test_status_submenu_labels(self):
        from src.telegram_ceo.keyboards import status_submenu_keyboard
        kb = status_submenu_keyboard()
        texts = [btn.text for btn in kb.inline_keyboard[0]]
        assert any("Агенты" in t for t in texts)
        assert any("Tasks" in t for t in texts)
        assert any("Revenue" in t for t in texts)


# ═══════════════════════════════════════════════════════════════
# Sub-menu callbacks — 6 tests
# ═══════════════════════════════════════════════════════════════

class TestSubMenuCallbacks:
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
    async def test_sub_content_post(self):
        from src.telegram_ceo.handlers.callbacks import on_sub_content_post, _new_content_state
        _new_content_state.discard(123)
        callback = self._make_callback("sub:content:post")
        await on_sub_content_post(callback, SubMenuCB(menu="content", action="post"))
        assert 123 in _new_content_state
        _new_content_state.discard(123)

    @pytest.mark.asyncio
    async def test_sub_content_calendar(self):
        from src.telegram_ceo.handlers.callbacks import on_sub_content_calendar
        callback = self._make_callback("sub:content:calendar")
        with patch("src.telegram_ceo.handlers.commands.cmd_calendar") as mock:
            mock.return_value = None
            await on_sub_content_calendar(callback, SubMenuCB(menu="content", action="calendar"))
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_sub_content_linkedin(self):
        from src.telegram_ceo.handlers.callbacks import on_sub_content_linkedin
        callback = self._make_callback("sub:content:linkedin")
        with patch("src.telegram_ceo.handlers.commands.cmd_linkedin") as mock:
            mock.return_value = None
            await on_sub_content_linkedin(callback, SubMenuCB(menu="content", action="linkedin"))
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_sub_status_agents(self):
        from src.telegram_ceo.handlers.callbacks import on_sub_status_agents
        callback = self._make_callback("sub:status:agents")
        with patch("src.telegram_ceo.handlers.commands.cmd_status") as mock:
            mock.return_value = None
            await on_sub_status_agents(callback, SubMenuCB(menu="status", action="agents"))
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_sub_status_tasks(self):
        from src.telegram_ceo.handlers.callbacks import on_sub_status_tasks
        callback = self._make_callback("sub:status:tasks")
        with patch("src.telegram_ceo.handlers.commands.cmd_tasks") as mock:
            mock.return_value = None
            await on_sub_status_tasks(callback, SubMenuCB(menu="status", action="tasks"))
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_sub_status_revenue_no_file(self):
        from src.telegram_ceo.handlers.callbacks import on_sub_status_revenue
        callback = self._make_callback("sub:status:revenue")
        with patch("os.path.exists", return_value=False):
            await on_sub_status_revenue(callback, SubMenuCB(menu="status", action="revenue"))
            callback.message.answer.assert_called_once()
            assert "отсутствуют" in callback.message.answer.call_args[0][0]
