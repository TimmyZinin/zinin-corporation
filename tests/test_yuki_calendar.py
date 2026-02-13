"""Tests for Yuki calendar integration — /calendar, /plan, auto mark_done."""

import json
import os
import tempfile
from datetime import date
from unittest.mock import patch

import pytest

# Patch calendar path before importing
_tmpdir = tempfile.mkdtemp()
_test_calendar_path = os.path.join(_tmpdir, "test_calendar.json")


@pytest.fixture(autouse=True)
def clean_calendar():
    """Reset calendar for each test."""
    if os.path.exists(_test_calendar_path):
        os.remove(_test_calendar_path)
    with patch("src.content_calendar._CALENDAR_PATH", _test_calendar_path):
        yield


# ── content_calendar: get_entry_by_id ──────────────────────────────────


class TestGetEntryById:
    def test_returns_entry(self, clean_calendar):
        with patch("src.content_calendar._CALENDAR_PATH", _test_calendar_path):
            from src.content_calendar import add_entry, get_entry_by_id
            entry = add_entry(entry_date="2026-02-13", topic="Test topic", brand="sborka")
            result = get_entry_by_id(entry["id"])
            assert result is not None
            assert result["topic"] == "Test topic"

    def test_returns_none_for_unknown(self, clean_calendar):
        with patch("src.content_calendar._CALENDAR_PATH", _test_calendar_path):
            from src.content_calendar import get_entry_by_id
            result = get_entry_by_id("nonexistent")
            assert result is None


# ── content_calendar: update_entry ─────────────────────────────────────


class TestUpdateEntry:
    def test_update_topic(self, clean_calendar):
        with patch("src.content_calendar._CALENDAR_PATH", _test_calendar_path):
            from src.content_calendar import add_entry, update_entry, get_entry_by_id
            entry = add_entry(entry_date="2026-02-13", topic="Old topic", brand="sborka")
            result = update_entry(entry["id"], topic="New topic")
            assert result is True
            updated = get_entry_by_id(entry["id"])
            assert updated["topic"] == "New topic"

    def test_update_multiple_fields(self, clean_calendar):
        with patch("src.content_calendar._CALENDAR_PATH", _test_calendar_path):
            from src.content_calendar import add_entry, update_entry, get_entry_by_id
            entry = add_entry(entry_date="2026-02-13", topic="Topic", author="tim", brand="sborka")
            update_entry(entry["id"], author="kristina", platform="threads")
            updated = get_entry_by_id(entry["id"])
            assert updated["author"] == "kristina"
            assert updated["platform"] == "threads"

    def test_update_unknown_id(self, clean_calendar):
        with patch("src.content_calendar._CALENDAR_PATH", _test_calendar_path):
            from src.content_calendar import update_entry
            result = update_entry("nonexistent", topic="whatever")
            assert result is False

    def test_update_ignores_disallowed_fields(self, clean_calendar):
        with patch("src.content_calendar._CALENDAR_PATH", _test_calendar_path):
            from src.content_calendar import add_entry, update_entry, get_entry_by_id
            entry = add_entry(entry_date="2026-02-13", topic="Topic", brand="sborka")
            update_entry(entry["id"], id="hacked", post_id="injected")
            updated = get_entry_by_id(entry["id"])
            assert updated["id"] == entry["id"]  # unchanged
            assert updated["post_id"] == ""  # unchanged


# ── content_calendar: seed_sborka_launch_v2 ────────────────────────────


class TestSeedSborkaV2:
    def test_creates_5_entries(self, clean_calendar):
        with patch("src.content_calendar._CALENDAR_PATH", _test_calendar_path):
            from src.content_calendar import seed_sborka_launch_v2
            entries = seed_sborka_launch_v2()
            assert len(entries) == 5

    def test_dates_feb_13_17(self, clean_calendar):
        with patch("src.content_calendar._CALENDAR_PATH", _test_calendar_path):
            from src.content_calendar import seed_sborka_launch_v2
            entries = seed_sborka_launch_v2()
            dates = [e["date"] for e in entries]
            assert "2026-02-13" in dates
            assert "2026-02-14" in dates
            assert "2026-02-15" in dates
            assert "2026-02-16" in dates
            assert "2026-02-17" in dates

    def test_all_sborka_brand(self, clean_calendar):
        with patch("src.content_calendar._CALENDAR_PATH", _test_calendar_path):
            from src.content_calendar import seed_sborka_launch_v2
            entries = seed_sborka_launch_v2()
            for e in entries:
                assert e["brand"] == "sborka"

    def test_webinar_on_feb_17(self, clean_calendar):
        with patch("src.content_calendar._CALENDAR_PATH", _test_calendar_path):
            from src.content_calendar import seed_sborka_launch_v2
            entries = seed_sborka_launch_v2()
            feb17 = [e for e in entries if e["date"] == "2026-02-17"]
            assert len(feb17) == 1
            assert "LIVE" in feb17[0]["topic"] or "вебинар" in feb17[0]["topic"].lower()
            assert feb17[0]["author"] == "both"

    def test_all_have_cta(self, clean_calendar):
        with patch("src.content_calendar._CALENDAR_PATH", _test_calendar_path):
            from src.content_calendar import seed_sborka_launch_v2
            entries = seed_sborka_launch_v2()
            for e in entries:
                assert e["cta"], f"Entry {e['date']} has no CTA"
                assert "@sborka_career_bot" in e["cta"]


