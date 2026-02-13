"""Tests for Sprint 6: scheduler import fixes + CEO image sender + CEO bot refactor."""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.telegram_ceo.handlers.commands import VALID_AGENTS
from src.telegram_ceo.handlers.messages import _AGENT_LABELS, AGENT_TIMEOUT_SEC
from src.error_handler import format_error_for_user


# ── Scheduler Import Fixes ────────────────────────────────────


class TestSchedulerImports:
    """Verify fixed imports in scheduler.py resolve correctly."""

    def test_keyboards_import_from_same_package(self):
        """action_keyboard imports from telegram_ceo.keyboards (not src.keyboards)."""
        from src.telegram_ceo.keyboards import action_keyboard
        assert callable(action_keyboard)

    def test_evening_review_keyboard_import(self):
        from src.telegram_ceo.keyboards import evening_review_keyboard
        assert callable(evening_review_keyboard)

    def test_task_pool_import_path(self):
        """task_pool imports from src.task_pool (not src.src.task_pool)."""
        from src.task_pool import get_all_tasks, TaskStatus
        assert callable(get_all_tasks)
        assert hasattr(TaskStatus, "TODO")

    def test_proactive_morning_import_chain(self):
        """All imports in proactive_morning() are valid."""
        from src.revenue_tracker import add_daily_snapshot, format_revenue_summary
        from src.proactive_planner import generate_morning_plan, format_morning_message
        from src.telegram_ceo.keyboards import action_keyboard
        assert callable(add_daily_snapshot)
        assert callable(generate_morning_plan)
        assert callable(action_keyboard)

    def test_proactive_midday_import_chain(self):
        """All imports in proactive_midday() are valid."""
        from src.proactive_planner import generate_midday_check, format_midday_message
        from src.telegram_ceo.keyboards import action_keyboard
        assert callable(generate_midday_check)
        assert callable(action_keyboard)

    def test_proactive_evening_import_chain(self):
        """All imports in proactive_evening() are valid."""
        from src.proactive_planner import generate_evening_review, format_evening_message
        from src.telegram_ceo.keyboards import evening_review_keyboard
        assert callable(generate_evening_review)
        assert callable(evening_review_keyboard)

    def test_evening_report_import_chain(self):
        """All imports in evening_report() are valid."""
        from src.analytics import get_agent_activity_report, get_cost_estimates
        from src.task_pool import get_all_tasks, TaskStatus
        assert callable(get_agent_activity_report)
        assert callable(get_cost_estimates)

    def test_scheduler_registers_all_proactive_jobs(self):
        from src.telegram_ceo.scheduler import setup_ceo_scheduler
        from src.telegram_ceo.config import CeoTelegramConfig
        mock_bot = MagicMock()
        config = CeoTelegramConfig(allowed_user_ids=[123])
        scheduler = setup_ceo_scheduler(mock_bot, config)
        job_ids = [j.id for j in scheduler.get_jobs()]
        for job_id in ["proactive_morning", "proactive_midday", "proactive_evening"]:
            assert job_id in job_ids, f"Job {job_id} not registered"

    def test_no_triple_dot_imports_in_scheduler(self):
        """Ensure no '...' (triple-dot) relative imports exist in scheduler.py."""
        import inspect
        from src.telegram_ceo import scheduler
        source = inspect.getsource(scheduler)
        assert "from ..." not in source, "Found triple-dot import in scheduler.py"

    def test_keyboard_imports_use_single_dot(self):
        """Ensure keyboard imports in scheduler use single dot (same package)."""
        import inspect
        from src.telegram_ceo import scheduler
        source = inspect.getsource(scheduler)
        # All keyboard imports should be from .keyboards, not ..keyboards
        import re
        wrong = re.findall(r"from \.\.keyboards import", source)
        assert len(wrong) == 0, f"Found {len(wrong)} wrong keyboard imports (..keyboards)"


# ── Image Sender ──────────────────────────────────────────────


