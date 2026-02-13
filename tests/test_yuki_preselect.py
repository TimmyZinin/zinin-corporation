"""Tests for Yuki pre-selection: platform detection, preselect keyboards, callbacks, approve skip."""

import pytest


# ── Platform parsing ──────────────────────────────────────────────────────────

class TestPlatformParsing:
    """_parse_author_topic now returns 4-tuple (author, brand, topic, platform)."""

    def test_returns_4_tuple(self):
        from src.telegram_yuki.handlers.commands import _parse_author_topic
        result = _parse_author_topic("пост AI-агенты")
        assert len(result) == 4

    def test_no_platform_returns_none(self):
        from src.telegram_yuki.handlers.commands import _parse_author_topic
        _, _, _, platform = _parse_author_topic("пост AI-агенты")
        assert platform is None

    def test_detects_threads_russian(self):
        from src.telegram_yuki.handlers.commands import _parse_author_topic
        _, _, topic, platform = _parse_author_topic("пост для тредс AI-агенты")
        assert platform == "threads"
        assert "AI-агенты" in topic

    def test_detects_threads_english(self):
        from src.telegram_yuki.handlers.commands import _parse_author_topic
        _, _, _, platform = _parse_author_topic("post threads AI trends")
        assert platform == "threads"

    def test_detects_linkedin_russian(self):
        from src.telegram_yuki.handlers.commands import _parse_author_topic
        _, _, _, platform = _parse_author_topic("пост для линкедин о продуктивности")
        assert platform == "linkedin"

    def test_detects_linkedin_english(self):
        from src.telegram_yuki.handlers.commands import _parse_author_topic
        _, _, _, platform = _parse_author_topic("пост linkedin AI tools")
        assert platform == "linkedin"

    def test_detects_telegram_russian(self):
        from src.telegram_yuki.handlers.commands import _parse_author_topic
        _, _, _, platform = _parse_author_topic("пост для телеграм AI обзор")
        assert platform == "telegram"

    def test_detects_all_platforms_russian(self):
        from src.telegram_yuki.handlers.commands import _parse_author_topic
        _, _, _, platform = _parse_author_topic("пост для все платформы AI")
        assert platform == "all"

    def test_detects_all_english(self):
        from src.telegram_yuki.handlers.commands import _parse_author_topic
        _, _, _, platform = _parse_author_topic("пост all AI-тренды")
        assert platform == "all"

    def test_platform_stripped_from_topic(self):
        from src.telegram_yuki.handlers.commands import _parse_author_topic
        _, _, topic, platform = _parse_author_topic("пост для тредс AI и ML")
        assert platform == "threads"
        assert "тредс" not in topic.lower()
        assert "для" not in topic.split()[0].lower() if topic else True

    def test_author_and_platform_combined(self):
        from src.telegram_yuki.handlers.commands import _parse_author_topic
        author, _, topic, platform = _parse_author_topic(
            "пост от Тима для тредс карьера"
        )
        assert author == "tim"
        assert platform == "threads"
        assert "карьера" in topic

    def test_brand_and_platform_combined(self):
        from src.telegram_yuki.handlers.commands import _parse_author_topic
        author, brand, _, platform = _parse_author_topic(
            "пост для личного бренда для линкедин tech trends"
        )
        assert author == "tim"
        assert brand == "personal"
        assert platform == "linkedin"


# ── PLATFORM_MAP ──────────────────────────────────────────────────────────────

class TestPlatformMap:
    """PLATFORM_MAP keys and values."""

    def test_all_russian_keys(self):
        from src.telegram_yuki.handlers.commands import PLATFORM_MAP
        assert "линкедин" in PLATFORM_MAP
        assert "тредс" in PLATFORM_MAP
        assert "телеграм" in PLATFORM_MAP
        assert "все платформы" in PLATFORM_MAP

    def test_all_english_keys(self):
        from src.telegram_yuki.handlers.commands import PLATFORM_MAP
        assert "linkedin" in PLATFORM_MAP
        assert "threads" in PLATFORM_MAP
        assert "telegram" in PLATFORM_MAP
        assert "all" in PLATFORM_MAP


# ── Preselect keyboard ────────────────────────────────────────────────────────

class TestPreSelectKeyboard:
    """preselect_keyboard() structure and buttons."""

    def test_has_three_rows(self):
        from src.telegram_yuki.keyboards import preselect_keyboard
        kb = preselect_keyboard()
        assert len(kb.inline_keyboard) == 3

    def test_first_row_authors(self):
        from src.telegram_yuki.keyboards import preselect_keyboard
        kb = preselect_keyboard()
        row = kb.inline_keyboard[0]
        assert len(row) == 2
        assert row[0].callback_data == "pre_author:kristina"
        assert row[1].callback_data == "pre_author:tim"

    def test_second_row_platforms(self):
        from src.telegram_yuki.keyboards import preselect_keyboard
        kb = preselect_keyboard()
        row = kb.inline_keyboard[1]
        assert len(row) == 3
        assert row[0].callback_data == "pre_platform:linkedin"
        assert row[1].callback_data == "pre_platform:threads"
        assert row[2].callback_data == "pre_platform:telegram"

    def test_third_row_all(self):
        from src.telegram_yuki.keyboards import preselect_keyboard
        kb = preselect_keyboard()
        row = kb.inline_keyboard[2]
        assert len(row) == 1
        assert row[0].callback_data == "pre_platform:all"

    def test_checkmark_on_current_author(self):
        from src.telegram_yuki.keyboards import preselect_keyboard
        kb = preselect_keyboard(current_author="tim")
        row = kb.inline_keyboard[0]
        # Tim should have checkmark
        assert "✓" in row[1].text
        # Kristina should not
        assert "✓" not in row[0].text

    def test_checkmark_on_current_platform(self):
        from src.telegram_yuki.keyboards import preselect_keyboard
        kb = preselect_keyboard(current_platform="threads")
        row = kb.inline_keyboard[1]
        # Threads should have checkmark
        assert "✓" in row[1].text
        # LinkedIn should not
        assert "✓" not in row[0].text