# ── keyboards: calendar keyboards ──────────────────────────────────────


class TestCalendarKeyboards:
    def test_calendar_entry_keyboard(self):
        from src.telegram_yuki.keyboards import calendar_entry_keyboard
        kb = calendar_entry_keyboard("abc12345")
        buttons = []
        for row in kb.inline_keyboard:
            for btn in row:
                buttons.append(btn.callback_data)
        assert "cal_gen:abc12345" in buttons
        assert "cal_skip:abc12345" in buttons
        assert "cal_edit:abc12345" in buttons

    def test_plan_source_keyboard_with_entries(self):
        from src.telegram_yuki.keyboards import plan_source_keyboard
        kb = plan_source_keyboard(has_entries=True)
        data = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert "plan_cal" in data
        assert "plan_new" in data

    def test_plan_source_keyboard_without_entries(self):
        from src.telegram_yuki.keyboards import plan_source_keyboard
        kb = plan_source_keyboard(has_entries=False)
        data = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert "plan_cal" not in data
        assert "plan_new" in data

    def test_calendar_pick_keyboard(self):
        from src.telegram_yuki.keyboards import calendar_pick_keyboard
        entries = [
            {"id": "aaa11111", "topic": "Topic A", "author": "tim"},
            {"id": "bbb22222", "topic": "Topic B", "author": "kristina"},
        ]
        kb = calendar_pick_keyboard(entries)
        data = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert "plan_pick:aaa11111" in data
        assert "plan_pick:bbb22222" in data

    def test_calendar_pick_truncates_long_topics(self):
        from src.telegram_yuki.keyboards import calendar_pick_keyboard
        entries = [
            {"id": "ccc33333", "topic": "A" * 60, "author": "tim"},
        ]
        kb = calendar_pick_keyboard(entries)
        btn_text = kb.inline_keyboard[0][0].text
        assert len(btn_text) < 60  # Should be truncated

    def test_calendar_pick_max_5(self):
        from src.telegram_yuki.keyboards import calendar_pick_keyboard
        entries = [{"id": f"id{i}", "topic": f"T{i}", "author": "tim"} for i in range(10)]
        kb = calendar_pick_keyboard(entries)
        assert len(kb.inline_keyboard) == 5


# ── callbacks: state management ────────────────────────────────────────


class TestCalendarCallbackState:
    def test_calendar_edit_state_dict_exists(self):
        from src.telegram_yuki.handlers.callbacks import _calendar_edit_state
        assert isinstance(_calendar_edit_state, dict)

    def test_plan_custom_state_set_exists(self):
        from src.telegram_yuki.handlers.callbacks import _plan_custom_state
        assert isinstance(_plan_custom_state, set)

    def test_preselect_state_supports_calendar_entry_id(self):
        from src.telegram_yuki.handlers.callbacks import _preselect_state
        _preselect_state[99999] = {
            "topic": "test",
            "author": "tim",
            "brand": "sborka",
            "calendar_entry_id": "abc123",
        }
        assert _preselect_state[99999]["calendar_entry_id"] == "abc123"
        del _preselect_state[99999]


# ── auto mark_done ─────────────────────────────────────────────────────


class TestAutoMarkDone:
    def test_mark_done_with_calendar_entry(self, clean_calendar):
        with patch("src.content_calendar._CALENDAR_PATH", _test_calendar_path):
            from src.content_calendar import add_entry, get_entry_by_id, mark_done
            entry = add_entry(entry_date="2026-02-13", topic="Test", brand="sborka")
            mark_done(entry["id"], post_id="post_123")
            updated = get_entry_by_id(entry["id"])
            assert updated["status"] == "done"
            assert updated["post_id"] == "post_123"

    def test_mark_done_unknown_entry_returns_false(self, clean_calendar):
        with patch("src.content_calendar._CALENDAR_PATH", _test_calendar_path):
            from src.content_calendar import mark_done
            result = mark_done("nonexistent", post_id="post_456")
            assert result is False

    def test_mark_skipped(self, clean_calendar):
        with patch("src.content_calendar._CALENDAR_PATH", _test_calendar_path):
            from src.content_calendar import add_entry, get_entry_by_id, mark_skipped
            entry = add_entry(entry_date="2026-02-13", topic="Skip me", brand="sborka")
            mark_skipped(entry["id"])
            updated = get_entry_by_id(entry["id"])
            assert updated["status"] == "skipped"
