"""Tests for proposal_applier.py — auto-applying CTO proposals to agent YAMLs."""

import os
import textwrap
from unittest.mock import patch, MagicMock

import pytest

# ──────────────────────────────────────────────────────────
# Sample YAML for tests
# ──────────────────────────────────────────────────────────

SAMPLE_YAML = textwrap.dedent("""\
    # ========================================
    # 📱 TEST AGENT
    # ========================================

    role: "Test Agent Role"

    goal: |
      Тестовая цель агента.
      Вторая строка цели для проверки.
      Третья строка с деталями.

    backstory: |
      Ты — тестовый агент, 30 лет. Полное имя: Тест Тестов.

      БИОГРАФИЯ:
      Родился в 2000 году. Выпускник МГУ.

      КАРЬЕРНЫЙ ПУТЬ:
      Работал тестировщиком 10 лет.
      Создал 500 тестов за карьеру.

      ХАРАКТЕР:
      Дотошный и внимательный к деталям.
      Никогда не пропускает баги.

    llm: openrouter/anthropic/claude-3-5-haiku-latest
    verbose: true
    memory: true
""")

SAMPLE_YAML_INLINE_ROLE = textwrap.dedent("""\
    role: "Inline Role Value"

    goal: |
      Short goal line one.
      Short goal line two for testing purposes.

    backstory: |
      Short backstory for testing field extraction and replacement.
      Second line of backstory here.

    llm: openrouter/anthropic/claude-sonnet-4
""")


# ──────────────────────────────────────────────────────────
# Test _detect_target_field
# ──────────────────────────────────────────────────────────

class TestDetectTargetField:
    def test_goal_keyword_english(self):
        from src.tools.proposal_applier import _detect_target_field
        assert _detect_target_field("Update the goal to include metrics") == "goal"

    def test_goal_keyword_russian(self):
        from src.tools.proposal_applier import _detect_target_field
        assert _detect_target_field("Добавить новую цель агенту") == "goal"

    def test_role_keyword_english(self):
        from src.tools.proposal_applier import _detect_target_field
        assert _detect_target_field("Change the role description") == "role"

    def test_role_keyword_russian(self):
        from src.tools.proposal_applier import _detect_target_field
        assert _detect_target_field("Изменить роль агента") == "role"

    def test_backstory_keyword(self):
        from src.tools.proposal_applier import _detect_target_field
        assert _detect_target_field("Обновить backstory агента") == "backstory"

    def test_backstory_russian_keyword(self):
        from src.tools.proposal_applier import _detect_target_field
        assert _detect_target_field("Добавить в биографию опыт работы") == "backstory"

    def test_default_is_backstory(self):
        from src.tools.proposal_applier import _detect_target_field
        assert _detect_target_field("Добавить новые инструкции") == "backstory"

    def test_goal_takes_priority_over_backstory(self):
        from src.tools.proposal_applier import _detect_target_field
        # "goal" keyword appears — should return "goal" even with other text
        assert _detect_target_field("Update goal and backstory sections") == "goal"


# ──────────────────────────────────────────────────────────
# Test _extract_yaml_field
# ──────────────────────────────────────────────────────────

class TestExtractYamlField:
    def test_extract_block_scalar_backstory(self):
        from src.tools.proposal_applier import _extract_yaml_field
        result = _extract_yaml_field(SAMPLE_YAML, "backstory")
        assert result is not None
        assert "тестовый агент" in result
        assert "БИОГРАФИЯ" in result
        assert "ХАРАКТЕР" in result

    def test_extract_block_scalar_goal(self):
        from src.tools.proposal_applier import _extract_yaml_field
        result = _extract_yaml_field(SAMPLE_YAML, "goal")
        assert result is not None
        assert "Тестовая цель" in result
        assert "Вторая строка" in result

    def test_extract_inline_role(self):
        from src.tools.proposal_applier import _extract_yaml_field
        result = _extract_yaml_field(SAMPLE_YAML, "role")
        assert result is not None
        assert "Test Agent Role" in result

    def test_extract_nonexistent_field(self):
        from src.tools.proposal_applier import _extract_yaml_field
        result = _extract_yaml_field(SAMPLE_YAML, "nonexistent")
        assert result is None

    def test_extract_llm_field(self):
        from src.tools.proposal_applier import _extract_yaml_field
        result = _extract_yaml_field(SAMPLE_YAML, "llm")
        assert result is not None
        assert "haiku" in result


