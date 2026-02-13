"""Tests for CEO Alexey Telegram bot modules."""

import asyncio
import inspect
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ──────────────────────────────────────────────────────────
# Test: CeoTelegramConfig
# ──────────────────────────────────────────────────────────

class TestCeoTelegramConfig:
    def test_default_values(self):
        from src.telegram_ceo.config import CeoTelegramConfig
        cfg = CeoTelegramConfig()
        assert cfg.bot_token == ""
        assert cfg.allowed_user_ids == []
        assert cfg.default_agent == "manager"
        assert cfg.morning_briefing_hour == 8
        assert cfg.weekly_review_day == "mon"
        assert cfg.weekly_review_hour == 10

    def test_from_env(self, monkeypatch):
        from src.telegram_ceo.config import CeoTelegramConfig
        monkeypatch.setenv("TELEGRAM_CEO_BOT_TOKEN", "test-token-123")
        monkeypatch.setenv("TELEGRAM_CEO_ALLOWED_USERS", "111,222")
        monkeypatch.setenv("TG_CEO_MORNING_HOUR", "7")
        monkeypatch.setenv("TG_CEO_WEEKLY_HOUR", "11")
        cfg = CeoTelegramConfig.from_env()
        assert cfg.bot_token == "test-token-123"
        assert cfg.allowed_user_ids == [111, 222]
        assert cfg.morning_briefing_hour == 7
        assert cfg.weekly_review_hour == 11

    def test_from_env_empty(self, monkeypatch):
        from src.telegram_ceo.config import CeoTelegramConfig
        monkeypatch.delenv("TELEGRAM_CEO_BOT_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_CEO_ALLOWED_USERS", raising=False)
        cfg = CeoTelegramConfig.from_env()
        assert cfg.bot_token == ""
        assert cfg.allowed_user_ids == []

    def test_from_env_single_user(self, monkeypatch):
        from src.telegram_ceo.config import CeoTelegramConfig
        monkeypatch.setenv("TELEGRAM_CEO_BOT_TOKEN", "tk")
        monkeypatch.setenv("TELEGRAM_CEO_ALLOWED_USERS", "555")
        cfg = CeoTelegramConfig.from_env()
        assert cfg.allowed_user_ids == [555]


# ──────────────────────────────────────────────────────────
# Test: Bridge — new methods
# ──────────────────────────────────────────────────────────

class TestBridgeCeoMethods:
    def test_run_strategic_review_exists(self):
        from src.telegram.bridge import AgentBridge
        assert hasattr(AgentBridge, "run_strategic_review")
        assert asyncio.iscoroutinefunction(AgentBridge.run_strategic_review)

    def test_run_corporation_report_exists(self):
        from src.telegram.bridge import AgentBridge
        assert hasattr(AgentBridge, "run_corporation_report")
        assert asyncio.iscoroutinefunction(AgentBridge.run_corporation_report)

    def test_run_strategic_review_calls_corp(self):
        """Verify run_strategic_review calls corp.strategic_review()."""
        from src.telegram.bridge import AgentBridge
        src = inspect.getsource(AgentBridge.run_strategic_review)
        assert "strategic_review" in src
        assert "asyncio.to_thread" in src

    def test_run_corporation_report_calls_corp(self):
        """Verify run_corporation_report calls corp.full_corporation_report()."""
        from src.telegram.bridge import AgentBridge
        src = inspect.getsource(AgentBridge.run_corporation_report)
        assert "full_corporation_report" in src
        assert "asyncio.to_thread" in src

    def test_send_to_agent_supports_manager(self):
        """AgentBridge.send_to_agent default is accountant but supports any agent_name."""
        from src.telegram.bridge import AgentBridge
        sig = inspect.signature(AgentBridge.send_to_agent)
        assert "agent_name" in sig.parameters

    def test_run_generate_post_exists(self):
        from src.telegram.bridge import AgentBridge
        assert hasattr(AgentBridge, "run_generate_post")
        assert asyncio.iscoroutinefunction(AgentBridge.run_generate_post)

    def test_run_content_review_exists(self):
        from src.telegram.bridge import AgentBridge
        assert hasattr(AgentBridge, "run_content_review")
        assert asyncio.iscoroutinefunction(AgentBridge.run_content_review)

    def test_run_linkedin_status_exists(self):
        from src.telegram.bridge import AgentBridge
        assert hasattr(AgentBridge, "run_linkedin_status")
        assert asyncio.iscoroutinefunction(AgentBridge.run_linkedin_status)

    def test_run_generate_post_calls_corp(self):
        from src.telegram.bridge import AgentBridge
        src = inspect.getsource(AgentBridge.run_generate_post)
        assert "generate_post" in src

    def test_run_content_review_calls_corp(self):
        from src.telegram.bridge import AgentBridge
        src = inspect.getsource(AgentBridge.run_content_review)
        assert "content_review" in src


