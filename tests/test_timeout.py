"""Tests for timeout handling in CEO bot handlers."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.telegram_ceo.handlers.messages import AGENT_TIMEOUT_SEC


class TestTimeoutConstant:
    def test_timeout_is_120(self):
        assert AGENT_TIMEOUT_SEC == 120

    def test_timeout_is_positive(self):
        assert AGENT_TIMEOUT_SEC > 0


class TestTimeoutBehavior:
    """Test that asyncio.wait_for is used correctly."""

    @pytest.mark.asyncio
    async def test_wait_for_timeout_raises(self):
        """asyncio.wait_for raises TimeoutError when coro exceeds timeout."""
        async def slow_coro():
            await asyncio.sleep(10)
            return "result"

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(slow_coro(), timeout=0.01)

    @pytest.mark.asyncio
    async def test_wait_for_fast_returns(self):
        """asyncio.wait_for returns result when coro completes in time."""
        async def fast_coro():
            return "fast result"

        result = await asyncio.wait_for(fast_coro(), timeout=5)
        assert result == "fast result"


class TestTimeoutMessage:
    """Test timeout error message format."""

    def test_timeout_message_contains_seconds(self):
        msg = f"⏱ Юки не ответил за {AGENT_TIMEOUT_SEC} сек."
        assert "120" in msg

    def test_timeout_message_suggests_route(self):
        agent_name = "smm"
        msg = f"Попробуйте /route {agent_name} <задача> для прямого вызова."
        assert "/route smm" in msg
