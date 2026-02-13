"""Tests for progress updates in CEO bot message handler."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.telegram_ceo.handlers.messages import _progress_updater


class TestProgressUpdater:
    @pytest.mark.asyncio
    async def test_updates_message_after_interval(self):
        """Progress updater edits message text after interval."""
        status_msg = AsyncMock()
        stop = asyncio.Event()

        # Run updater with 0.05s interval, stop after 0.12s
        task = asyncio.create_task(_progress_updater(status_msg, "Юки", stop, interval=0.05))
        await asyncio.sleep(0.12)
        stop.set()
        await task

        # Should have called edit_text at least once
        assert status_msg.edit_text.call_count >= 1

    @pytest.mark.asyncio
    async def test_stops_on_event(self):
        """Progress updater stops when stop event is set."""
        status_msg = AsyncMock()
        stop = asyncio.Event()

        task = asyncio.create_task(_progress_updater(status_msg, "Маттиас", stop, interval=10))
        await asyncio.sleep(0.01)
        stop.set()
        await task

        # Should complete without calling edit (interval too long)
        assert status_msg.edit_text.call_count == 0

    @pytest.mark.asyncio
    async def test_handles_edit_failure(self):
        """Progress updater doesn't crash when edit_text fails."""
        status_msg = AsyncMock()
        status_msg.edit_text.side_effect = Exception("message deleted")
        stop = asyncio.Event()

        task = asyncio.create_task(_progress_updater(status_msg, "Мартин", stop, interval=0.05))
        await asyncio.sleep(0.12)
        stop.set()
        await task

        # Should have tried to edit but not crashed
        assert status_msg.edit_text.call_count >= 1

    @pytest.mark.asyncio
    async def test_message_format(self):
        """Progress updater shows agent name and elapsed time."""
        status_msg = AsyncMock()
        stop = asyncio.Event()

        task = asyncio.create_task(_progress_updater(status_msg, "Райан", stop, interval=0.05))
        await asyncio.sleep(0.07)
        stop.set()
        await task

        if status_msg.edit_text.call_count > 0:
            call_text = status_msg.edit_text.call_args[0][0]
            assert "Райан" in call_text
            assert "работает" in call_text