# ──────────────────────────────────────────────────────────
# Test: Exported typing helpers
# ──────────────────────────────────────────────────────────

class TestTypingHelpers:
    def test_keep_typing_importable(self):
        from src.telegram.handlers.commands import keep_typing
        assert asyncio.iscoroutinefunction(keep_typing)

    def test_run_with_typing_importable(self):
        from src.telegram.handlers.commands import run_with_typing
        assert asyncio.iscoroutinefunction(run_with_typing)


# ──────────────────────────────────────────────────────────
# Test: CEO Commands
# ──────────────────────────────────────────────────────────

class TestCeoCommands:
    def test_commands_module_has_router(self):
        from src.telegram_ceo.handlers.commands import router
        assert router is not None

    def test_start_command_exists(self):
        from src.telegram_ceo.handlers.commands import cmd_start
        assert asyncio.iscoroutinefunction(cmd_start)

    def test_review_command_exists(self):
        from src.telegram_ceo.handlers.commands import cmd_review
        assert asyncio.iscoroutinefunction(cmd_review)

    def test_report_command_exists(self):
        from src.telegram_ceo.handlers.commands import cmd_report
        assert asyncio.iscoroutinefunction(cmd_report)

    def test_status_command_exists(self):
        from src.telegram_ceo.handlers.commands import cmd_status
        assert asyncio.iscoroutinefunction(cmd_status)

    def test_delegate_command_exists(self):
        from src.telegram_ceo.handlers.commands import cmd_delegate
        assert asyncio.iscoroutinefunction(cmd_delegate)

    def test_help_command_exists(self):
        from src.telegram_ceo.handlers.commands import cmd_help
        assert asyncio.iscoroutinefunction(cmd_help)

    def test_content_command_exists(self):
        from src.telegram_ceo.handlers.commands import cmd_content
        assert asyncio.iscoroutinefunction(cmd_content)

    def test_linkedin_command_exists(self):
        from src.telegram_ceo.handlers.commands import cmd_linkedin
        assert asyncio.iscoroutinefunction(cmd_linkedin)

    def test_valid_agents_includes_specialists(self):
        from src.telegram_ceo.handlers.commands import VALID_AGENTS
        assert "accountant" in VALID_AGENTS
        assert "automator" in VALID_AGENTS
        assert "smm" in VALID_AGENTS

    @pytest.mark.asyncio
    async def test_start_sends_ceo_greeting(self):
        from src.telegram_ceo.handlers.commands import cmd_start
        msg = AsyncMock()
        await cmd_start(msg)
        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "Алексей" in text
        assert "CEO" in text

    @pytest.mark.asyncio
    async def test_start_mentions_yuki(self):
        from src.telegram_ceo.handlers.commands import cmd_start
        msg = AsyncMock()
        await cmd_start(msg)
        text = msg.answer.call_args[0][0]
        assert "Юки" in text or "/content" in text

    @pytest.mark.asyncio
    async def test_help_lists_all_commands(self):
        from src.telegram_ceo.handlers.commands import cmd_help
        msg = AsyncMock()
        await cmd_help(msg)
        text = msg.answer.call_args[0][0]
        assert "/review" in text
        assert "/report" in text
        assert "/status" in text
        assert "/delegate" in text
        assert "/content" in text
        assert "/linkedin" in text
        assert "Юки" in text

    @pytest.mark.asyncio
    async def test_status_no_llm_call(self):
        """Status command should NOT call AgentBridge (no LLM)."""
        from src.telegram_ceo.handlers.commands import cmd_status
        msg = AsyncMock()
        with patch("src.telegram_ceo.handlers.commands.get_all_statuses", return_value={
            "manager": {"status": "idle", "queued_tasks": 0},
            "accountant": {"status": "idle", "queued_tasks": 1},
            "automator": {"status": "working", "queued_tasks": 0},
            "smm": {"status": "idle", "queued_tasks": 0},
        }), patch("src.telegram_ceo.handlers.commands.get_agent_task_count", return_value=2):
            await cmd_status(msg)
        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "Алексей" in text or "CEO" in text
        assert "Маттиас" in text or "CFO" in text

    @pytest.mark.asyncio
    async def test_delegate_no_args_shows_help(self):
        from src.telegram_ceo.handlers.commands import cmd_delegate
        msg = AsyncMock()
        msg.text = "/delegate"
        await cmd_delegate(msg)
        text = msg.answer.call_args[0][0]
        assert "Формат" in text or "delegate" in text.lower()

    @pytest.mark.asyncio
    async def test_delegate_unknown_agent_error(self):
        from src.telegram_ceo.handlers.commands import cmd_delegate
        msg = AsyncMock()
        msg.text = "/delegate unknown_agent do something"
        await cmd_delegate(msg)
        text = msg.answer.call_args[0][0]
        assert "Неизвестный" in text or "unknown" in text.lower()

    @pytest.mark.asyncio
    async def test_delegate_valid_agent_calls_bridge(self):
        from src.telegram_ceo.handlers.commands import cmd_delegate
        msg = AsyncMock()
        msg.text = "/delegate accountant Подготовь бюджет на Q1"
        msg.answer = AsyncMock(return_value=AsyncMock(delete=AsyncMock()))
        msg.answer_chat_action = AsyncMock()

        with patch("src.telegram_ceo.handlers.commands.run_with_typing") as mock_rwt:
            mock_rwt.return_value = None
            await cmd_delegate(msg)
            mock_rwt.assert_called_once()
            call_args = mock_rwt.call_args
            assert call_args[0][0] is msg
            assert "30–60 сек" in call_args[0][2]

    @pytest.mark.asyncio
    async def test_review_calls_strategic_review(self):
        from src.telegram_ceo.handlers.commands import cmd_review
        msg = AsyncMock()
        with patch("src.telegram_ceo.handlers.commands.run_with_typing") as mock_rwt:
            mock_rwt.return_value = None
            await cmd_review(msg)
            mock_rwt.assert_called_once()
            assert "стратегический" in mock_rwt.call_args[0][2].lower()

    @pytest.mark.asyncio
    async def test_report_calls_corporation_report(self):
        from src.telegram_ceo.handlers.commands import cmd_report
        msg = AsyncMock()
        with patch("src.telegram_ceo.handlers.commands.run_with_typing") as mock_rwt:
            mock_rwt.return_value = None
            await cmd_report(msg)
            mock_rwt.assert_called_once()
            assert "отчёт" in mock_rwt.call_args[0][2].lower()

    @pytest.mark.asyncio
    async def test_content_no_topic_shows_help(self):
        from src.telegram_ceo.handlers.commands import cmd_content
        msg = AsyncMock()
        msg.text = "/content"
        await cmd_content(msg)
        text = msg.answer.call_args[0][0]
        assert "Формат" in text or "тема" in text.lower()

    @pytest.mark.asyncio
    async def test_content_with_topic_calls_yuki(self):
        from src.telegram_ceo.handlers.commands import cmd_content
        msg = AsyncMock()
        msg.text = "/content AI-агенты в бизнесе"
        with patch("src.telegram_ceo.handlers.commands.run_with_typing") as mock_rwt:
            mock_rwt.return_value = None
            await cmd_content(msg)
            mock_rwt.assert_called_once()
            wait_msg = mock_rwt.call_args[0][2]
            assert "Юки" in wait_msg

    @pytest.mark.asyncio
    async def test_linkedin_calls_yuki(self):
        from src.telegram_ceo.handlers.commands import cmd_linkedin
        msg = AsyncMock()
        with patch("src.telegram_ceo.handlers.commands.run_with_typing") as mock_rwt:
            mock_rwt.return_value = None
            await cmd_linkedin(msg)
            mock_rwt.assert_called_once()
            wait_msg = mock_rwt.call_args[0][2]
            assert "Юки" in wait_msg or "LinkedIn" in wait_msg


