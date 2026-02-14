"""Tests for Yuki menu-first UX — keyboards, platform codes, callback data sizes."""

import pytest

from src.telegram_yuki.keyboards import (
    start_menu_keyboard,
    author_submenu_keyboard,
    multiplatform_post_keyboard,
    publish_all_keyboard,
    published_lock_keyboard,
    rating_keyboard,
    image_offer_keyboard,
    image_review_keyboard,
    preselect_keyboard,
    approval_keyboard,
    post_ready_keyboard,
    approval_with_image_keyboard,
    final_choice_keyboard,
    feedback_keyboard,
    calendar_entry_keyboard,
    plan_source_keyboard,
    calendar_pick_keyboard,
    preselect_confirm_keyboard,
    PLAT_SHORT,
    PLAT_LONG,
    PLAT_EMOJI,
)


class TestPlatformCodes:

    def test_plat_short_mapping(self):
        assert PLAT_SHORT == {"linkedin": "li", "threads": "th", "telegram": "tg"}

    def test_plat_long_reverse(self):
        assert PLAT_LONG == {"li": "linkedin", "th": "threads", "tg": "telegram"}

    def test_plat_emoji_coverage(self):
        for plat in PLAT_SHORT:
            assert plat in PLAT_EMOJI


class TestStartMenuKeyboard:

    def test_has_4_buttons(self):
        kb = start_menu_keyboard()
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        assert len(buttons) == 4

    def test_author_callbacks(self):
        kb = start_menu_keyboard()
        callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert "m_au:tim" in callbacks
        assert "m_au:kristina" in callbacks

    def test_calendar_and_status(self):
        kb = start_menu_keyboard()
        callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert "m_cal_view" in callbacks
        assert "m_status" in callbacks


class TestAuthorSubmenuKeyboard:

    def test_has_3_buttons(self):
        kb = author_submenu_keyboard("kristina")
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        assert len(buttons) == 3

    def test_callbacks(self):
        kb = author_submenu_keyboard("tim")
        callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert "m_cal" in callbacks
        assert "m_topic" in callbacks
        assert "m_back" in callbacks


class TestMultiplatformPostKeyboard:

    def test_has_4_buttons(self):
        kb = multiplatform_post_keyboard("abc12345", "linkedin")
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        assert len(buttons) == 4

    def test_callback_contains_platform_short(self):
        kb = multiplatform_post_keyboard("abc12345", "linkedin")
        callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert any("mp_pub:li:" in c for c in callbacks)
        assert any("mp_imp:li:" in c for c in callbacks)
        assert any("mp_sch:li:" in c for c in callbacks)
        assert any("mp_rm:li:" in c for c in callbacks)

    def test_threads_uses_th(self):
        kb = multiplatform_post_keyboard("x", "threads")
        callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert any(":th:" in c for c in callbacks)

    def test_telegram_uses_tg(self):
        kb = multiplatform_post_keyboard("x", "telegram")
        callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert any(":tg:" in c for c in callbacks)


class TestPublishAllKeyboard:

    def test_has_1_button(self):
        kb = publish_all_keyboard("abc12345")
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        assert len(buttons) == 1

    def test_callback(self):
        kb = publish_all_keyboard("test1234")
        btn = kb.inline_keyboard[0][0]
        assert btn.callback_data == "mp_all:test1234"


class TestPublishedLockKeyboard:

    def test_has_1_button(self):
        kb = published_lock_keyboard("linkedin")
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        assert len(buttons) == 1

    def test_noop_callback(self):
        kb = published_lock_keyboard("linkedin")
        btn = kb.inline_keyboard[0][0]
        assert btn.callback_data == "noop"

    def test_platform_in_text(self):
        kb = published_lock_keyboard("threads")
        btn = kb.inline_keyboard[0][0]
        assert "threads" in btn.text


class TestRatingKeyboard:

    def test_has_5_buttons(self):
        kb = rating_keyboard("r_txt", "abc12345")
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        assert len(buttons) == 5

    def test_scores_1_to_5(self):
        kb = rating_keyboard("r_ovr", "abc12345")
        buttons = kb.inline_keyboard[0]
        for i, btn in enumerate(buttons, 1):
            assert f":{i}:" in btn.callback_data

    def test_prefix_in_callback(self):
        kb = rating_keyboard("r_img", "test")
        btn = kb.inline_keyboard[0][0]
        assert btn.callback_data.startswith("r_img:")


class TestImageOfferKeyboard:

    def test_has_2_buttons(self):
        kb = image_offer_keyboard("abc12345")
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        assert len(buttons) == 2

    def test_callbacks(self):
        kb = image_offer_keyboard("x")
        callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert "pp_img:x" in callbacks
        assert "pp_skip:x" in callbacks