# ──────────────────────────────────────────────────────────
# Test _replace_yaml_field
# ──────────────────────────────────────────────────────────

class TestReplaceYamlField:
    def test_replace_backstory(self):
        from src.tools.proposal_applier import _replace_yaml_field
        new_value = "Новый бэкстори.\n\nВторой абзац нового бэкстори с деталями."
        result = _replace_yaml_field(SAMPLE_YAML, "backstory", new_value)
        # Original role and goal should be preserved
        assert 'role: "Test Agent Role"' in result
        assert "Тестовая цель" in result
        # New backstory should be present
        assert "Новый бэкстори" in result
        assert "backstory: |" in result
        # llm should be preserved
        assert "llm: openrouter/anthropic/claude-3-5-haiku-latest" in result

    def test_replace_goal(self):
        from src.tools.proposal_applier import _replace_yaml_field
        new_value = "Новая цель агента.\nВторая строка новой цели."
        result = _replace_yaml_field(SAMPLE_YAML, "goal", new_value)
        assert "Новая цель агента" in result
        assert "goal: |" in result
        # Backstory should be preserved
        assert "тестовый агент" in result

    def test_replace_nonexistent_field_raises(self):
        from src.tools.proposal_applier import _replace_yaml_field
        with pytest.raises(ValueError, match="не найдено"):
            _replace_yaml_field(SAMPLE_YAML, "nonexistent", "value")

    def test_preserves_comments(self):
        from src.tools.proposal_applier import _replace_yaml_field
        new_value = "Новый бэкстори для проверки комментариев."
        result = _replace_yaml_field(SAMPLE_YAML, "backstory", new_value)
        assert "# ========================================" in result
        assert "# 📱 TEST AGENT" in result

    def test_result_is_valid_yaml(self):
        import yaml
        from src.tools.proposal_applier import _replace_yaml_field
        new_value = "Новый бэкстори.\nВторая строка."
        result = _replace_yaml_field(SAMPLE_YAML, "backstory", new_value)
        data = yaml.safe_load(result)
        assert isinstance(data, dict)
        assert "backstory" in data
        assert "Новый бэкстори" in data["backstory"]


# ──────────────────────────────────────────────────────────
# Test _detect_target_model
# ──────────────────────────────────────────────────────────

class TestDetectTargetModel:
    def test_sonnet_keyword(self):
        from src.tools.proposal_applier import _detect_target_model
        result = _detect_target_model("Перевести на sonnet", SAMPLE_YAML)
        assert result == "openrouter/anthropic/claude-sonnet-4"

    def test_haiku_keyword(self):
        from src.tools.proposal_applier import _detect_target_model
        result = _detect_target_model("Понизить до haiku", SAMPLE_YAML_INLINE_ROLE)
        assert result == "openrouter/anthropic/claude-3-5-haiku-latest"

    def test_upgrade_from_haiku(self):
        from src.tools.proposal_applier import _detect_target_model
        result = _detect_target_model("Повысить модель — upgrade", SAMPLE_YAML)
        assert result == "openrouter/anthropic/claude-sonnet-4"

    def test_downgrade_from_sonnet(self):
        from src.tools.proposal_applier import _detect_target_model
        result = _detect_target_model("Понизить модель", SAMPLE_YAML_INLINE_ROLE)
        assert result == "openrouter/anthropic/claude-3-5-haiku-latest"

    def test_no_match_returns_none(self):
        from src.tools.proposal_applier import _detect_target_model
        result = _detect_target_model("Непонятное предложение", SAMPLE_YAML)
        assert result is None


