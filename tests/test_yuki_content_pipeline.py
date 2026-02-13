"""Tests for Yuki content pipeline: CS-001 (deferred image), CS-002 (no-image option),
CS-003 (image regeneration), CS-004 (feedback iterations)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── CS-001 + CS-002: Keyboard tests ────────────────────────────────────────

class TestPostReadyKeyboard:
    """CS-001/CS-002: post_ready_keyboard with image choice."""

    def test_has_three_rows(self):
        from src.telegram_yuki.keyboards import post_ready_keyboard
        kb = post_ready_keyboard("test123")
        assert len(kb.inline_keyboard) == 3

    def test_first_row_image_options(self):
        from src.telegram_yuki.keyboards import post_ready_keyboard
        kb = post_ready_keyboard("test123")
        row = kb.inline_keyboard[0]
        assert len(row) == 2
        assert row[0].callback_data == "gen_image:test123"
        assert row[1].callback_data == "approve:test123"
        assert "картинк" in row[0].text.lower()

    def test_second_row_regen_reject(self):
        from src.telegram_yuki.keyboards import post_ready_keyboard
        kb = post_ready_keyboard("test123")
        row = kb.inline_keyboard[1]
        assert len(row) == 2
        assert row[0].callback_data == "regen:test123"
        assert row[1].callback_data == "reject:test123"

    def test_third_row_edit(self):
        from src.telegram_yuki.keyboards import post_ready_keyboard
        kb = post_ready_keyboard("test123")
        row = kb.inline_keyboard[2]
        assert len(row) == 1
        assert row[0].callback_data == "edit:test123"


class TestApprovalWithImageKeyboard:
    """CS-003: approval_with_image_keyboard."""

    def test_has_three_rows(self):
        from src.telegram_yuki.keyboards import approval_with_image_keyboard
        kb = approval_with_image_keyboard("img123")
        assert len(kb.inline_keyboard) == 3

    def test_first_row_approve_reject(self):
        from src.telegram_yuki.keyboards import approval_with_image_keyboard
        kb = approval_with_image_keyboard("img123")
        row = kb.inline_keyboard[0]
        assert row[0].callback_data == "approve:img123"
        assert row[1].callback_data == "reject:img123"

    def test_second_row_regen_image_and_text(self):
        from src.telegram_yuki.keyboards import approval_with_image_keyboard
        kb = approval_with_image_keyboard("img123")
        row = kb.inline_keyboard[1]
        assert row[0].callback_data == "regen_image:img123"
        assert row[1].callback_data == "regen:img123"

    def test_third_row_edit(self):
        from src.telegram_yuki.keyboards import approval_with_image_keyboard
        kb = approval_with_image_keyboard("img123")
        row = kb.inline_keyboard[2]
        assert row[0].callback_data == "edit:img123"


class TestFinalChoiceKeyboard:
    """CS-004: final_choice_keyboard at max iterations."""

    def test_has_one_row(self):
        from src.telegram_yuki.keyboards import final_choice_keyboard
        kb = final_choice_keyboard("fin123")
        assert len(kb.inline_keyboard) == 1

    def test_approve_and_reject_buttons(self):
        from src.telegram_yuki.keyboards import final_choice_keyboard
        kb = final_choice_keyboard("fin123")
        row = kb.inline_keyboard[0]
        assert len(row) == 2
        assert row[0].callback_data == "approve:fin123"
        assert row[1].callback_data == "reject:fin123"
        assert "как есть" in row[0].text.lower()
        assert "окончательно" in row[1].text.lower()


# ── CS-004: DraftManager iteration fields ───────────────────────────────────

class TestDraftIterationFields:
    """CS-004: DraftManager creates drafts with iteration tracking."""

    def setup_method(self):
        from src.telegram_yuki.drafts import DraftManager
        DraftManager._drafts.clear()

    def test_draft_has_iteration_field(self):
        from src.telegram_yuki.drafts import DraftManager
        post_id = DraftManager.create_draft(topic="test", text="text")
        draft = DraftManager.get_draft(post_id)
        assert draft["iteration"] == 1

    def test_draft_has_max_iterations_field(self):
        from src.telegram_yuki.drafts import DraftManager
        post_id = DraftManager.create_draft(topic="test", text="text")
        draft = DraftManager.get_draft(post_id)
        assert draft["max_iterations"] == 3

    def test_draft_has_feedback_history_field(self):
        from src.telegram_yuki.drafts import DraftManager
        post_id = DraftManager.create_draft(topic="test", text="text")
        draft = DraftManager.get_draft(post_id)
        assert draft["feedback_history"] == []

    def test_iteration_can_be_updated(self):
        from src.telegram_yuki.drafts import DraftManager
        post_id = DraftManager.create_draft(topic="test", text="text")
        DraftManager.update_draft(post_id, iteration=2, feedback_history=["shorter"])
        draft = DraftManager.get_draft(post_id)
        assert draft["iteration"] == 2
        assert draft["feedback_history"] == ["shorter"]


# ── CS-003: Image regen state ──────────────────────────────────────────────

class TestImageRegenState:
    """CS-003: _image_regen_state management in callbacks."""

    def test_is_in_image_regen_mode_false(self):
        from src.telegram_yuki.handlers.callbacks import (
            _image_regen_state, is_in_image_regen_mode,
        )
        _image_regen_state.clear()
        assert is_in_image_regen_mode(123) is False

    def test_is_in_image_regen_mode_true(self):
        from src.telegram_yuki.handlers.callbacks import (
            _image_regen_state, is_in_image_regen_mode,
        )
        _image_regen_state.clear()
        _image_regen_state[123] = "post_abc"
        assert is_in_image_regen_mode(123) is True

    def test_get_image_regen_post_id(self):
        from src.telegram_yuki.handlers.callbacks import (
            _image_regen_state, get_image_regen_post_id,
        )
        _image_regen_state.clear()
        _image_regen_state[456] = "post_xyz"
        assert get_image_regen_post_id(456) == "post_xyz"
        assert get_image_regen_post_id(999) is None

    def test_consume_image_regen_mode(self):
        from src.telegram_yuki.handlers.callbacks import (
            _image_regen_state, consume_image_regen_mode, is_in_image_regen_mode,
        )
        _image_regen_state.clear()
        _image_regen_state[789] = "post_123"
        result = consume_image_regen_mode(789)
        assert result == "post_123"
        assert is_in_image_regen_mode(789) is False

    def test_consume_not_active(self):
        from src.telegram_yuki.handlers.callbacks import (
            _image_regen_state, consume_image_regen_mode,
        )
        _image_regen_state.clear()
        assert consume_image_regen_mode(999) is None


# ── CS-003: generate_image_with_refinement ─────────────────────────────────

class TestGenerateImageWithRefinement:
    """CS-003: generate_image_with_refinement() function."""

    @patch("src.telegram_yuki.image_gen._call_openrouter")
    @patch("src.telegram_yuki.image_gen._extract_image")
    def test_returns_path_on_success(self, mock_extract, mock_call):
        from src.telegram_yuki.image_gen import generate_image_with_refinement
        mock_call.return_value = {"choices": []}
        mock_extract.return_value = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        result = generate_image_with_refinement("test topic", "test text", "make it brighter")
        assert result.endswith("_refined.png")
        assert "yuki_" in result

    @patch("src.telegram_yuki.image_gen._call_openrouter")
    @patch("src.telegram_yuki.image_gen._extract_image")
    def test_returns_empty_on_no_image(self, mock_extract, mock_call):
        from src.telegram_yuki.image_gen import generate_image_with_refinement
        mock_call.return_value = {"choices": []}
        mock_extract.return_value = None
        result = generate_image_with_refinement("test", "text", "refinement")
        assert result == ""

    @patch("src.telegram_yuki.image_gen._call_openrouter")
    def test_returns_empty_on_exception(self, mock_call):
        from src.telegram_yuki.image_gen import generate_image_with_refinement
        mock_call.side_effect = RuntimeError("API error")
        result = generate_image_with_refinement("test", "text", "refinement")
        assert result == ""

    @patch("src.telegram_yuki.image_gen._call_openrouter")
    @patch("src.telegram_yuki.image_gen._extract_image")
    def test_refinement_appended_to_prompt(self, mock_extract, mock_call):
        from src.telegram_yuki.image_gen import generate_image_with_refinement
        mock_call.return_value = {"choices": []}
        mock_extract.return_value = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        generate_image_with_refinement("topic", "text", "add red arrow")
        call_args = mock_call.call_args[0][0]
        assert "add red arrow" in call_args
        assert "ADDITIONAL USER REFINEMENT" in call_args


# ── CS-001: Callback handler existence ─────────────────────────────────────

class TestCallbackHandlerExistence:
    """Verify new callback handlers are importable and callable."""

    def test_on_gen_image_exists(self):
        from src.telegram_yuki.handlers.callbacks import on_gen_image
        assert callable(on_gen_image)

    def test_on_regen_image_exists(self):
        from src.telegram_yuki.handlers.callbacks import on_regen_image
        assert callable(on_regen_image)


# ── CS-002: _generate_post_flow uses post_ready_keyboard ───────────────────

class TestGeneratePostFlowKeyboard:
    """CS-002: _generate_post_flow should use post_ready_keyboard, not approval_keyboard."""

    def test_post_ready_keyboard_imported(self):
        import inspect
        from src.telegram_yuki.handlers import messages
        source = inspect.getsource(messages._generate_post_flow)
        assert "post_ready_keyboard" in source
        assert "approval_keyboard" not in source


# ── CS-004: _handle_edit_feedback iteration tracking ───────────────────────

class TestEditFeedbackIterations:
    """CS-004: Iteration tracking in _handle_edit_feedback."""

    def test_iteration_fields_in_source(self):
        import inspect
        from src.telegram_yuki.handlers import messages
        source = inspect.getsource(messages._handle_edit_feedback)
        assert "iteration" in source
        assert "max_iterations" in source
        assert "feedback_history" in source
        assert "final_choice_keyboard" in source


# ── Existing keyboards unchanged ───────────────────────────────────────────

class TestExistingKeyboardsUnchanged:
    """Verify existing keyboards still work after additions."""

    def test_approval_keyboard(self):
        from src.telegram_yuki.keyboards import approval_keyboard
        kb = approval_keyboard("test")
        assert len(kb.inline_keyboard) == 2

    def test_platform_keyboard(self):
        from src.telegram_yuki.keyboards import platform_keyboard
        kb = platform_keyboard("test")
        assert len(kb.inline_keyboard) >= 2

    def test_time_keyboard(self):
        from src.telegram_yuki.keyboards import time_keyboard
        kb = time_keyboard("test")
        assert len(kb.inline_keyboard) >= 2

    def test_reject_reasons_keyboard(self):
        from src.telegram_yuki.keyboards import reject_reasons_keyboard
        kb = reject_reasons_keyboard("test")
        assert len(kb.inline_keyboard) >= 2

    def test_feedback_keyboard(self):
        from src.telegram_yuki.keyboards import feedback_keyboard
        kb = feedback_keyboard("test")
        assert len(kb.inline_keyboard) == 2
