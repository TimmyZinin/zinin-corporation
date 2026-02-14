"""Tests for CEO bot proactive system integration (keyboards, scheduler, callbacks)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.telegram_ceo.callback_factory import ActionCB, EveningCB


class TestActionKeyboard:
    """Test action_keyboard() and evening_review_keyboard()."""

    def test_action_keyboard_has_two_buttons(self):
        from src.telegram_ceo.keyboards import action_keyboard
        kb = action_keyboard("act_12345678")
        buttons = kb.inline_keyboard
        assert len(buttons) == 1  # 1 row
        assert len(buttons[0]) == 2  # 2 buttons

    def test_action_keyboard_launch_callback(self):
        from src.telegram_ceo.keyboards import action_keyboard
        kb = action_keyboard("act_test")
        launch_btn = kb.inline_keyboard[0][0]
        assert launch_btn.callback_data == ActionCB(action="launch", id="act_test").pack()
        assert "Запустить" in launch_btn.text

    def test_action_keyboard_skip_callback(self):
        from src.telegram_ceo.keyboards import action_keyboard
        kb = action_keyboard("act_test")
        skip_btn = kb.inline_keyboard[0][1]
        assert skip_btn.callback_data == ActionCB(action="skip", id="act_test").pack()
        assert "Пропустить" in skip_btn.text

    def test_evening_review_keyboard_has_two_buttons(self):
        from src.telegram_ceo.keyboards import evening_review_keyboard
        kb = evening_review_keyboard()
        buttons = kb.inline_keyboard
        assert len(buttons) == 1
        assert len(buttons[0]) == 2

    def test_evening_approve_callback(self):
        from src.telegram_ceo.keyboards import evening_review_keyboard
        kb = evening_review_keyboard()
        approve_btn = kb.inline_keyboard[0][0]
        assert approve_btn.callback_data == EveningCB(action="approve").pack()
        assert "Утвердить" in approve_btn.text

    def test_evening_adjust_callback(self):
        from src.telegram_ceo.keyboards import evening_review_keyboard
        kb = evening_review_keyboard()
        adjust_btn = kb.inline_keyboard[0][1]
        assert adjust_btn.callback_data == EveningCB(action="adjust").pack()
        assert "Скорректировать" in adjust_btn.text


class TestSchedulerJobs:
    """Test that new scheduler jobs are registered."""

    def test_scheduler_has_proactive_jobs(self):
        from src.telegram_ceo.scheduler import setup_ceo_scheduler
        from src.telegram_ceo.config import CeoTelegramConfig
        mock_bot = MagicMock()
        config = CeoTelegramConfig(allowed_user_ids=[123])
        scheduler = setup_ceo_scheduler(mock_bot, config)
        job_ids = [j.id for j in scheduler.get_jobs()]
        assert "proactive_morning" in job_ids
        assert "proactive_midday" in job_ids
        assert "proactive_evening" in job_ids

    def test_scheduler_has_comment_digest_job(self):
        from src.telegram_ceo.scheduler import setup_ceo_scheduler
        from src.telegram_ceo.config import CeoTelegramConfig
        mock_bot = MagicMock()
        config = CeoTelegramConfig(allowed_user_ids=[123])
        scheduler = setup_ceo_scheduler(mock_bot, config)
        job_ids = [j.id for j in scheduler.get_jobs()]
        assert "comment_digest" in job_ids

    def test_scheduler_has_competitor_scan_job(self):
        from src.telegram_ceo.scheduler import setup_ceo_scheduler
        from src.telegram_ceo.config import CeoTelegramConfig
        mock_bot = MagicMock()
        config = CeoTelegramConfig(allowed_user_ids=[123])
        scheduler = setup_ceo_scheduler(mock_bot, config)
        job_ids = [j.id for j in scheduler.get_jobs()]
        assert "competitor_scan" in job_ids

    def test_scheduler_without_users_skips_all(self):
        from src.telegram_ceo.scheduler import setup_ceo_scheduler
        from src.telegram_ceo.config import CeoTelegramConfig
        mock_bot = MagicMock()
        config = CeoTelegramConfig(allowed_user_ids=[])
        scheduler = setup_ceo_scheduler(mock_bot, config)
        job_ids = [j.id for j in scheduler.get_jobs()]
        assert "proactive_morning" not in job_ids


class TestEveningAdjustState:
    """Test evening adjust state management."""

    def test_is_in_evening_adjust_mode(self):
        from src.telegram_ceo.handlers.callbacks import (
            _evening_adjust_state, is_in_evening_adjust_mode, consume_evening_adjust_mode
        )
        _evening_adjust_state.clear()
        assert is_in_evening_adjust_mode(123) is False
        _evening_adjust_state.add(123)
        assert is_in_evening_adjust_mode(123) is True

    def test_consume_evening_adjust_mode(self):
        from src.telegram_ceo.handlers.callbacks import (
            _evening_adjust_state, consume_evening_adjust_mode, is_in_evening_adjust_mode
        )
        _evening_adjust_state.clear()
        _evening_adjust_state.add(456)
        assert consume_evening_adjust_mode(456) is True
        assert is_in_evening_adjust_mode(456) is False

    def test_consume_not_active(self):
        from src.telegram_ceo.handlers.callbacks import (
            _evening_adjust_state, consume_evening_adjust_mode
        )
        _evening_adjust_state.clear()
        assert consume_evening_adjust_mode(789) is False


class TestCallbackRegistration:
    """Test that proactive callbacks are registered on the router."""

    def test_action_launch_handler_exists(self):
        from src.telegram_ceo.handlers.callbacks import on_action_launch
        assert callable(on_action_launch)

    def test_action_skip_handler_exists(self):
        from src.telegram_ceo.handlers.callbacks import on_action_skip
        assert callable(on_action_skip)

    def test_evening_approve_handler_exists(self):
        from src.telegram_ceo.handlers.callbacks import on_evening_approve
        assert callable(on_evening_approve)

    def test_evening_adjust_handler_exists(self):
        from src.telegram_ceo.handlers.callbacks import on_evening_adjust
        assert callable(on_evening_adjust)


class TestMessagesImport:
    """Test that messages.py imports the new state functions."""

    def test_imports_evening_adjust(self):
        from src.telegram_ceo.handlers.messages import handle_text
        # Just verify the import doesn't fail
        assert callable(handle_text)


class TestExistingKeyboardsUnchanged:
    """Verify existing keyboards still work after additions."""

    def test_task_menu_keyboard(self):
        from src.telegram_ceo.keyboards import task_menu_keyboard
        kb = task_menu_keyboard()
        assert len(kb.inline_keyboard) == 2

    def test_task_detail_keyboard(self):
        from src.telegram_ceo.keyboards import task_detail_keyboard
        kb = task_detail_keyboard("task1", "TODO")
        assert len(kb.inline_keyboard) >= 1

    def test_escalation_keyboard(self):
        from src.telegram_ceo.keyboards import escalation_keyboard
        kb = escalation_keyboard("task1")
        assert len(kb.inline_keyboard) == 2

    def test_proposal_keyboard(self):
        from src.telegram_ceo.keyboards import proposal_keyboard
        kb = proposal_keyboard("prop1")
        assert len(kb.inline_keyboard) == 2

    def test_diagnostic_keyboard(self):
        from src.telegram_ceo.keyboards import diagnostic_keyboard
        kb = diagnostic_keyboard("diag1")
        assert len(kb.inline_keyboard) == 2


# ═══════════════════════════════════════════════════════════════
# Sprint 10: New proactive scheduler jobs
# ═══════════════════════════════════════════════════════════════

class TestSprint10SchedulerJobs:
    """Test new proactive scheduler jobs added in Sprint 10."""

    def test_sophie_daily_health_job(self):
        from src.telegram_ceo.scheduler import setup_ceo_scheduler
        from src.telegram_ceo.config import CeoTelegramConfig
        mock_bot = MagicMock()
        config = CeoTelegramConfig(allowed_user_ids=[123])
        scheduler = setup_ceo_scheduler(mock_bot, config)
        job_ids = [j.id for j in scheduler.get_jobs()]
        assert "sophie_daily_health" in job_ids

    def test_sophie_weekly_sprint_job(self):
        from src.telegram_ceo.scheduler import setup_ceo_scheduler
        from src.telegram_ceo.config import CeoTelegramConfig
        mock_bot = MagicMock()
        config = CeoTelegramConfig(allowed_user_ids=[123])
        scheduler = setup_ceo_scheduler(mock_bot, config)
        job_ids = [j.id for j in scheduler.get_jobs()]
        assert "sophie_weekly_sprint" in job_ids

    def test_ryan_visual_prep_job(self):
        from src.telegram_ceo.scheduler import setup_ceo_scheduler
        from src.telegram_ceo.config import CeoTelegramConfig
        mock_bot = MagicMock()
        config = CeoTelegramConfig(allowed_user_ids=[123])
        scheduler = setup_ceo_scheduler(mock_bot, config)
        job_ids = [j.id for j in scheduler.get_jobs()]
        assert "ryan_visual_prep" in job_ids

    def test_alexey_content_pulse_job(self):
        from src.telegram_ceo.scheduler import setup_ceo_scheduler
        from src.telegram_ceo.config import CeoTelegramConfig
        mock_bot = MagicMock()
        config = CeoTelegramConfig(allowed_user_ids=[123])
        scheduler = setup_ceo_scheduler(mock_bot, config)
        job_ids = [j.id for j in scheduler.get_jobs()]
        assert "alexey_content_pulse" in job_ids

    def test_alexey_revenue_pulse_job(self):
        from src.telegram_ceo.scheduler import setup_ceo_scheduler
        from src.telegram_ceo.config import CeoTelegramConfig
        mock_bot = MagicMock()
        config = CeoTelegramConfig(allowed_user_ids=[123])
        scheduler = setup_ceo_scheduler(mock_bot, config)
        job_ids = [j.id for j in scheduler.get_jobs()]
        assert "alexey_revenue_pulse" in job_ids

    def test_scheduler_has_at_least_20_jobs(self):
        from src.telegram_ceo.scheduler import setup_ceo_scheduler
        from src.telegram_ceo.config import CeoTelegramConfig
        mock_bot = MagicMock()
        config = CeoTelegramConfig(allowed_user_ids=[123])
        scheduler = setup_ceo_scheduler(mock_bot, config)
        assert len(scheduler.get_jobs()) >= 20
