"""
Tests for Multi-Platform Content Adapter (#30).
"""

import inspect
import pytest
from unittest.mock import patch, MagicMock


# ── Module structure ──────────────────────────────────────

class TestModuleStructure:
    def test_module_exists(self):
        from src.tools import content_adapter
        assert content_adapter is not None

    def test_platform_rules_exist(self):
        from src.tools.content_adapter import PLATFORM_RULES
        assert "linkedin" in PLATFORM_RULES
        assert "telegram" in PLATFORM_RULES
        assert "threads" in PLATFORM_RULES

    def test_platform_rules_have_required_keys(self):
        from src.tools.content_adapter import PLATFORM_RULES
        required_keys = {"label", "max_chars", "tone", "hashtags", "emoji_level", "format"}
        for platform, rules in PLATFORM_RULES.items():
            for key in required_keys:
                assert key in rules, f"Missing {key} in {platform} rules"

    def test_platform_max_chars_reasonable(self):
        from src.tools.content_adapter import PLATFORM_RULES
        assert PLATFORM_RULES["linkedin"]["max_chars"] >= 2000
        assert PLATFORM_RULES["telegram"]["max_chars"] >= 1000
        assert PLATFORM_RULES["threads"]["max_chars"] <= 600

    def test_adapt_content_function_exists(self):
        from src.tools.content_adapter import adapt_content
        assert callable(adapt_content)

    def test_adapt_for_all_platforms_exists(self):
        from src.tools.content_adapter import adapt_for_all_platforms
        assert callable(adapt_for_all_platforms)


# ── adapt_content ─────────────────────────────────────────

class TestAdaptContent:
    SAMPLE_POST = (
        "Вчера я провёл 3 часа анализируя AI-инструменты для HR.\n\n"
        "Результат? 80% из них — маркетинговый шум.\n\n"
        "Вот 5 инструментов, которые реально работают:\n"
        "1. ChatGPT для написания вакансий — экономит 40 минут\n"
        "2. LinkedIn Recruiter — всё ещё лучший sourcing\n"
        "3. Notion AI для систематизации кандидатов\n"
        "4. Otter.ai для записи интервью\n"
        "5. Claude для оценки резюме\n\n"
        "Не гонитесь за трендами. Тестируйте.\n\n"
        "#HR #AI #recruitment #карьера #СБОРКА"
    )

    def test_same_platform_returns_original(self):
        from src.tools.content_adapter import adapt_content
        result = adapt_content(self.SAMPLE_POST, "linkedin", "linkedin")
        assert result == self.SAMPLE_POST

    def test_unknown_platform_returns_original(self):
        from src.tools.content_adapter import adapt_content
        result = adapt_content(self.SAMPLE_POST, "tiktok", "linkedin")
        assert result == self.SAMPLE_POST

    @patch("src.tools.tech_tools._call_llm_tech", return_value=None)
    def test_fallback_telegram_removes_hashtags(self, mock_llm):
        from src.tools.content_adapter import adapt_content
        result = adapt_content(self.SAMPLE_POST, "telegram", "linkedin")
        assert "#HR" not in result
        assert "#AI" not in result

    @patch("src.tools.tech_tools._call_llm_tech", return_value=None)
    def test_fallback_telegram_respects_max_chars(self, mock_llm):
        from src.tools.content_adapter import PLATFORM_RULES, adapt_content
        long_post = "A" * 5000
        result = adapt_content(long_post, "telegram", "linkedin")
        assert len(result) <= PLATFORM_RULES["telegram"]["max_chars"] + 5  # +5 for "..."

    @patch("src.tools.tech_tools._call_llm_tech", return_value=None)
    def test_fallback_threads_short(self, mock_llm):
        from src.tools.content_adapter import PLATFORM_RULES, adapt_content
        result = adapt_content(self.SAMPLE_POST, "threads", "linkedin")
        assert len(result) <= PLATFORM_RULES["threads"]["max_chars"]

    @patch("src.tools.tech_tools._call_llm_tech")
    def test_llm_adaptation_used(self, mock_llm):
        from src.tools.content_adapter import adapt_content
        mock_llm.return_value = "Адаптированный текст для Telegram канала. Всё коротко и по делу."
        result = adapt_content(self.SAMPLE_POST, "telegram", "linkedin")
        assert "Адаптированный текст" in result

    @patch("src.tools.tech_tools._call_llm_tech")
    def test_llm_adaptation_truncated_if_too_long(self, mock_llm):
        from src.tools.content_adapter import PLATFORM_RULES, adapt_content
        # LLM returns text exceeding threads limit
        mock_llm.return_value = "A" * 1000
        result = adapt_content("original", "threads", "linkedin")
        assert len(result) <= PLATFORM_RULES["threads"]["max_chars"] + 5

    @patch("src.tools.tech_tools._call_llm_tech", side_effect=Exception("API error"))
    def test_llm_exception_falls_back(self, mock_llm):
        from src.tools.content_adapter import adapt_content
        # Should not raise, should fall back to rule-based
        result = adapt_content(self.SAMPLE_POST, "telegram", "linkedin")
        assert len(result) > 0

    @patch("src.tools.tech_tools._call_llm_tech", return_value="")
    def test_llm_empty_response_falls_back(self, mock_llm):
        from src.tools.content_adapter import adapt_content
        result = adapt_content(self.SAMPLE_POST, "telegram", "linkedin")
        assert len(result) > 0