# ──────────────────────────────────────────────────────────
# Test: CEO Messages
# ──────────────────────────────────────────────────────────

class TestCeoMessages:
    def test_messages_module_has_router(self):
        from src.telegram_ceo.handlers.messages import router
        assert router is not None

    def test_handle_text_exists(self):
        from src.telegram_ceo.handlers.messages import handle_text
        assert asyncio.iscoroutinefunction(handle_text)

    def test_format_context_function(self):
        from src.telegram_ceo.handlers.messages import _format_context
        result = _format_context([
            {"role": "user", "text": "Привет"},
            {"role": "assistant", "text": "Добрый день"},
        ])
        assert "Тим: Привет" in result
        assert "Алексей: Добрый день" in result

    def test_format_context_empty(self):
        from src.telegram_ceo.handlers.messages import _format_context
        result = _format_context([])
        assert result == ""

    def test_format_context_truncates_long_assistant(self):
        from src.telegram_ceo.handlers.messages import _format_context
        long_text = "A" * 2000
        result = _format_context([{"role": "assistant", "text": long_text}])
        assert len(result) <= 810  # "Алексей: " + 800 chars

    def test_max_context_is_20(self):
        from src.telegram_ceo.handlers.messages import MAX_CONTEXT
        assert MAX_CONTEXT == 20

    def test_agent_default_is_manager(self):
        """CEO messages should default to 'manager' agent."""
        from src.telegram_ceo.handlers import messages
        src = inspect.getsource(messages.handle_text)
        assert 'agent_name = "manager"' in src