# ──────────────────────────────────────────────────────────
# Test _apply_model_tier_change
# ──────────────────────────────────────────────────────────

class TestApplyModelTierChange:
    def test_change_haiku_to_sonnet(self):
        from src.tools.proposal_applier import _apply_model_tier_change
        proposal = {
            "proposed_change": "Перевести на sonnet для улучшения качества",
        }
        result = _apply_model_tier_change(proposal, SAMPLE_YAML)
        assert "openrouter/anthropic/claude-sonnet-4" in result
        assert "claude-3-5-haiku-latest" not in result
        # Rest of YAML preserved
        assert 'role: "Test Agent Role"' in result

    def test_change_sonnet_to_haiku(self):
        from src.tools.proposal_applier import _apply_model_tier_change
        proposal = {
            "proposed_change": "Перевести на haiku для экономии",
        }
        result = _apply_model_tier_change(proposal, SAMPLE_YAML_INLINE_ROLE)
        assert "openrouter/anthropic/claude-3-5-haiku-latest" in result
        assert "claude-sonnet-4" not in result

    def test_no_model_detected_raises(self):
        from src.tools.proposal_applier import _apply_model_tier_change
        proposal = {"proposed_change": "Какое-то непонятное изменение"}
        with pytest.raises(ValueError, match="Не удалось определить"):
            _apply_model_tier_change(proposal, SAMPLE_YAML)

    def test_same_model_raises(self):
        from src.tools.proposal_applier import _apply_model_tier_change
        proposal = {"proposed_change": "Перевести на haiku"}
        with pytest.raises(ValueError, match="не изменилась"):
            _apply_model_tier_change(proposal, SAMPLE_YAML)


# ──────────────────────────────────────────────────────────
# Test _validate_yaml
# ──────────────────────────────────────────────────────────

class TestValidateYaml:
    def test_valid_yaml(self):
        from src.tools.proposal_applier import _validate_yaml
        _validate_yaml(SAMPLE_YAML)  # should not raise

    def test_invalid_yaml_syntax(self):
        from src.tools.proposal_applier import _validate_yaml
        with pytest.raises(ValueError, match="невалиден"):
            _validate_yaml("key: [invalid yaml{{{")

    def test_missing_required_key(self):
        from src.tools.proposal_applier import _validate_yaml
        yaml_without_role = "goal: |\n  test goal\nbackstory: |\n  test backstory\nllm: test"
        with pytest.raises(ValueError, match="role"):
            _validate_yaml(yaml_without_role)

    def test_too_short_backstory(self):
        from src.tools.proposal_applier import _validate_yaml
        short = "role: test\ngoal: |\n  A valid goal that is long enough\nbackstory: short\nllm: test"
        with pytest.raises(ValueError, match="слишком короткое"):
            _validate_yaml(short)


# ──────────────────────────────────────────────────────────
# Test _compute_diff
# ──────────────────────────────────────────────────────────

class TestComputeDiff:
    def test_diff_shows_changes(self):
        from src.tools.proposal_applier import _compute_diff
        before = "line1\nline2\nline3"
        after = "line1\nmodified\nline3"
        diff = _compute_diff(before, after, "test_agent")
        assert "-line2" in diff
        assert "+modified" in diff
        assert "test_agent" in diff

    def test_no_diff_for_identical(self):
        from src.tools.proposal_applier import _compute_diff
        text = "line1\nline2"
        diff = _compute_diff(text, text, "test_agent")
        assert diff == ""


# ──────────────────────────────────────────────────────────
# Test format_diff_for_telegram
# ──────────────────────────────────────────────────────────

