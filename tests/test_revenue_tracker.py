"""Tests for Revenue Tracker module."""

import json
import os
import pytest
from unittest.mock import patch
from datetime import date, datetime


class TestRevenueTrackerPath:
    """Test _revenue_path() resolution."""

    def test_returns_data_path(self):
        from src.revenue_tracker import _revenue_path
        path = _revenue_path()
        assert path.endswith("revenue.json")

    def test_path_contains_data_dir(self):
        from src.revenue_tracker import _revenue_path
        path = _revenue_path()
        assert "data" in path


class TestDefaultData:
    """Test default revenue data."""

    def test_default_has_channels(self):
        from src.revenue_tracker import _default_data
        data = _default_data()
        assert "channels" in data
        assert len(data["channels"]) == 5

    def test_default_has_target(self):
        from src.revenue_tracker import _default_data
        data = _default_data()
        assert data["target_mrr"] == 2500.0

    def test_default_has_deadline(self):
        from src.revenue_tracker import _default_data
        data = _default_data()
        assert data["deadline"] == "2026-03-02"

    def test_default_channels_have_required_fields(self):
        from src.revenue_tracker import _default_data
        data = _default_data()
        for key, ch in data["channels"].items():
            assert "name" in ch
            assert "mrr" in ch
            assert "members" in ch
            assert "target" in ch

    def test_default_krmktl_mrr(self):
        from src.revenue_tracker import _default_data
        data = _default_data()
        assert data["channels"]["krmktl"]["mrr"] == 350.0

    def test_default_botanica_mrr(self):
        from src.revenue_tracker import _default_data
        data = _default_data()
        assert data["channels"]["botanica"]["mrr"] == 165.0

    def test_default_history_empty(self):
        from src.revenue_tracker import _default_data
        data = _default_data()
        assert data["history"] == []


class TestLoadSave:
    """Test JSON load/save with temp files."""

    def test_load_returns_default_when_no_file(self, tmp_path):
        from src.revenue_tracker import _load_revenue
        with patch("src.revenue_tracker._revenue_path", return_value=str(tmp_path / "nope.json")):
            data = _load_revenue()
        assert data["target_mrr"] == 2500.0
        assert len(data["channels"]) == 5

    def test_save_and_load_roundtrip(self, tmp_path):
        from src.revenue_tracker import _save_revenue, _load_revenue
        path = str(tmp_path / "rev.json")
        test_data = {"target_mrr": 1000, "channels": {}, "history": [], "updated_at": ""}
        with patch("src.revenue_tracker._revenue_path", return_value=path):
            assert _save_revenue(test_data)
            loaded = _load_revenue()
        assert loaded["target_mrr"] == 1000

    def test_load_handles_corrupt_json(self, tmp_path):
        from src.revenue_tracker import _load_revenue
        path = str(tmp_path / "bad.json")
        with open(path, "w") as f:
            f.write("not json at all")
        with patch("src.revenue_tracker._revenue_path", return_value=path):
            data = _load_revenue()
        assert data["target_mrr"] == 2500.0


class TestGetRevenueSummary:
    """Test get_revenue_summary()."""

    def test_returns_dict_with_required_keys(self, tmp_path):
        from src.revenue_tracker import get_revenue_summary, _save_revenue, _default_data
        path = str(tmp_path / "rev.json")
        with patch("src.revenue_tracker._revenue_path", return_value=path):
            _save_revenue(_default_data())
            summary = get_revenue_summary()
        assert "total_mrr" in summary
        assert "gap" in summary
        assert "days_left" in summary
        assert "channels" in summary

    def test_total_mrr_sums_channels(self, tmp_path):
        from src.revenue_tracker import get_revenue_summary, _save_revenue, _default_data
        path = str(tmp_path / "rev.json")
        with patch("src.revenue_tracker._revenue_path", return_value=path):
            _save_revenue(_default_data())
            summary = get_revenue_summary()
        # 350 + 0 + 165 + 0 + 0 = 515
        assert summary["total_mrr"] == 515.0

    def test_gap_calculation(self, tmp_path):
        from src.revenue_tracker import get_revenue_summary, _save_revenue, _default_data
        path = str(tmp_path / "rev.json")
        with patch("src.revenue_tracker._revenue_path", return_value=path):
            _save_revenue(_default_data())
            summary = get_revenue_summary()
        assert summary["gap"] == 2500.0 - 515.0

    def test_gap_never_negative(self, tmp_path):
        from src.revenue_tracker import get_revenue_summary, _save_revenue
        path = str(tmp_path / "rev.json")
        data = {"target_mrr": 100, "deadline": "2026-03-02",
                "channels": {"ch": {"name": "ch", "mrr": 200, "members": 0, "target": 100}},
                "history": [], "updated_at": ""}
        with patch("src.revenue_tracker._revenue_path", return_value=path):
            _save_revenue(data)
            summary = get_revenue_summary()
        assert summary["gap"] == 0