# ──────────────────────────────────────────────────────────
# Test: CEO Scheduler
# ──────────────────────────────────────────────────────────

class TestCeoScheduler:
    def test_setup_ceo_scheduler_importable(self):
        from src.telegram_ceo.scheduler import setup_ceo_scheduler
        assert callable(setup_ceo_scheduler)

    def test_scheduler_no_users_no_jobs(self):
        from src.telegram_ceo.scheduler import setup_ceo_scheduler
        from src.telegram_ceo.config import CeoTelegramConfig
        bot = MagicMock()
        config = CeoTelegramConfig(allowed_user_ids=[])
        scheduler = setup_ceo_scheduler(bot, config)
        jobs = scheduler.get_jobs()
        assert len(jobs) == 0

    def test_scheduler_with_users_has_jobs(self):
        from src.telegram_ceo.scheduler import setup_ceo_scheduler
        from src.telegram_ceo.config import CeoTelegramConfig
        bot = MagicMock()
        config = CeoTelegramConfig(allowed_user_ids=[123])
        scheduler = setup_ceo_scheduler(bot, config)
        jobs = scheduler.get_jobs()
        assert len(jobs) == 17
        job_ids = {j.id for j in jobs}
        assert "ceo_morning_briefing" in job_ids
        assert "ceo_weekly_review" in job_ids
        assert "cto_api_health_check" in job_ids
        assert "cto_improvement_09" in job_ids
        assert "cto_improvement_13" in job_ids
        assert "cto_improvement_17" in job_ids
        assert "cto_improvement_21" in job_ids
        assert "task_pool_archive" in job_ids
        assert "cto_orphan_patrol" in job_ids
        assert "daily_analytics" in job_ids
        assert "evening_report" in job_ids
        assert "weekly_digest" in job_ids

    def test_morning_briefing_does_not_call_llm(self):
        """Morning briefing should use activity_tracker, not AgentBridge."""
        from src.telegram_ceo import scheduler
        src = inspect.getsource(scheduler.morning_briefing if hasattr(scheduler, "morning_briefing") else scheduler.setup_ceo_scheduler)
        # The morning_briefing function uses get_all_statuses, not AgentBridge
        assert "get_all_statuses" in src

    def test_weekly_review_calls_corporation_report(self):
        """Weekly review should use AgentBridge.run_corporation_report (full report from all agents)."""
        from src.telegram_ceo import scheduler
        src = inspect.getsource(scheduler.setup_ceo_scheduler)
        assert "run_corporation_report" in src