class TestFormatDiffForTelegram:
    def test_empty_diff(self):
        from src.tools.proposal_applier import format_diff_for_telegram
        assert format_diff_for_telegram("") == "(нет изменений)"

    def test_html_escaping(self):
        from src.tools.proposal_applier import format_diff_for_telegram
        diff = "+added <script>alert('xss')</script>"
        result = format_diff_for_telegram(diff)
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_truncation(self):
        from src.tools.proposal_applier import format_diff_for_telegram
        long_diff = "+a\n" * 5000
        result = format_diff_for_telegram(long_diff, max_len=100)
        assert len(result) < 200  # truncated + "обрезано"
        assert "обрезано" in result


# ──────────────────────────────────────────────────────────
# Test apply_proposal (integration, with mocks)
# ──────────────────────────────────────────────────────────

class TestApplyProposal:
    def test_tool_proposal_returns_not_applied(self):
        from src.tools.proposal_applier import apply_proposal
        proposal = {
            "id": "test-1",
            "proposal_type": "tool",
            "proposed_change": "Добавить инструмент web_search",
        }
        result = apply_proposal(proposal)
        assert result["applied"] is False
        assert "ручная" in result["message"].lower() or "реализация" in result["message"].lower()

    def test_model_tier_change_applies(self, tmp_path):
        """Model tier change modifies llm: line in YAML."""
        from src.tools.proposal_applier import apply_proposal

        # Create temp YAML file
        yaml_file = tmp_path / "test_agent.yaml"
        yaml_file.write_text(SAMPLE_YAML, encoding="utf-8")

        proposal = {
            "id": "test-2",
            "proposal_type": "model_tier",
            "target_agent": "test_agent",
            "proposed_change": "Перевести на sonnet для улучшения качества",
        }

        with patch("src.tools.proposal_applier._agent_yaml_dir", return_value=str(tmp_path)):
            result = apply_proposal(proposal)

        assert result["applied"] is True
        assert result["diff"] != ""
        assert "sonnet" in result["diff"]

        # Verify file was actually changed
        new_content = yaml_file.read_text(encoding="utf-8")
        assert "claude-sonnet-4" in new_content
        assert "claude-3-5-haiku-latest" not in new_content

        # Verify backup was cleaned up
        assert not (tmp_path / "test_agent.yaml.backup").exists()

    def test_prompt_change_applies(self, tmp_path):
        """Prompt change uses LLM to modify backstory."""
        from src.tools.proposal_applier import apply_proposal

        yaml_file = tmp_path / "test_agent.yaml"
        yaml_file.write_text(SAMPLE_YAML, encoding="utf-8")

        proposal = {
            "id": "test-3",
            "proposal_type": "prompt",
            "target_agent": "test_agent",
            "proposed_change": "Добавить в backstory опыт работы с AI-агентами",
        }

        # Mock _call_llm_tech to return modified backstory
        modified_backstory = (
            "Ты — тестовый агент, 30 лет. Полное имя: Тест Тестов.\n\n"
            "БИОГРАФИЯ:\n"
            "Родился в 2000 году. Выпускник МГУ.\n\n"
            "КАРЬЕРНЫЙ ПУТЬ:\n"
            "Работал тестировщиком 10 лет.\n"
            "Создал 500 тестов за карьеру.\n"
            "Имеет опыт работы с AI-агентами и мульти-агентными системами.\n\n"
            "ХАРАКТЕР:\n"
            "Дотошный и внимательный к деталям.\n"
            "Никогда не пропускает баги."
        )

        with (
            patch("src.tools.proposal_applier._agent_yaml_dir", return_value=str(tmp_path)),
            patch("src.tools.proposal_applier._call_llm_tech", return_value=modified_backstory),
        ):
            result = apply_proposal(proposal)

        assert result["applied"] is True
        assert result["diff"] != ""
        assert "AI-агент" in result["diff"]

        # Verify file was actually changed
        new_content = yaml_file.read_text(encoding="utf-8")
        assert "AI-агент" in new_content
        # Other fields preserved
        assert 'role: "Test Agent Role"' in new_content
        assert "llm: openrouter/anthropic/claude-3-5-haiku-latest" in new_content

    def test_prompt_change_llm_unavailable_raises(self, tmp_path):
        """If LLM returns nothing, apply should raise."""
        from src.tools.proposal_applier import apply_proposal

        yaml_file = tmp_path / "test_agent.yaml"
        yaml_file.write_text(SAMPLE_YAML, encoding="utf-8")

        proposal = {
            "id": "test-4",
            "proposal_type": "prompt",
            "target_agent": "test_agent",
            "proposed_change": "Добавить в backstory инструкции",
        }

        with (
            patch("src.tools.proposal_applier._agent_yaml_dir", return_value=str(tmp_path)),
            patch("src.tools.proposal_applier._call_llm_tech", return_value=None),
        ):
            with pytest.raises(ValueError, match="LLM недоступен"):
                apply_proposal(proposal)

        # Verify rollback — file should be unchanged
        content = yaml_file.read_text(encoding="utf-8")
        assert content == SAMPLE_YAML

    def test_prompt_change_too_short_raises(self, tmp_path):
        """If LLM returns too short text, should raise and rollback."""
        from src.tools.proposal_applier import apply_proposal

        yaml_file = tmp_path / "test_agent.yaml"
        yaml_file.write_text(SAMPLE_YAML, encoding="utf-8")

        proposal = {
            "id": "test-5",
            "proposal_type": "prompt",
            "target_agent": "test_agent",
            "proposed_change": "Упростить backstory",
        }

        with (
            patch("src.tools.proposal_applier._agent_yaml_dir", return_value=str(tmp_path)),
            patch("src.tools.proposal_applier._call_llm_tech", return_value="Короткий"),
        ):
            with pytest.raises(ValueError, match="слишком короткий"):
                apply_proposal(proposal)

        # Verify rollback
        content = yaml_file.read_text(encoding="utf-8")
        assert content == SAMPLE_YAML

    def test_missing_yaml_raises(self):
        from src.tools.proposal_applier import apply_proposal
        proposal = {
            "id": "test-6",
            "proposal_type": "prompt",
            "target_agent": "nonexistent_agent",
            "proposed_change": "some change",
        }
        with pytest.raises(FileNotFoundError):
            apply_proposal(proposal)

    def test_backup_cleanup_on_success(self, tmp_path):
        """Backup file should be removed after successful apply."""
        from src.tools.proposal_applier import apply_proposal

        yaml_file = tmp_path / "test_agent.yaml"
        yaml_file.write_text(SAMPLE_YAML, encoding="utf-8")

        proposal = {
            "id": "test-7",
            "proposal_type": "model_tier",
            "target_agent": "test_agent",
            "proposed_change": "Upgrade to sonnet",
        }

        with patch("src.tools.proposal_applier._agent_yaml_dir", return_value=str(tmp_path)):
            apply_proposal(proposal)

        assert not (tmp_path / "test_agent.yaml.backup").exists()

    def test_backup_rollback_on_failure(self, tmp_path):
        """On failure, original file should be restored from backup."""
        from src.tools.proposal_applier import apply_proposal

        yaml_file = tmp_path / "test_agent.yaml"
        yaml_file.write_text(SAMPLE_YAML, encoding="utf-8")

        proposal = {
            "id": "test-8",
            "proposal_type": "prompt",
            "target_agent": "test_agent",
            "proposed_change": "Some change",
        }

        with (
            patch("src.tools.proposal_applier._agent_yaml_dir", return_value=str(tmp_path)),
            patch("src.tools.proposal_applier._call_llm_tech", return_value=None),
        ):
            with pytest.raises(ValueError):
                apply_proposal(proposal)

        # File restored
        content = yaml_file.read_text(encoding="utf-8")
        assert content == SAMPLE_YAML
        # Backup cleaned up
        assert not (tmp_path / "test_agent.yaml.backup").exists()


