"""Tests for scheduler health monitoring in CEO bot."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.telegram_ceo.scheduler import _notify_job_error, setup_ceo_scheduler
from src.error_handler import format_error_for_user


class TestNotifyJobError:
    @pytest.mark.asyncio
    async def test_sends_error_message(self):
        bot = AsyncMock()
        error = ValueError("test error")
        await _notify_job_error(bot, 123, "test_job", error)
        bot.send_message.assert_called_once()
        call_args = bot.send_message.call_args
        assert call_args[0][0] == 123
        assert "test_job" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_formats_error_safely(self):
        bot = AsyncMock()
        error = RuntimeError("<script>alert(1)</script>")
        await _notify_job_error(bot, 123, "xss_test", error)
        msg = bot.send_message.call_args[0][1]
        assert "<script>" not in msg  # HTML escaped

    @pytest.mark.asyncio
    async def test_does_not_raise_on_send_failure(self):
        bot = AsyncMock()
        bot.send_message.side_effect = Exception("network error")
        error = ValueError("original error")
        # Should not raise
        await _notify_job_error(bot, 123, "failing_job", error)


class TestSchedulerSetup:
    def test_returns_scheduler(self):
        bot = MagicMock()
        config = MagicMock()
        config.allowed_user_ids = [12345]
        config.morning_briefing_hour = 7
        config.weekly_review_day = "sun"
        config.weekly_review_hour = 18
        scheduler = setup_ceo_scheduler(bot, config)
        assert scheduler is not None

    def test_has_jobs(self):
        bot = MagicMock()
        config = MagicMock()
        config.allowed_user_ids = [12345]
        config.morning_briefing_hour = 7
        config.weekly_review_day = "sun"
        config.weekly_review_hour = 18
        scheduler = setup_ceo_scheduler(bot, config)
        jobs = scheduler.get_jobs()
        assert len(jobs) >= 10  # at least 10 jobs expected

    def test_no_users_returns_empty_scheduler(self):
        bot = MagicMock()
        config = MagicMock()
        config.allowed_user_ids = []
        scheduler = setup_ceo_scheduler(bot, config)
        jobs = scheduler.get_jobs()
        assert len(jobs) == 0

    def test_job_ids_include_critical_jobs(self):
        bot = MagicMock()
        config = MagicMock()
        config.allowed_user_ids = [12345]
        config.morning_briefing_hour = 7
        config.weekly_review_day = "sun"
        config.weekly_review_hour = 18
        scheduler = setup_ceo_scheduler(bot, config)
        job_ids = {j.id for j in scheduler.get_jobs()}
        assert "ceo_morning_briefing" in job_ids
        assert "ceo_weekly_review" in job_ids
        assert "proactive_morning" in job_ids
        assert "proactive_midday" in job_ids
        assert "proactive_evening" in job_ids
        assert "evening_report" in job_ids