# ──────────────────────────────────────────────────────────
# Test: CEO Bot
# ──────────────────────────────────────────────────────────

class TestCeoBot:
    def test_main_importable(self):
        from src.telegram_ceo.bot import main
        assert asyncio.iscoroutinefunction(main)

    def test_bot_imports_auth_middleware(self):
        """CEO bot should reuse AuthMiddleware from Маттиас bot."""
        from src.telegram_ceo import bot
        src = inspect.getsource(bot)
        assert "AuthMiddleware" in src
        assert "telegram.bot" in src

    def test_bot_registers_commands_and_messages(self):
        from src.telegram_ceo import bot
        src = inspect.getsource(bot.main)
        assert "commands.router" in src
        assert "messages.router" in src

    @pytest.mark.asyncio
    async def test_main_returns_without_token(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_CEO_BOT_TOKEN", raising=False)
        from src.telegram_ceo.bot import main
        with patch("src.telegram_ceo.bot.CeoTelegramConfig.from_env") as mock_cfg:
            mock_cfg.return_value = MagicMock(bot_token="", allowed_user_ids=[])
            # Should return early without error
            await main()


# ──────────────────────────────────────────────────────────
# Test: Entry Point
# ──────────────────────────────────────────────────────────

class TestEntryPoint:
    def test_run_alexey_bot_exists(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "run_alexey_bot.py",
        )
        assert os.path.exists(path)

    def test_run_alexey_bot_imports_ceo_main(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "run_alexey_bot.py",
        )
        with open(path) as f:
            content = f.read()
        assert "from src.telegram_ceo.bot import main" in content


# ──────────────────────────────────────────────────────────
# Test: Infrastructure
# ──────────────────────────────────────────────────────────

class TestInfrastructure:
    def test_start_sh_has_ceo_bot(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "start.sh",
        )
        with open(path) as f:
            content = f.read()
        assert "TELEGRAM_CEO_BOT_TOKEN" in content
        assert "run_alexey_bot.py" in content

    def test_dockerfile_copies_alexey_bot(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "Dockerfile",
        )
        with open(path) as f:
            content = f.read()
        assert "run_alexey_bot.py" in content

    def test_start_sh_cleans_up_ceo_pid(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "start.sh",
        )
        with open(path) as f:
            content = f.read()
        assert "CEO_BOT_PID" in content


# ──────────────────────────────────────────────────────────
# Test: API Diagnostics System
# ──────────────────────────────────────────────────────────

class TestAPIDiagnostics:
    """Tests for CTO API diagnostic system with action buttons."""

    def test_diagnostic_keyboard_exists(self):
        from src.telegram_ceo.keyboards import diagnostic_keyboard
        kb = diagnostic_keyboard("diag_test_123")
        assert kb is not None
        assert len(kb.inline_keyboard) == 2  # 2 rows
        assert len(kb.inline_keyboard[0]) == 2  # Row 1: recheck + detail
        assert len(kb.inline_keyboard[1]) == 1  # Row 2: ack

    def test_diagnostic_keyboard_callback_data(self):
        from src.telegram_ceo.keyboards import diagnostic_keyboard
        kb = diagnostic_keyboard("diag_20260208_1430")
        assert kb.inline_keyboard[0][0].callback_data == "api_recheck:diag_20260208_1430"
        assert kb.inline_keyboard[0][1].callback_data == "api_detail:diag_20260208_1430"
        assert kb.inline_keyboard[1][0].callback_data == "api_ack:diag_20260208_1430"

    def test_diagnostic_storage_helpers_exist(self):
        from src.telegram_ceo.handlers.callbacks import (
            _load_diagnostics, _save_diagnostics, _find_diagnostic, _update_diagnostic,
        )
        assert callable(_load_diagnostics)
        assert callable(_save_diagnostics)
        assert callable(_find_diagnostic)
        assert callable(_update_diagnostic)

    def test_load_diagnostics_empty(self):
        from src.telegram_ceo.handlers.callbacks import _load_diagnostics
        with patch(
            "src.telegram_ceo.handlers.callbacks._diagnostic_path",
            return_value="/tmp/_test_diag_empty.json",
        ):
            import os
            if os.path.exists("/tmp/_test_diag_empty.json"):
                os.remove("/tmp/_test_diag_empty.json")
            data = _load_diagnostics()
            assert "diagnostics" in data
            assert "stats" in data
            assert data["diagnostics"] == []

    def test_save_and_load_diagnostics(self):
        from src.telegram_ceo.handlers.callbacks import (
            _load_diagnostics, _save_diagnostics, _find_diagnostic,
        )
        import os
        test_path = "/tmp/_test_diag_roundtrip.json"
        with patch(
            "src.telegram_ceo.handlers.callbacks._diagnostic_path",
            return_value=test_path,
        ):
            if os.path.exists(test_path):
                os.remove(test_path)
            data = _load_diagnostics()
            data["diagnostics"].append({
                "id": "diag_test_001",
                "timestamp": "2026-02-08 14:30:00",
                "failed_apis": ["moralis"],
                "results": {"moralis": {"ok": False, "error": "HTTP 401"}},
                "analysis": "Test analysis",
                "status": "pending",
            })
            _save_diagnostics(data)

            found = _find_diagnostic("diag_test_001")
            assert found is not None
            assert found["analysis"] == "Test analysis"

            assert _find_diagnostic("nonexistent") is None

            os.remove(test_path)

    def test_diagnostics_cap_at_100(self):
        from src.telegram_ceo.handlers.callbacks import _load_diagnostics, _save_diagnostics
        import os
        test_path = "/tmp/_test_diag_cap.json"
        with patch(
            "src.telegram_ceo.handlers.callbacks._diagnostic_path",
            return_value=test_path,
        ):
            if os.path.exists(test_path):
                os.remove(test_path)
            data = _load_diagnostics()
            for i in range(120):
                data["diagnostics"].append({"id": f"diag_{i}", "status": "pending"})
            _save_diagnostics(data)

            reloaded = _load_diagnostics()
            assert len(reloaded["diagnostics"]) == 100
            # Last 100 kept (IDs 20-119)
            assert reloaded["diagnostics"][0]["id"] == "diag_20"

            os.remove(test_path)

    def test_api_recheck_handler_exists(self):
        from src.telegram_ceo.handlers.callbacks import on_api_recheck
        assert asyncio.iscoroutinefunction(on_api_recheck)

    def test_api_detail_handler_exists(self):
        from src.telegram_ceo.handlers.callbacks import on_api_detail
        assert asyncio.iscoroutinefunction(on_api_detail)

    def test_api_ack_handler_exists(self):
        from src.telegram_ceo.handlers.callbacks import on_api_ack
        assert asyncio.iscoroutinefunction(on_api_ack)

    def test_scheduler_uses_diagnostic_keyboard(self):
        from src.telegram_ceo import scheduler
        src = inspect.getsource(scheduler.setup_ceo_scheduler)
        assert "diagnostic_keyboard" in src
        assert "_call_llm_tech" in src
        assert "_check_single_api" in src

    def test_scheduler_has_llm_cooldown(self):
        from src.telegram_ceo import scheduler
        src = inspect.getsource(scheduler.setup_ceo_scheduler)
        assert "last_analysis" in src
        assert "timedelta(minutes=15)" in src

    def test_scheduler_has_analytics_job(self):
        from src.telegram_ceo import scheduler
        src = inspect.getsource(scheduler.setup_ceo_scheduler)
        assert "daily_analytics" in src
        assert "format_analytics_report" in src

    def test_scheduler_has_evening_report(self):
        from src.telegram_ceo import scheduler
        src = inspect.getsource(scheduler.setup_ceo_scheduler)
        assert "evening_report" in src

    def test_scheduler_has_weekly_digest(self):
        from src.telegram_ceo import scheduler
        src = inspect.getsource(scheduler.setup_ceo_scheduler)
        assert "weekly_digest" in src
        assert "format_weekly_digest" in src


# ──────────────────────────────────────────────────────────
# NLU integration in message handler
# ──────────────────────────────────────────────────────────

class TestCeoNLUIntegration:
    def test_message_handler_has_nlu(self):
        from src.telegram_ceo.handlers import messages
        src = inspect.getsource(messages.handle_text)
        assert "detect_intent" in src
        assert "detect_agent" in src

    def test_execute_intent_exists(self):
        from src.telegram_ceo.handlers.messages import _execute_intent
        assert asyncio.iscoroutinefunction(_execute_intent)

    def test_agent_labels_all_agents(self):
        from src.telegram_ceo.handlers.messages import _AGENT_LABELS
        assert "manager" in _AGENT_LABELS
        assert "accountant" in _AGENT_LABELS
        assert "smm" in _AGENT_LABELS
        assert "automator" in _AGENT_LABELS

    def test_nlu_routing_in_handler(self):
        """Message handler should route to non-manager agents via NLU."""
        from src.telegram_ceo.handlers import messages
        src = inspect.getsource(messages.handle_text)
        assert "agent_target" in src
        assert "agent_name" in src


# ──────────────────────────────────────────────────────────
# Voice handler (CP-008)
# ──────────────────────────────────────────────────────────

class TestCeoVoiceHandler:
    def test_voice_handler_exists(self):
        from src.telegram_ceo.handlers.messages import handle_voice
        assert asyncio.iscoroutinefunction(handle_voice)

    def test_voice_handler_uses_transcribe(self):
        from src.telegram_ceo.handlers import messages
        src = inspect.getsource(messages.handle_voice)
        assert "transcribe_voice" in src
        assert "convert_ogg_to_wav" in src

    def test_voice_handler_checks_availability(self):
        from src.telegram_ceo.handlers import messages
        src = inspect.getsource(messages.handle_voice)
        assert "is_voice_available" in src

    def test_voice_handler_has_brain_dump_check(self):
        from src.telegram_ceo.handlers import messages
        src = inspect.getsource(messages.handle_voice)
        assert "is_brain_dump" in src
        assert "parse_brain_dump" in src

    def test_voice_handler_cleans_up_files(self):
        from src.telegram_ceo.handlers import messages
        src = inspect.getsource(messages.handle_voice)
        assert "os.unlink" in src

    def test_voice_handler_forwards_to_agent(self):
        from src.telegram_ceo.handlers import messages
        src = inspect.getsource(messages.handle_voice)
        assert "AgentBridge" in src

    def test_voice_handler_shows_transcription(self):
        from src.telegram_ceo.handlers import messages
        src = inspect.getsource(messages.handle_voice)
        assert "Распознано" in src


# ──────────────────────────────────────────────────────────
# /route command (CP-003)
# ──────────────────────────────────────────────────────────

class TestRouteCommand:
    def test_route_handler_exists(self):
        from src.telegram_ceo.handlers.commands import cmd_route
        assert asyncio.iscoroutinefunction(cmd_route)

    def test_route_has_alias_map(self):
        from src.telegram_ceo.handlers import commands
        src = inspect.getsource(commands.cmd_route)
        assert "alias_map" in src
        assert "cfo" in src
        assert "cto" in src

    def test_route_sends_to_agent(self):
        from src.telegram_ceo.handlers import commands
        src = inspect.getsource(commands.cmd_route)
        assert "AgentBridge" in src


# ──────────────────────────────────────────────────────────
# /analytics command (CP-001)
# ──────────────────────────────────────────────────────────

class TestAnalyticsCommand:
    def test_analytics_handler_exists(self):
        from src.telegram_ceo.handlers.commands import cmd_analytics
        assert asyncio.iscoroutinefunction(cmd_analytics)

    def test_analytics_uses_report(self):
        from src.telegram_ceo.handlers import commands
        src = inspect.getsource(commands.cmd_analytics)
        assert "format_analytics_report" in src

    def test_analytics_custom_hours(self):
        from src.telegram_ceo.handlers import commands
        src = inspect.getsource(commands.cmd_analytics)
        assert "hours" in src