# ──────────────────────────────────────────────────────────
# Test on_cto_approve integration with apply_proposal
# ──────────────────────────────────────────────────────────

class TestOnCtoApproveWithApply:
    """Test that on_cto_approve calls apply_proposal and reports diff."""

    @pytest.fixture
    def mock_callback(self):
        cb = MagicMock()
        cb.data = "cto_approve:test-id-1"
        cb.message = MagicMock()
        cb.message.edit_text = MagicMock(return_value=MagicMock())  # awaitable
        cb.answer = MagicMock(return_value=MagicMock())  # awaitable

        # Make async methods awaitable
        import asyncio
        future_none = asyncio.Future()
        future_none.set_result(None)
        cb.message.edit_text.return_value = future_none
        cb.answer.return_value = future_none

        return cb

    @pytest.mark.asyncio
    async def test_approve_calls_apply_and_shows_diff(self, mock_callback):
        """Successful apply should show diff in message."""
        from src.telegram_ceo.handlers.callbacks import on_cto_approve

        test_proposal = {
            "id": "test-id-1",
            "title": "Тест",
            "target_agent": "manager",
            "proposal_type": "model_tier",
            "proposed_change": "Перевести на sonnet",
            "status": "pending",
        }

        apply_result = {
            "applied": True,
            "diff": "--- a\n+++ b\n-old\n+new",
            "message": "Изменения применены к YAML.",
        }

        with (
            patch(
                "src.telegram_ceo.handlers.callbacks._find_and_update_proposal",
                return_value=test_proposal,
            ),
            patch(
                "src.tools.improvement_advisor._AGENT_LABELS",
                {"manager": "👑 Алексей"},
            ),
            patch(
                "src.tools.proposal_applier.apply_proposal",
                return_value=apply_result,
            ),
            patch(
                "src.tools.proposal_applier.format_diff_for_telegram",
                return_value="--- a\n+++ b\n-old\n+new",
            ),
        ):
            await on_cto_approve(mock_callback)

        # edit_text should be called at least twice:
        # 1) "⏳ ПРИМЕНЯЮ" status
        # 2) "✅ ОДОБРЕНО И ПРИМЕНЕНО" with diff
        assert mock_callback.message.edit_text.call_count >= 2
        final_call = mock_callback.message.edit_text.call_args_list[-1]
        final_text = final_call[0][0] if final_call[0] else final_call[1].get("text", "")
        # Verify diff content appears
        assert "ПРИМЕНЕНО" in final_text or "применено" in final_text.lower()

    @pytest.mark.asyncio
    async def test_approve_tool_proposal_shows_manual_message(self, mock_callback):
        """Tool proposal should show 'requires manual implementation'."""
        from src.telegram_ceo.handlers.callbacks import on_cto_approve

        test_proposal = {
            "id": "test-id-1",
            "title": "Добавить web_search",
            "target_agent": "yuki",
            "proposal_type": "tool",
            "proposed_change": "Добавить инструмент web_search",
            "status": "pending",
        }

        apply_result = {
            "applied": False,
            "diff": "",
            "message": "Предложение инструмента одобрено. Требуется ручная реализация.",
        }

        with (
            patch(
                "src.telegram_ceo.handlers.callbacks._find_and_update_proposal",
                return_value=test_proposal,
            ),
            patch(
                "src.tools.improvement_advisor._AGENT_LABELS",
                {"yuki": "📱 Юки"},
            ),
            patch(
                "src.tools.proposal_applier.apply_proposal",
                return_value=apply_result,
            ),
        ):
            await on_cto_approve(mock_callback)

        # Should show ОДОБРЕНО (not ПРИМЕНЕНО)
        final_call = mock_callback.message.edit_text.call_args_list[-1]
        final_text = final_call[0][0] if final_call[0] else final_call[1].get("text", "")
        assert "ОДОБРЕНО" in final_text
        assert "ручная" in final_text.lower() or "реализация" in final_text.lower()

    @pytest.mark.asyncio
    async def test_approve_apply_error_shows_warning(self, mock_callback):
        """If apply fails, should show error but still confirm approval."""
        from src.telegram_ceo.handlers.callbacks import on_cto_approve

        test_proposal = {
            "id": "test-id-1",
            "title": "Ошибочное предложение",
            "target_agent": "manager",
            "proposal_type": "prompt",
            "proposed_change": "Something",
            "status": "pending",
        }

        with (
            patch(
                "src.telegram_ceo.handlers.callbacks._find_and_update_proposal",
                return_value=test_proposal,
            ),
            patch(
                "src.tools.improvement_advisor._AGENT_LABELS",
                {"manager": "👑 Алексей"},
            ),
            patch(
                "src.tools.proposal_applier.apply_proposal",
                side_effect=ValueError("YAML не найден"),
            ),
        ):
            await on_cto_approve(mock_callback)

        # Should show ОДОБРЕНО (не применено) with error
        final_call = mock_callback.message.edit_text.call_args_list[-1]
        final_text = final_call[0][0] if final_call[0] else final_call[1].get("text", "")
        assert "ОДОБРЕНО" in final_text
        assert "не применено" in final_text.lower() or "ошибка" in final_text.lower()

    @pytest.mark.asyncio
    async def test_not_found_proposal_answers_alert(self, mock_callback):
        """Missing proposal should show alert."""
        from src.telegram_ceo.handlers.callbacks import on_cto_approve

        with patch(
            "src.telegram_ceo.handlers.callbacks._find_and_update_proposal",
            return_value=None,
        ):
            await on_cto_approve(mock_callback)

        mock_callback.answer.assert_called_with("Предложение не найдено", show_alert=True)