# ── Preselect confirm keyboard ────────────────────────────────────────────────

class TestPreSelectConfirmKeyboard:
    """preselect_confirm_keyboard() buttons."""

    def test_has_one_row(self):
        from src.telegram_yuki.keyboards import preselect_confirm_keyboard
        kb = preselect_confirm_keyboard()
        assert len(kb.inline_keyboard) == 1

    def test_two_buttons(self):
        from src.telegram_yuki.keyboards import preselect_confirm_keyboard
        kb = preselect_confirm_keyboard()
        row = kb.inline_keyboard[0]
        assert len(row) == 2
        assert row[0].callback_data == "pre_go"
        assert row[1].callback_data == "pre_change"


# ── Preselect state ──────────────────────────────────────────────────────────

class TestPreSelectState:
    """_preselect_state dict operations."""

    def test_state_set_and_get(self):
        from src.telegram_yuki.handlers.callbacks import _preselect_state
        _preselect_state[999] = {"topic": "test", "author": "kristina", "brand": "sborka"}
        assert _preselect_state[999]["topic"] == "test"
        _preselect_state.pop(999, None)  # cleanup

    def test_state_consume(self):
        from src.telegram_yuki.handlers.callbacks import _preselect_state
        _preselect_state[888] = {"topic": "x", "author": "tim"}
        consumed = _preselect_state.pop(888, None)
        assert consumed is not None
        assert consumed["author"] == "tim"
        assert 888 not in _preselect_state

    def test_state_missing_user(self):
        from src.telegram_yuki.handlers.callbacks import _preselect_state
        assert _preselect_state.get(777) is None


# ── Callback handlers exist ──────────────────────────────────────────────────

class TestPreSelectCallbacksExist:
    """Pre-selection callback handlers are registered."""

    def test_on_pre_author_exists(self):
        from src.telegram_yuki.handlers.callbacks import on_pre_author
        assert callable(on_pre_author)

    def test_on_pre_platform_exists(self):
        from src.telegram_yuki.handlers.callbacks import on_pre_platform
        assert callable(on_pre_platform)

    def test_on_pre_go_exists(self):
        from src.telegram_yuki.handlers.callbacks import on_pre_go
        assert callable(on_pre_go)

    def test_on_pre_change_exists(self):
        from src.telegram_yuki.handlers.callbacks import on_pre_change
        assert callable(on_pre_change)


# ── Approve skip logic ───────────────────────────────────────────────────────

class TestApproveSkipsPlatform:
    """When platforms are pre-selected (not default linkedin), approve skips platform_keyboard."""

    def test_draft_with_preselected_threads(self):
        """Draft with platforms=['threads'] should skip platform selection."""
        from src.telegram_yuki.drafts import DraftManager
        post_id = DraftManager.create_draft(
            topic="test skip", text="body", platforms=["threads"],
        )
        draft = DraftManager.get_draft(post_id)
        assert draft["platforms"] == ["threads"]
        # Not default → approve should skip platform_keyboard
        assert draft["platforms"] != ["linkedin"]
        DraftManager._drafts.pop(post_id, None)

    def test_draft_with_default_linkedin(self):
        """Draft with platforms=['linkedin'] should show platform selection."""
        from src.telegram_yuki.drafts import DraftManager
        post_id = DraftManager.create_draft(
            topic="test default", text="body",
        )
        draft = DraftManager.get_draft(post_id)
        assert draft["platforms"] == ["linkedin"]
        DraftManager._drafts.pop(post_id, None)

    def test_draft_with_all_platforms(self):
        """Draft with all platforms should skip platform selection."""
        from src.telegram_yuki.drafts import DraftManager
        post_id = DraftManager.create_draft(
            topic="test all", text="body",
            platforms=["linkedin", "threads", "telegram"],
        )
        draft = DraftManager.get_draft(post_id)
        assert len(draft["platforms"]) == 3
        assert draft["platforms"] != ["linkedin"]
        DraftManager._drafts.pop(post_id, None)


# ── Generate post flow accepts platform ──────────────────────────────────────

class TestGeneratePostFlowSignature:
    """_generate_post_flow accepts platform parameter."""

    def test_accepts_platform_kwarg(self):
        import inspect
        from src.telegram_yuki.handlers.messages import _generate_post_flow
        sig = inspect.signature(_generate_post_flow)
        assert "platform" in sig.parameters
        assert sig.parameters["platform"].default == "linkedin"