class TestExtractImagePaths:
    """Test image path extraction from agent responses."""

    def test_extract_png_path(self):
        from src.telegram_ceo.image_sender import extract_image_paths
        text = "Изображение сохранено: /data/design_images/gen_brand_20260213_123456_abc.png"
        paths = extract_image_paths(text)
        assert len(paths) == 1
        assert paths[0] == "/data/design_images/gen_brand_20260213_123456_abc.png"

    def test_extract_jpg_path(self):
        from src.telegram_ceo.image_sender import extract_image_paths
        text = "Chart saved to /data/design_images/chart_bar_20260213.jpg done"
        paths = extract_image_paths(text)
        assert len(paths) == 1
        assert "/data/design_images/chart_bar_20260213.jpg" in paths[0]

    def test_extract_yuki_image_path(self):
        from src.telegram_ceo.image_sender import extract_image_paths
        text = "Картинка: /data/yuki_images/yuki_1707834567.png"
        paths = extract_image_paths(text)
        assert len(paths) == 1

    def test_extract_multiple_paths(self):
        from src.telegram_ceo.image_sender import extract_image_paths
        text = (
            "Image 1: /data/design_images/img1.png\n"
            "Image 2: /data/design_images/img2.jpg\n"
            "No image here."
        )
        paths = extract_image_paths(text)
        assert len(paths) == 2

    def test_no_paths_in_normal_text(self):
        from src.telegram_ceo.image_sender import extract_image_paths
        text = "Отчёт готов. Выручка составила $500. Рост 15%."
        paths = extract_image_paths(text)
        assert len(paths) == 0

    def test_tmp_path_extracted(self):
        from src.telegram_ceo.image_sender import extract_image_paths
        text = "File at /tmp/generated_chart.png"
        paths = extract_image_paths(text)
        assert len(paths) == 1

    def test_webp_extension(self):
        from src.telegram_ceo.image_sender import extract_image_paths
        text = "/data/design_images/banner.webp"
        paths = extract_image_paths(text)
        assert len(paths) == 1

    def test_gif_extension(self):
        from src.telegram_ceo.image_sender import extract_image_paths
        text = "Animation: /data/design_images/anim.gif"
        paths = extract_image_paths(text)
        assert len(paths) == 1

    def test_non_image_extension_ignored(self):
        from src.telegram_ceo.image_sender import extract_image_paths
        text = "File: /data/design_images/document.pdf"
        paths = extract_image_paths(text)
        assert len(paths) == 0

    def test_path_with_hyphens_and_underscores(self):
        from src.telegram_ceo.image_sender import extract_image_paths
        text = "/data/design_images/gen_brand-v2_20260213_abc-123.png"
        paths = extract_image_paths(text)
        assert len(paths) == 1


class TestSendImagesFromResponse:
    """Test the async send_images_from_response function."""

    @pytest.mark.asyncio
    async def test_no_images_returns_text_unchanged(self):
        from src.telegram_ceo.image_sender import send_images_from_response
        bot = AsyncMock()
        text = "Просто текст без картинок."
        result = await send_images_from_response(bot, 123, text)
        assert result == text
        bot.send_photo.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_file_not_sent(self):
        from src.telegram_ceo.image_sender import send_images_from_response
        bot = AsyncMock()
        text = "Image: /data/design_images/nonexistent_abc123.png"
        result = await send_images_from_response(bot, 123, text)
        bot.send_photo.assert_not_called()
        # Path stays in text since file wasn't sent
        assert "/data/design_images/nonexistent_abc123.png" in result

    @pytest.mark.asyncio
    async def test_existing_file_sent_and_replaced(self, tmp_path):
        from src.telegram_ceo.image_sender import send_images_from_response
        # Create a temp image file
        img = tmp_path / "test_image.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        bot = AsyncMock()
        # The regex only matches /data/ or /tmp/ paths, so use /tmp/ prefix
        text = f"Image: {img}"
        # Since our regex requires /data/ or /tmp/ prefix, test with /tmp/
        tmp_img = f"/tmp/test_sprint6_{os.getpid()}.png"
        try:
            with open(tmp_img, "wb") as f:
                f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
            text = f"Image: {tmp_img}"
            result = await send_images_from_response(bot, 123, text)
            bot.send_photo.assert_called_once()
            assert "[📷 отправлено выше]" in result
            assert tmp_img not in result
        finally:
            if os.path.exists(tmp_img):
                os.unlink(tmp_img)

    @pytest.mark.asyncio
    async def test_send_photo_failure_handled(self, tmp_path):
        from src.telegram_ceo.image_sender import send_images_from_response
        tmp_img = f"/tmp/test_sprint6_fail_{os.getpid()}.png"
        try:
            with open(tmp_img, "wb") as f:
                f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
            bot = AsyncMock()
            bot.send_photo.side_effect = Exception("Telegram API error")
            text = f"Image: {tmp_img}"
            # Should not raise, just log warning
            result = await send_images_from_response(bot, 123, text)
            assert tmp_img in result  # Not replaced since send failed
        finally:
            if os.path.exists(tmp_img):
                os.unlink(tmp_img)