# ── adapt_for_all_platforms ───────────────────────────────

class TestAdaptForAllPlatforms:
    SAMPLE = "Тестовый пост для адаптации. Содержит факты и цифры: $1000 и 50%."

    @patch("src.tools.tech_tools._call_llm_tech", return_value=None)
    def test_returns_all_platforms(self, mock_llm):
        from src.tools.content_adapter import adapt_for_all_platforms, PLATFORM_RULES
        result = adapt_for_all_platforms(self.SAMPLE, "linkedin")
        for platform in PLATFORM_RULES:
            assert platform in result

    @patch("src.tools.tech_tools._call_llm_tech", return_value=None)
    def test_source_platform_unchanged(self, mock_llm):
        from src.tools.content_adapter import adapt_for_all_platforms
        result = adapt_for_all_platforms(self.SAMPLE, "linkedin")
        assert result["linkedin"] == self.SAMPLE

    @patch("src.tools.tech_tools._call_llm_tech", return_value=None)
    def test_other_platforms_adapted(self, mock_llm):
        from src.tools.content_adapter import adapt_for_all_platforms
        long_post = "A" * 3000 + "\n\n#test #hashtag"
        result = adapt_for_all_platforms(long_post, "linkedin")
        # Telegram should have hashtags removed
        assert "#test" not in result["telegram"]


# ── _truncate_smart ───────────────────────────────────────

class TestTruncateSmart:
    def test_short_text_unchanged(self):
        from src.tools.content_adapter import _truncate_smart
        assert _truncate_smart("Hello world.", 100) == "Hello world."

    def test_truncate_at_sentence(self):
        from src.tools.content_adapter import _truncate_smart
        text = "First sentence. Second sentence. Third sentence."
        result = _truncate_smart(text, 35)
        assert result.endswith(".")
        assert len(result) <= 35

    def test_truncate_at_space_if_no_sentence(self):
        from src.tools.content_adapter import _truncate_smart
        text = "A" * 50 + " " + "B" * 50
        result = _truncate_smart(text, 60)
        assert len(result) <= 63  # +3 for "..."


# ── Publishing integration ────────────────────────────────

class TestPublishingIntegration:
    def test_do_publish_uses_adaptation(self):
        from src.telegram_yuki.handlers.callbacks import _do_publish
        src = inspect.getsource(_do_publish)
        assert "adapt_for_all_platforms" in src

    def test_do_publish_has_fallback(self):
        """If adaptation fails, should still use original text."""
        from src.telegram_yuki.handlers.callbacks import _do_publish
        src = inspect.getsource(_do_publish)
        assert "adapted.get" in src

    def test_adaptation_only_for_multi_platform(self):
        """Adaptation should only run when publishing to multiple platforms."""
        from src.telegram_yuki.handlers.callbacks import _do_publish
        src = inspect.getsource(_do_publish)
        assert "len(platforms) > 1" in src


# ── Prompt constants ──────────────────────────────────────

class TestPromptConstants:
    def test_adapt_system_prompt(self):
        from src.tools.content_adapter import _ADAPT_SYSTEM
        assert "adaptation" in _ADAPT_SYSTEM.lower() or "adapt" in _ADAPT_SYSTEM.lower()
        assert "Russian" in _ADAPT_SYSTEM or "русск" in _ADAPT_SYSTEM.lower()

    def test_adapt_prompt_has_placeholders(self):
        from src.tools.content_adapter import _ADAPT_PROMPT_TEMPLATE
        assert "{platform_label}" in _ADAPT_PROMPT_TEMPLATE
        assert "{max_chars}" in _ADAPT_PROMPT_TEMPLATE
        assert "{original_text}" in _ADAPT_PROMPT_TEMPLATE