class TestGetGap:
    """Test get_gap()."""

    def test_gap_matches_summary(self, tmp_path):
        from src.revenue_tracker import get_gap, _save_revenue, _default_data
        path = str(tmp_path / "rev.json")
        with patch("src.revenue_tracker._revenue_path", return_value=path):
            _save_revenue(_default_data())
            gap = get_gap()
        assert gap == 1985.0


class TestGetDaysLeft:
    """Test get_days_left()."""

    def test_returns_non_negative_int(self):
        from src.revenue_tracker import get_days_left
        days = get_days_left()
        assert isinstance(days, int)
        assert days >= 0


class TestUpdateChannel:
    """Test update_channel()."""

    def test_update_mrr(self, tmp_path):
        from src.revenue_tracker import update_channel, get_revenue_summary, _save_revenue, _default_data
        path = str(tmp_path / "rev.json")
        with patch("src.revenue_tracker._revenue_path", return_value=path):
            _save_revenue(_default_data())
            result = update_channel("krmktl", mrr=500.0)
        assert result["mrr"] == 500.0

    def test_update_members(self, tmp_path):
        from src.revenue_tracker import update_channel, _save_revenue, _default_data
        path = str(tmp_path / "rev.json")
        with patch("src.revenue_tracker._revenue_path", return_value=path):
            _save_revenue(_default_data())
            result = update_channel("sborka", members=20)
        assert result["members"] == 20

    def test_update_target(self, tmp_path):
        from src.revenue_tracker import update_channel, _save_revenue, _default_data
        path = str(tmp_path / "rev.json")
        with patch("src.revenue_tracker._revenue_path", return_value=path):
            _save_revenue(_default_data())
            result = update_channel("sborka", target=900.0)
        assert result["target"] == 900.0

    def test_update_creates_new_channel(self, tmp_path):
        from src.revenue_tracker import update_channel, get_revenue_summary, _save_revenue, _default_data
        path = str(tmp_path / "rev.json")
        with patch("src.revenue_tracker._revenue_path", return_value=path):
            _save_revenue(_default_data())
            update_channel("new_channel", mrr=100.0, members=5)
            summary = get_revenue_summary()
        assert "new_channel" in summary["channels"]
        assert summary["channels"]["new_channel"]["mrr"] == 100.0

    def test_update_persists(self, tmp_path):
        from src.revenue_tracker import update_channel, get_revenue_summary, _save_revenue, _default_data
        path = str(tmp_path / "rev.json")
        with patch("src.revenue_tracker._revenue_path", return_value=path):
            _save_revenue(_default_data())
            update_channel("krmktl", mrr=800.0)
            summary = get_revenue_summary()
        assert summary["channels"]["krmktl"]["mrr"] == 800.0


