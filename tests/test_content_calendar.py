"""Tests for Content Calendar module."""

import json
import os
import pytest
from unittest.mock import patch
from datetime import date, timedelta


class TestCalendarPath:
    """Test _calendar_path() resolution."""

    def test_returns_json_path(self):
        from src.content_calendar import _calendar_path
        path = _calendar_path()
        assert path.endswith("content_calendar.json")

    def test_path_contains_data_dir(self):
        from src.content_calendar import _calendar_path
        path = _calendar_path()
        assert "data" in path


class TestLoadSave:
    """Test JSON load/save."""

    def test_load_returns_empty_when_no_file(self, tmp_path):
        from src.content_calendar import _load_calendar
        with patch("src.content_calendar._calendar_path", return_value=str(tmp_path / "nope.json")):
            data = _load_calendar()
        assert data == {"entries": [], "updated_at": ""}

    def test_save_and_load_roundtrip(self, tmp_path):
        from src.content_calendar import _save_calendar, _load_calendar
        path = str(tmp_path / "cal.json")
        test_data = {"entries": [{"id": "test"}], "updated_at": "now"}
        with patch("src.content_calendar._calendar_path", return_value=path):
            assert _save_calendar(test_data)
            loaded = _load_calendar()
        assert len(loaded["entries"]) == 1
        assert loaded["entries"][0]["id"] == "test"

    def test_load_handles_corrupt_json(self, tmp_path):
        from src.content_calendar import _load_calendar
        path = str(tmp_path / "bad.json")
        with open(path, "w") as f:
            f.write("not json")
        with patch("src.content_calendar._calendar_path", return_value=path):
            data = _load_calendar()
        assert data == {"entries": [], "updated_at": ""}


class TestAddEntry:
    """Test add_entry()."""

    def test_returns_entry_with_id(self, tmp_path):
        from src.content_calendar import add_entry
        path = str(tmp_path / "cal.json")
        with patch("src.content_calendar._calendar_path", return_value=path):
            entry = add_entry(entry_date="2026-02-14", topic="Test post")
        assert "id" in entry
        assert len(entry["id"]) == 8

    def test_entry_has_required_fields(self, tmp_path):
        from src.content_calendar import add_entry
        path = str(tmp_path / "cal.json")
        with patch("src.content_calendar._calendar_path", return_value=path):
            entry = add_entry(
                entry_date="2026-02-14",
                topic="AI agents",
                author="kristina",
                platform="linkedin",
                cta="Subscribe",
                brand="sborka",
            )
        assert entry["topic"] == "AI agents"
        assert entry["author"] == "kristina"
        assert entry["platform"] == "linkedin"
        assert entry["cta"] == "Subscribe"
        assert entry["brand"] == "sborka"
        assert entry["status"] == "planned"

    def test_entry_persisted(self, tmp_path):
        from src.content_calendar import add_entry, get_all_entries
        path = str(tmp_path / "cal.json")
        with patch("src.content_calendar._calendar_path", return_value=path):
            add_entry(entry_date="2026-02-14", topic="Post 1")
            add_entry(entry_date="2026-02-15", topic="Post 2")
            entries = get_all_entries()
        assert len(entries) == 2


class TestGetToday:
    """Test get_today()."""

    def test_returns_only_today_entries(self, tmp_path):
        from src.content_calendar import add_entry, get_today
        path = str(tmp_path / "cal.json")
        today = date.today().isoformat()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        with patch("src.content_calendar._calendar_path", return_value=path):
            add_entry(entry_date=today, topic="Today post")
            add_entry(entry_date=tomorrow, topic="Tomorrow post")
            today_entries = get_today()
        assert len(today_entries) == 1
        assert today_entries[0]["topic"] == "Today post"

    def test_returns_empty_when_no_today(self, tmp_path):
        from src.content_calendar import add_entry, get_today
        path = str(tmp_path / "cal.json")
        with patch("src.content_calendar._calendar_path", return_value=path):
            add_entry(entry_date="2020-01-01", topic="Old post")
            result = get_today()
        assert result == []


class TestGetDate:
    """Test get_date()."""

    def test_returns_entries_for_date(self, tmp_path):
        from src.content_calendar import add_entry, get_date
        path = str(tmp_path / "cal.json")
        with patch("src.content_calendar._calendar_path", return_value=path):
            add_entry(entry_date="2026-02-14", topic="Post A")
            add_entry(entry_date="2026-02-14", topic="Post B")
            add_entry(entry_date="2026-02-15", topic="Post C")
            result = get_date("2026-02-14")
        assert len(result) == 2


class TestGetWeek:
    """Test get_week()."""

    def test_returns_entries_within_7_days(self, tmp_path):
        from src.content_calendar import add_entry, get_week
        path = str(tmp_path / "cal.json")
        today = date.today()
        with patch("src.content_calendar._calendar_path", return_value=path):
            add_entry(entry_date=today.isoformat(), topic="Today")
            add_entry(entry_date=(today + timedelta(days=3)).isoformat(), topic="Day 3")
            add_entry(entry_date=(today + timedelta(days=10)).isoformat(), topic="Day 10")
            week = get_week()
        assert len(week) == 2