class TestImageSenderModule:
    """Test module-level attributes."""

    def test_regex_pattern_exists(self):
        from src.telegram_ceo.image_sender import _IMAGE_PATH_RE
        assert _IMAGE_PATH_RE is not None

    def test_module_imports_cleanly(self):
        import src.telegram_ceo.image_sender as mod
        assert hasattr(mod, "extract_image_paths")
        assert hasattr(mod, "send_images_from_response")


class TestCEOHandlersImportImageSender:
    """Verify messages.py and callbacks.py can access image_sender."""

    def test_messages_handler_importable(self):
        from src.telegram_ceo.handlers.messages import handle_text
        assert callable(handle_text)

    def test_image_sender_importable_from_handlers(self):
        from src.telegram_ceo.image_sender import send_images_from_response
        assert callable(send_images_from_response)


# ── Sprint 6 Refactor: CEO Bot ──────────────────────────────────


class TestValidAgentsRefactor:
    """VALID_AGENTS must include all 6 agents."""

    def test_includes_all_six(self):
        expected = {"manager", "accountant", "automator", "smm", "designer", "cpo"}
        assert VALID_AGENTS == expected

    def test_designer_present(self):
        assert "designer" in VALID_AGENTS

    def test_cpo_present(self):
        assert "cpo" in VALID_AGENTS


class TestAgentLabelsRefactor:
    """Agent labels dict must have all 6 agents."""

    def test_six_labels(self):
        assert len(_AGENT_LABELS) == 6

    def test_designer_is_ryan(self):
        assert "Райан" in _AGENT_LABELS["designer"]

    def test_cpo_is_sophie(self):
        assert "Софи" in _AGENT_LABELS["cpo"]


class TestErrorSanitizationRefactor:
    """Verify format_error_for_user works correctly."""

    def test_html_escaped(self):
        error = ValueError("<b>xss</b>")
        result = format_error_for_user(error)
        assert "<b>" not in result

    def test_max_length(self):
        error = ValueError("x" * 500)
        result = format_error_for_user(error)
        assert len(result) <= 220

    def test_type_included(self):
        error = RuntimeError("msg")
        result = format_error_for_user(error)
        assert "RuntimeError" in result


class TestTimeoutConfig:
    """Verify timeout constant."""

    def test_timeout_120(self):
        assert AGENT_TIMEOUT_SEC == 120


class TestFastRouterModule:
    """Verify fast_router.py module."""

    def test_importable(self):
        from src.telegram_ceo.fast_router import route_message, RouteResult
        assert callable(route_message)

    def test_route_returns_dataclass(self):
        from src.telegram_ceo.fast_router import route_message
        result = route_message("тест")
        assert hasattr(result, "route_type")
        assert hasattr(result, "agent_name")
        assert hasattr(result, "confidence")
        assert hasattr(result, "intent_command")
