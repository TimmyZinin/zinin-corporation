"""Tests for competitor analysis module."""

import time
import pytest
from unittest.mock import patch


class TestCompetitorInsightsLoadSave:
    """Test JSON load/save persistence."""

    @patch("src.competitor_analysis._INSIGHTS_PATH", "/tmp/test_comp_insights.json")
    def test_load_returns_defaults_when_no_file(self):
        import os
        try:
            os.remove("/tmp/test_comp_insights.json")
        except FileNotFoundError:
            pass
        from src.competitor_analysis import _load_insights
        data = _load_insights()
        assert len(data["competitors"]) >= 1
        assert data["insights"] == []

    @patch("src.competitor_analysis._INSIGHTS_PATH", "/tmp/test_comp_insights_rw.json")
    def test_save_and_load_roundtrip(self):
        from src.competitor_analysis import _load_insights, _save_insights
        data = {
            "competitors": ["Test Comp"],
            "insights": [{"id": "ci_1", "competitor": "Test Comp"}],
            "updated_at": "",
        }
        _save_insights(data)
        loaded = _load_insights()
        assert len(loaded["insights"]) == 1
        assert loaded["updated_at"] != ""


class TestGetCompetitors:
    """Test get_competitors function."""

    @patch("src.competitor_analysis._INSIGHTS_PATH", "/tmp/test_comp_get.json")
    def test_returns_default_competitors(self):
        import os
        try:
            os.remove("/tmp/test_comp_get.json")
        except FileNotFoundError:
            pass
        from src.competitor_analysis import get_competitors
        comps = get_competitors()
        assert len(comps) >= 1


class TestAddInsight:
    """Test add_insight function."""

    @patch("src.competitor_analysis._INSIGHTS_PATH", "/tmp/test_comp_add.json")
    def test_returns_entry_with_fields(self):
        from src.competitor_analysis import add_insight
        entry = add_insight("Competitor A", "Posted about AI trends", source="test")
        assert entry["id"].startswith("ci_")
        assert entry["competitor"] == "Competitor A"
        assert entry["summary"] == "Posted about AI trends"
        assert entry["source"] == "test"
        assert "timestamp" in entry

    @patch("src.competitor_analysis._INSIGHTS_PATH", "/tmp/test_comp_add2.json")
    def test_keeps_max_200_entries(self):
        from src.competitor_analysis import add_insight, _load_insights, _save_insights
        data = {
            "competitors": ["A"],
            "insights": [{"id": f"ci_{i}", "competitor": "A", "summary": f"test {i}", "timestamp": 0} for i in range(200)],
            "updated_at": "",
        }
        _save_insights(data)
        add_insight("A", "overflow entry")
        loaded = _load_insights()
        assert len(loaded["insights"]) == 200


class TestGetRecentInsights:
    """Test get_recent_insights function."""

    @patch("src.competitor_analysis._INSIGHTS_PATH", "/tmp/test_comp_recent.json")
    def test_returns_recent_only(self):
        from src.competitor_analysis import _save_insights, get_recent_insights
        now = time.time()
        data = {
            "competitors": ["A"],
            "insights": [
                {"id": "ci_1", "timestamp": now - 3600},
                {"id": "ci_2", "timestamp": now - 86400 * 10},
            ],
            "updated_at": "",
        }
        _save_insights(data)
        recent = get_recent_insights(days=7)
        assert len(recent) == 1
        assert recent[0]["id"] == "ci_1"


class TestFormatInsightsSummary:
    """Test format_insights_summary function."""

    def test_empty_insights(self):
        from src.competitor_analysis import format_insights_summary
        result = format_insights_summary([])
        assert "Нет данных" in result

    def test_with_insights(self):
        from src.competitor_analysis import format_insights_summary
        insights = [
            {"competitor": "Comp A", "summary": "Posted 3 articles about AI"},
            {"competitor": "Comp A", "summary": "Started new series"},
            {"competitor": "Comp B", "summary": "Launched new product"},
        ]
        result = format_insights_summary(insights)
        assert "3 наблюдений" in result
        assert "Comp A" in result
        assert "Comp B" in result