class TestGetOverdue:
    """Test get_overdue()."""

    def test_returns_past_undone_entries(self, tmp_path):
        from src.content_calendar import add_entry, get_overdue
        path = str(tmp_path / "cal.json")
        with patch("src.content_calendar._calendar_path", return_value=path):
            add_entry(entry_date="2020-01-01", topic="Old planned")
            add_entry(entry_date="2099-12-31", topic="Future planned")
            overdue = get_overdue()
        assert len(overdue) == 1
        assert overdue[0]["topic"] == "Old planned"

    def test_done_entries_not_overdue(self, tmp_path):
        from src.content_calendar import add_entry, mark_done, get_overdue
        path = str(tmp_path / "cal.json")
        with patch("src.content_calendar._calendar_path", return_value=path):
            entry = add_entry(entry_date="2020-01-01", topic="Old done")
            mark_done(entry["id"])
            overdue = get_overdue()
        assert len(overdue) == 0

    def test_skipped_entries_not_overdue(self, tmp_path):
        from src.content_calendar import add_entry, mark_skipped, get_overdue
        path = str(tmp_path / "cal.json")
        with patch("src.content_calendar._calendar_path", return_value=path):
            entry = add_entry(entry_date="2020-01-01", topic="Old skipped")
            mark_skipped(entry["id"])
            overdue = get_overdue()
        assert len(overdue) == 0


class TestMarkDone:
    """Test mark_done()."""

    def test_marks_entry_done(self, tmp_path):
        from src.content_calendar import add_entry, mark_done, get_all_entries
        path = str(tmp_path / "cal.json")
        with patch("src.content_calendar._calendar_path", return_value=path):
            entry = add_entry(entry_date="2026-02-14", topic="Done post")
            result = mark_done(entry["id"], post_id="POST123")
            entries = get_all_entries()
        assert result is True
        assert entries[0]["status"] == "done"
        assert entries[0]["post_id"] == "POST123"

    def test_returns_false_for_unknown_id(self, tmp_path):
        from src.content_calendar import mark_done
        path = str(tmp_path / "cal.json")
        with patch("src.content_calendar._calendar_path", return_value=path):
            result = mark_done("nonexistent")
        assert result is False


class TestMarkSkipped:
    """Test mark_skipped()."""

    def test_marks_entry_skipped(self, tmp_path):
        from src.content_calendar import add_entry, mark_skipped, get_all_entries
        path = str(tmp_path / "cal.json")
        with patch("src.content_calendar._calendar_path", return_value=path):
            entry = add_entry(entry_date="2026-02-14", topic="Skip post")
            mark_skipped(entry["id"])
            entries = get_all_entries()
        assert entries[0]["status"] == "skipped"


class TestFormatTodayPlan:
    """Test format_today_plan()."""

    def test_empty_plan(self, tmp_path):
        from src.content_calendar import format_today_plan
        path = str(tmp_path / "cal.json")
        with patch("src.content_calendar._calendar_path", return_value=path):
            text = format_today_plan()
        assert "пусто" in text

    def test_with_entries(self, tmp_path):
        from src.content_calendar import add_entry, format_today_plan
        path = str(tmp_path / "cal.json")
        today = date.today().isoformat()
        with patch("src.content_calendar._calendar_path", return_value=path):
            add_entry(entry_date=today, topic="AI post", author="tim", platform="linkedin")
            text = format_today_plan()
        assert "AI post" in text
        assert "Сегодня" in text

    def test_shows_overdue(self, tmp_path):
        from src.content_calendar import add_entry, format_today_plan
        path = str(tmp_path / "cal.json")
        with patch("src.content_calendar._calendar_path", return_value=path):
            add_entry(entry_date="2020-01-01", topic="Old post")
            text = format_today_plan()
        assert "Просрочено" in text


class TestFormatWeekPlan:
    """Test format_week_plan()."""

    def test_empty_plan(self, tmp_path):
        from src.content_calendar import format_week_plan
        path = str(tmp_path / "cal.json")
        with patch("src.content_calendar._calendar_path", return_value=path):
            text = format_week_plan()
        assert "пусто" in text

    def test_with_entries(self, tmp_path):
        from src.content_calendar import add_entry, format_week_plan
        path = str(tmp_path / "cal.json")
        today = date.today().isoformat()
        with patch("src.content_calendar._calendar_path", return_value=path):
            add_entry(entry_date=today, topic="Weekly post")
            text = format_week_plan()
        assert "Weekly post" in text
        assert "неделю" in text


class TestSeedSborkaLaunch:
    """Test seed_sborka_launch()."""

    def test_creates_5_entries(self, tmp_path):
        from src.content_calendar import seed_sborka_launch, get_all_entries
        path = str(tmp_path / "cal.json")
        with patch("src.content_calendar._calendar_path", return_value=path):
            created = seed_sborka_launch()
            all_entries = get_all_entries()
        assert len(created) == 5
        assert len(all_entries) == 5

    def test_entries_have_sborka_brand(self, tmp_path):
        from src.content_calendar import seed_sborka_launch
        path = str(tmp_path / "cal.json")
        with patch("src.content_calendar._calendar_path", return_value=path):
            created = seed_sborka_launch()
        for entry in created:
            assert entry["brand"] == "sborka"

    def test_entries_have_dates_feb_14_18(self, tmp_path):
        from src.content_calendar import seed_sborka_launch
        path = str(tmp_path / "cal.json")
        with patch("src.content_calendar._calendar_path", return_value=path):
            created = seed_sborka_launch()
        dates = [e["date"] for e in created]
        assert "2026-02-14" in dates
        assert "2026-02-18" in dates

    def test_launch_day_is_both_authors(self, tmp_path):
        from src.content_calendar import seed_sborka_launch
        path = str(tmp_path / "cal.json")
        with patch("src.content_calendar._calendar_path", return_value=path):
            created = seed_sborka_launch()
        launch = [e for e in created if e["date"] == "2026-02-18"][0]
        assert launch["author"] == "both"

    def test_entries_have_cta(self, tmp_path):
        from src.content_calendar import seed_sborka_launch
        path = str(tmp_path / "cal.json")
        with patch("src.content_calendar._calendar_path", return_value=path):
            created = seed_sborka_launch()
        for entry in created:
            assert entry["cta"] != ""