class TestDailySnapshot:
    """Test add_daily_snapshot()."""

    def test_snapshot_returns_dict(self, tmp_path):
        from src.revenue_tracker import add_daily_snapshot, _save_revenue, _default_data
        path = str(tmp_path / "rev.json")
        with patch("src.revenue_tracker._revenue_path", return_value=path):
            _save_revenue(_default_data())
            snap = add_daily_snapshot()
        assert "date" in snap
        assert "total_mrr" in snap
        assert "gap" in snap

    def test_snapshot_has_correct_total(self, tmp_path):
        from src.revenue_tracker import add_daily_snapshot, _save_revenue, _default_data
        path = str(tmp_path / "rev.json")
        with patch("src.revenue_tracker._revenue_path", return_value=path):
            _save_revenue(_default_data())
            snap = add_daily_snapshot()
        assert snap["total_mrr"] == 515.0

    def test_snapshot_deduplicates_same_day(self, tmp_path):
        from src.revenue_tracker import add_daily_snapshot, get_history, _save_revenue, _default_data
        path = str(tmp_path / "rev.json")
        with patch("src.revenue_tracker._revenue_path", return_value=path):
            _save_revenue(_default_data())
            add_daily_snapshot()
            add_daily_snapshot()
            history = get_history()
        today_snaps = [h for h in history if h["date"] == date.today().isoformat()]
        assert len(today_snaps) == 1

    def test_snapshot_saved_in_history(self, tmp_path):
        from src.revenue_tracker import add_daily_snapshot, get_history, _save_revenue, _default_data
        path = str(tmp_path / "rev.json")
        with patch("src.revenue_tracker._revenue_path", return_value=path):
            _save_revenue(_default_data())
            add_daily_snapshot()
            history = get_history()
        assert len(history) == 1


class TestGetHistory:
    """Test get_history()."""

    def test_empty_when_no_snapshots(self, tmp_path):
        from src.revenue_tracker import get_history, _save_revenue, _default_data
        path = str(tmp_path / "rev.json")
        with patch("src.revenue_tracker._revenue_path", return_value=path):
            _save_revenue(_default_data())
            history = get_history()
        assert history == []


class TestFormatRevenueSummary:
    """Test format_revenue_summary()."""

    def test_returns_string(self, tmp_path):
        from src.revenue_tracker import format_revenue_summary, _save_revenue, _default_data
        path = str(tmp_path / "rev.json")
        with patch("src.revenue_tracker._revenue_path", return_value=path):
            _save_revenue(_default_data())
            text = format_revenue_summary()
        assert isinstance(text, str)

    def test_contains_revenue_header(self, tmp_path):
        from src.revenue_tracker import format_revenue_summary, _save_revenue, _default_data
        path = str(tmp_path / "rev.json")
        with patch("src.revenue_tracker._revenue_path", return_value=path):
            _save_revenue(_default_data())
            text = format_revenue_summary()
        assert "Revenue Tracker" in text

    def test_contains_progress_bar(self, tmp_path):
        from src.revenue_tracker import format_revenue_summary, _save_revenue, _default_data
        path = str(tmp_path / "rev.json")
        with patch("src.revenue_tracker._revenue_path", return_value=path):
            _save_revenue(_default_data())
            text = format_revenue_summary()
        assert "█" in text or "░" in text

    def test_contains_channel_names(self, tmp_path):
        from src.revenue_tracker import format_revenue_summary, _save_revenue, _default_data
        path = str(tmp_path / "rev.json")
        with patch("src.revenue_tracker._revenue_path", return_value=path):
            _save_revenue(_default_data())
            text = format_revenue_summary()
        assert "Крипто" in text
        assert "СБОРКА" in text


class TestSeedRevenueData:
    """Test seed_revenue_data()."""

    def test_seeds_when_no_file(self, tmp_path):
        from src.revenue_tracker import seed_revenue_data
        path = str(tmp_path / "rev.json")
        with patch("src.revenue_tracker._revenue_path", return_value=path):
            result = seed_revenue_data()
        assert result is True
        assert os.path.exists(path)

    def test_does_not_overwrite_existing(self, tmp_path):
        from src.revenue_tracker import seed_revenue_data, _save_revenue
        path = str(tmp_path / "rev.json")
        with patch("src.revenue_tracker._revenue_path", return_value=path):
            _save_revenue({"custom": True})
            result = seed_revenue_data()
        assert result is False


class TestGetTotalMrr:
    """Test get_total_mrr()."""

    def test_returns_float(self, tmp_path):
        from src.revenue_tracker import get_total_mrr, _save_revenue, _default_data
        path = str(tmp_path / "rev.json")
        with patch("src.revenue_tracker._revenue_path", return_value=path):
            _save_revenue(_default_data())
            total = get_total_mrr()
        assert isinstance(total, float)
        assert total == 515.0