# ──────────────────────────────────────────────────────────
# Test _apply_prompt_change
# ──────────────────────────────────────────────────────────

class TestApplyPromptChange:
    def test_llm_output_cleaned(self, tmp_path):
        """LLM output with field prefix should be cleaned."""
        from src.tools.proposal_applier import _apply_prompt_change

        proposal = {
            "proposed_change": "Добавить в backstory информацию о навыках",
        }

        # LLM returns text with "backstory:" prefix
        llm_response = (
            "backstory: |\n"
            "  Ты — тестовый агент, 30 лет. Полное имя: Тест Тестов.\n\n"
            "  БИОГРАФИЯ:\n"
            "  Родился в 2000 году. Выпускник МГУ.\n\n"
            "  НАВЫКИ:\n"
            "  Обладает навыками AI-тестирования и автоматизации.\n\n"
            "  КАРЬЕРНЫЙ ПУТЬ:\n"
            "  Работал тестировщиком 10 лет.\n"
            "  Создал 500 тестов за карьеру.\n\n"
            "  ХАРАКТЕР:\n"
            "  Дотошный и внимательный к деталям.\n"
            "  Никогда не пропускает баги."
        )

        with patch("src.tools.proposal_applier._call_llm_tech", return_value=llm_response):
            result = _apply_prompt_change(proposal, SAMPLE_YAML)

        # Should produce valid YAML
        import yaml
        data = yaml.safe_load(result)
        assert "backstory" in data
        assert "НАВЫКИ" in data["backstory"]

    def test_goal_change_detected(self):
        """Proposal mentioning 'цель' should target goal field."""
        from src.tools.proposal_applier import _apply_prompt_change

        proposal = {
            "proposed_change": "Добавить новую цель: мониторинг метрик",
        }

        new_goal = (
            "Тестовая цель агента.\n"
            "Вторая строка цели для проверки.\n"
            "Третья строка с деталями.\n"
            "Мониторинг метрик производительности."
        )

        with patch("src.tools.proposal_applier._call_llm_tech", return_value=new_goal):
            result = _apply_prompt_change(proposal, SAMPLE_YAML)

        import yaml
        data = yaml.safe_load(result)
        assert "Мониторинг метрик" in data["goal"]
        # Backstory should be unchanged
        assert "тестовый агент" in data["backstory"]