class TestImageReviewKeyboard:

    def test_has_4_buttons(self):
        kb = image_review_keyboard("abc12345")
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        assert len(buttons) == 4

    def test_callbacks(self):
        kb = image_review_keyboard("x")
        callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert "pp_ok:x" in callbacks
        assert "pp_redo:x" in callbacks
        assert "pp_fb:x" in callbacks
        assert "pp_no:x" in callbacks


class TestCallbackDataSizes:
    """All callback_data must be under 64 bytes (Telegram limit)."""

    def _get_all_callbacks(self, kb):
        return [btn.callback_data for row in kb.inline_keyboard for btn in row]

    def test_start_menu_under_64(self):
        for cb in self._get_all_callbacks(start_menu_keyboard()):
            assert len(cb.encode("utf-8")) <= 64, f"Too long: {cb}"

    def test_author_submenu_under_64(self):
        for author in ("tim", "kristina"):
            for cb in self._get_all_callbacks(author_submenu_keyboard(author)):
                assert len(cb.encode("utf-8")) <= 64, f"Too long: {cb}"

    def test_multiplatform_under_64(self):
        for plat in ("linkedin", "threads", "telegram"):
            for cb in self._get_all_callbacks(multiplatform_post_keyboard("abcd1234", plat)):
                assert len(cb.encode("utf-8")) <= 64, f"Too long: {cb}"

    def test_publish_all_under_64(self):
        for cb in self._get_all_callbacks(publish_all_keyboard("abcd1234")):
            assert len(cb.encode("utf-8")) <= 64, f"Too long: {cb}"

    def test_published_lock_under_64(self):
        for plat in ("linkedin", "threads", "telegram"):
            for cb in self._get_all_callbacks(published_lock_keyboard(plat)):
                assert len(cb.encode("utf-8")) <= 64, f"Too long: {cb}"

    def test_rating_under_64(self):
        for prefix in ("r_txt", "r_img", "r_ovr"):
            for cb in self._get_all_callbacks(rating_keyboard(prefix, "abcd1234")):
                assert len(cb.encode("utf-8")) <= 64, f"Too long: {cb}"

    def test_image_offer_under_64(self):
        for cb in self._get_all_callbacks(image_offer_keyboard("abcd1234")):
            assert len(cb.encode("utf-8")) <= 64, f"Too long: {cb}"

    def test_image_review_under_64(self):
        for cb in self._get_all_callbacks(image_review_keyboard("abcd1234")):
            assert len(cb.encode("utf-8")) <= 64, f"Too long: {cb}"

    def test_approval_under_64(self):
        for cb in self._get_all_callbacks(approval_keyboard("abcd1234")):
            assert len(cb.encode("utf-8")) <= 64, f"Too long: {cb}"

    def test_post_ready_under_64(self):
        for cb in self._get_all_callbacks(post_ready_keyboard("abcd1234")):
            assert len(cb.encode("utf-8")) <= 64, f"Too long: {cb}"


class TestExistingKeyboardsNotBroken:
    """Ensure existing keyboards still work after modifications."""

    def test_approval_keyboard(self):
        kb = approval_keyboard("test")
        assert len(kb.inline_keyboard) == 2

    def test_post_ready_keyboard(self):
        kb = post_ready_keyboard("test")
        assert len(kb.inline_keyboard) >= 2

    def test_approval_with_image_keyboard(self):
        kb = approval_with_image_keyboard("test")
        assert len(kb.inline_keyboard) >= 2

    def test_final_choice_keyboard(self):
        kb = final_choice_keyboard("test")
        assert len(kb.inline_keyboard) == 1

    def test_feedback_keyboard(self):
        kb = feedback_keyboard("test")
        assert len(kb.inline_keyboard) == 2

    def test_preselect_keyboard(self):
        kb = preselect_keyboard("kristina")
        assert len(kb.inline_keyboard) >= 2

    def test_preselect_confirm_keyboard(self):
        kb = preselect_confirm_keyboard()
        assert len(kb.inline_keyboard) == 1

    def test_calendar_entry_keyboard(self):
        kb = calendar_entry_keyboard("test")
        assert len(kb.inline_keyboard) == 2

    def test_plan_source_keyboard(self):
        kb = plan_source_keyboard(has_entries=True)
        assert len(kb.inline_keyboard) == 2

    def test_calendar_pick_keyboard(self):
        entries = [{"id": "a", "topic": "Test", "author": "tim"}]
        kb = calendar_pick_keyboard(entries)
        assert len(kb.inline_keyboard) == 1
