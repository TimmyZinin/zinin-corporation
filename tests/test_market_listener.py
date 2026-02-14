"""Tests for Market Listener — topic scanning and persistence."""

import json
import os
import pytest

from src.market_listener import (
    get_today_topics,
    format_topics_for_menu,
    _load_insights,
    _save_insights,
    SEARCH_QUERIES,
)


@pytest.fixture(autouse=True)
def _clean_insights(monkeypatch, tmp_path):
    """Use temp file for insights during tests."""
    tmp_file = str(tmp_path / "market_insights.json")
    import src.market_listener as mod
    monkeypatch.setattr(mod, "_INSIGHTS_PATH", tmp_file)
    yield


class TestGetTodayTopics:

    def test_empty_when_no_scan(self):
        assert get_today_topics() == []

    def test_returns_topics_for_today(self):
        from datetime import date
        data = {
            "scans": [
                {
                    "date": date.today().isoformat(),
                    "topics": ["Topic A", "Topic B", "Topic C"],
                    "snippets_count": 3,
                }
            ],
            "updated_at": "2026-02-14T10:00:00",
        }
        _save_insights(data)
        topics = get_today_topics()
        assert topics == ["Topic A", "Topic B", "Topic C"]

    def test_ignores_old_dates(self):
        data = {
            "scans": [
                {
                    "date": "2020-01-01",
                    "topics": ["Old topic"],
                    "snippets_count": 1,
                }
            ],
            "updated_at": "",
        }
        _save_insights(data)
        assert get_today_topics() == []


class TestSaveAndLoadInsights:

    def test_save_and_load(self):
        data = {"scans": [{"date": "2026-02-14", "topics": ["A"]}], "updated_at": "x"}
        assert _save_insights(data) is True
        loaded = _load_insights()
        assert loaded["scans"][0]["topics"] == ["A"]

    def test_load_empty(self):
        data = _load_insights()
        assert data == {"scans": [], "updated_at": ""}


class TestFormatTopicsForMenu:

    def test_empty(self):
        result = format_topics_for_menu([])
        assert "Нет свежих тем" in result

    def test_with_topics(self):
        result = format_topics_for_menu(["Topic 1", "Topic 2"])
        assert "Горячие темы" in result
        assert "1." in result
        assert "2." in result
        assert "Topic 1" in result
        assert "Topic 2" in result

    def test_truncates_long_topics(self):
        long_topic = "A" * 200
        result = format_topics_for_menu([long_topic])
        # Should be truncated at 80
        assert len(result) < 250


class TestSearchQueries:

    def test_has_queries(self):
        assert len(SEARCH_QUERIES) >= 3

    def test_queries_are_strings(self):
        for q in SEARCH_QUERIES:
            assert isinstance(q, str)
            assert len(q) > 10


class TestDraftManagerNewFields:
    """Verify DraftManager creates drafts with new fields."""

    def test_draft_has_platform_texts(self):
        from src.telegram_yuki.drafts import DraftManager
        post_id = DraftManager.create_draft(topic="Test", text="Hello")
        draft = DraftManager.get_draft(post_id)
        assert "platform_texts" in draft
        assert draft["platform_texts"] == {}

    def test_draft_has_platform_status(self):
        from src.telegram_yuki.drafts import DraftManager
        post_id = DraftManager.create_draft(topic="Test", text="Hello")
        draft = DraftManager.get_draft(post_id)
        assert "platform_status" in draft
        assert draft["platform_status"] == {}

    def test_draft_has_ratings(self):
        from src.telegram_yuki.drafts import DraftManager
        post_id = DraftManager.create_draft(topic="Test", text="Hello")
        draft = DraftManager.get_draft(post_id)
        assert "ratings" in draft
        assert draft["ratings"] == {"text": 0, "image": 0, "overall": 0}

    def test_draft_has_rating_step(self):
        from src.telegram_yuki.drafts import DraftManager
        post_id = DraftManager.create_draft(topic="Test", text="Hello")
        draft = DraftManager.get_draft(post_id)
        assert "rating_step" in draft
        assert draft["rating_step"] == ""


class TestDraftManagerImageFeedback:
    """Verify DraftManager image feedback state methods."""

    def test_set_get_clear_image_feedback(self):
        from src.telegram_yuki.drafts import DraftManager
        user_id = 99999

        assert DraftManager.get_image_feedback(user_id) is None

        DraftManager.set_image_feedback(user_id, "post123")
        assert DraftManager.get_image_feedback(user_id) == "post123"

        DraftManager.clear_image_feedback(user_id)
        assert DraftManager.get_image_feedback(user_id) is None


class TestContentCalendarV3:
    """Verify seed_sborka_launch_v3 exists and works."""

    def test_seed_v3_exists(self, monkeypatch, tmp_path):
        import src.content_calendar as cal
        tmp_file = str(tmp_path / "cal.json")
        monkeypatch.setattr(cal, "_CALENDAR_PATH", tmp_file)

        from src.content_calendar import seed_sborka_launch_v3
        entries = seed_sborka_launch_v3()
        assert len(entries) == 7

    def test_seed_v3_dates(self, monkeypatch, tmp_path):
        import src.content_calendar as cal
        tmp_file = str(tmp_path / "cal.json")
        monkeypatch.setattr(cal, "_CALENDAR_PATH", tmp_file)

        from src.content_calendar import seed_sborka_launch_v3
        entries = seed_sborka_launch_v3()
        dates = [e["date"] for e in entries]
        assert "2026-02-14" in dates
        assert "2026-02-15" in dates
        assert "2026-02-16" in dates
        assert "2026-02-17" in dates

    def test_seed_v3_has_both_authors(self, monkeypatch, tmp_path):
        import src.content_calendar as cal
        tmp_file = str(tmp_path / "cal.json")
        monkeypatch.setattr(cal, "_CALENDAR_PATH", tmp_file)

        from src.content_calendar import seed_sborka_launch_v3
        entries = seed_sborka_launch_v3()
        authors = {e["author"] for e in entries}
        assert "kristina" in authors
        assert "tim" in authors
        assert "both" in authors

    def test_seed_v3_all_sborka_brand(self, monkeypatch, tmp_path):
        import src.content_calendar as cal
        tmp_file = str(tmp_path / "cal.json")
        monkeypatch.setattr(cal, "_CALENDAR_PATH", tmp_file)

        from src.content_calendar import seed_sborka_launch_v3
        entries = seed_sborka_launch_v3()
        for e in entries:
            assert e["brand"] == "sborka"
