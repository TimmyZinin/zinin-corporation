"""Tests for unified error handler."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.error_handler import (
    ErrorCategory,
    categorize_error,
    format_error_for_user,
    safe_agent_call,
)


# ──────────────────────────────────────────────────────────
# categorize_error tests
# ──────────────────────────────────────────────────────────

class TestCategorizeError:
    def test_timeout_error(self):
        assert categorize_error(asyncio.TimeoutError()) == ErrorCategory.TIMEOUT

    def test_connection_error(self):
        assert categorize_error(ConnectionError("connection refused")) == ErrorCategory.TRANSIENT

    def test_rate_limit_429(self):
        assert categorize_error(Exception("429 Too Many Requests")) == ErrorCategory.TRANSIENT

    def test_service_unavailable_503(self):
        assert categorize_error(Exception("503 Service Unavailable")) == ErrorCategory.TRANSIENT

    def test_overloaded(self):
        assert categorize_error(Exception("Server overloaded")) == ErrorCategory.TRANSIENT

    def test_unauthorized_401(self):
        assert categorize_error(Exception("401 Unauthorized")) == ErrorCategory.PERMANENT

    def test_forbidden_403(self):
        assert categorize_error(Exception("403 Forbidden")) == ErrorCategory.PERMANENT

    def test_invalid_api_key(self):
        assert categorize_error(Exception("Invalid API key")) == ErrorCategory.PERMANENT

    def test_import_error(self):
        assert categorize_error(ImportError("No module named 'foo'")) == ErrorCategory.PERMANENT

    def test_unknown_defaults_transient(self):
        assert categorize_error(Exception("some random error")) == ErrorCategory.TRANSIENT

    def test_permission_denied(self):
        assert categorize_error(Exception("Permission denied")) == ErrorCategory.PERMANENT

    def test_retry_keyword(self):
        assert categorize_error(Exception("please retry later")) == ErrorCategory.TRANSIENT


# ──────────────────────────────────────────────────────────
# format_error_for_user tests
# ──────────────────────────────────────────────────────────

class TestFormatErrorForUser:
    def test_basic_format(self):
        result = format_error_for_user(ValueError("bad value"))
        assert "ValueError" in result
        assert "bad value" in result

    def test_max_length(self):
        long_msg = "x" * 500
        result = format_error_for_user(Exception(long_msg))
        assert len(result) <= 210  # some margin for HTML entities

    def test_html_escape(self):
        result = format_error_for_user(Exception("<script>alert('xss')</script>"))
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_empty_message(self):
        result = format_error_for_user(Exception(""))
        assert "Exception" in result

    def test_unicode_message(self):
        result = format_error_for_user(Exception("Ошибка подключения"))
        assert "Ошибка подключения" in result


# ──────────────────────────────────────────────────────────
# ErrorCategory enum tests
# ──────────────────────────────────────────────────────────

class TestErrorCategory:
    def test_values(self):
        assert ErrorCategory.TRANSIENT == "transient"
        assert ErrorCategory.PERMANENT == "permanent"
        assert ErrorCategory.TIMEOUT == "timeout"

    def test_all_categories(self):
        assert len(ErrorCategory) == 3


# ──────────────────────────────────────────────────────────
# safe_agent_call tests
# ──────────────────────────────────────────────────────────

def _make_message(text="", user_id=1):
    msg = AsyncMock()
    msg.text = text
    msg.from_user = MagicMock()
    msg.from_user.id = user_id
    msg.chat = MagicMock()
    msg.chat.id = user_id
    msg.answer = AsyncMock()
    msg.answer_chat_action = AsyncMock()
    msg.bot = MagicMock()
    # First call returns status message, subsequent calls are response messages
    status_msg = AsyncMock()
    status_msg.delete = AsyncMock()
    msg.answer.return_value = status_msg
    return msg


class TestSafeAgentCall:
    @pytest.mark.asyncio
    async def test_success_returns_response(self):
        msg = _make_message()
        with patch("src.telegram.bridge.AgentBridge") as mock_bridge:
            mock_bridge.send_to_agent = AsyncMock(return_value="Hello from agent")
            with patch("src.telegram.handlers.commands.keep_typing", new_callable=lambda: lambda m, s: asyncio.sleep(0)):
                result = await safe_agent_call(
                    msg, "manager", "test message",
                    status_text="Testing...",
                )
        assert result == "Hello from agent"

    @pytest.mark.asyncio
    async def test_shows_status_message(self):
        msg = _make_message()
        with patch("src.telegram.bridge.AgentBridge") as mock_bridge:
            mock_bridge.send_to_agent = AsyncMock(return_value="ok")
            with patch("src.telegram.handlers.commands.keep_typing", new_callable=lambda: lambda m, s: asyncio.sleep(0)):
                await safe_agent_call(msg, "manager", "hi", status_text="Думает...")
        msg.answer.assert_any_call("Думает...")

    @pytest.mark.asyncio
    async def test_permanent_error_no_retry(self):
        msg = _make_message()
        with patch("src.telegram.bridge.AgentBridge") as mock_bridge:
            mock_bridge.send_to_agent = AsyncMock(
                side_effect=Exception("401 Unauthorized")
            )
            with patch("src.telegram.handlers.commands.keep_typing", new_callable=lambda: lambda m, s: asyncio.sleep(0)):
                result = await safe_agent_call(
                    msg, "accountant", "test",
                    max_retries=3,
                )
        assert result is None
        # Should only call once (permanent = no retry)
        assert mock_bridge.send_to_agent.call_count == 1

    @pytest.mark.asyncio
    async def test_transient_error_retries(self):
        msg = _make_message()
        with patch("src.telegram.bridge.AgentBridge") as mock_bridge:
            mock_bridge.send_to_agent = AsyncMock(
                side_effect=[Exception("503 Service Unavailable"), "recovered"]
            )
            with patch("src.telegram.handlers.commands.keep_typing", new_callable=lambda: lambda m, s: asyncio.sleep(0)):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    result = await safe_agent_call(
                        msg, "smm", "test",
                        max_retries=2,
                    )
        assert result == "recovered"
        assert mock_bridge.send_to_agent.call_count == 2

    @pytest.mark.asyncio
    async def test_error_sends_user_message(self):
        msg = _make_message()
        with patch("src.telegram.bridge.AgentBridge") as mock_bridge:
            mock_bridge.send_to_agent = AsyncMock(
                side_effect=Exception("Something broke")
            )
            with patch("src.telegram.handlers.commands.keep_typing", new_callable=lambda: lambda m, s: asyncio.sleep(0)):
                result = await safe_agent_call(msg, "manager", "test")
        assert result is None
        # Should have called answer with error
        calls = [str(c) for c in msg.answer.call_args_list]
        assert any("Ошибка" in c for c in calls)

    @pytest.mark.asyncio
    async def test_cleanup_deletes_status(self):
        msg = _make_message()
        status_msg = AsyncMock()
        status_msg.delete = AsyncMock()
        msg.answer.return_value = status_msg
        with patch("src.telegram.bridge.AgentBridge") as mock_bridge:
            mock_bridge.send_to_agent = AsyncMock(return_value="ok")
            with patch("src.telegram.handlers.commands.keep_typing", new_callable=lambda: lambda m, s: asyncio.sleep(0)):
                await safe_agent_call(msg, "manager", "test")
        status_msg.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_passes_bot_and_chat_id(self):
        msg = _make_message()
        bot = MagicMock()
        with patch("src.telegram.bridge.AgentBridge") as mock_bridge:
            mock_bridge.send_to_agent = AsyncMock(return_value="ok")
            with patch("src.telegram.handlers.commands.keep_typing", new_callable=lambda: lambda m, s: asyncio.sleep(0)):
                await safe_agent_call(
                    msg, "manager", "test",
                    bot=bot, chat_id=123,
                )
        call_kwargs = mock_bridge.send_to_agent.call_args[1]
        assert call_kwargs["bot"] == bot
        assert call_kwargs["chat_id"] == 123

    @pytest.mark.asyncio
    async def test_no_bot_no_chat_id(self):
        msg = _make_message()
        with patch("src.telegram.bridge.AgentBridge") as mock_bridge:
            mock_bridge.send_to_agent = AsyncMock(return_value="ok")
            with patch("src.telegram.handlers.commands.keep_typing", new_callable=lambda: lambda m, s: asyncio.sleep(0)):
                await safe_agent_call(msg, "accountant", "test")
        call_kwargs = mock_bridge.send_to_agent.call_args[1]
        assert "bot" not in call_kwargs
        assert "chat_id" not in call_kwargs
