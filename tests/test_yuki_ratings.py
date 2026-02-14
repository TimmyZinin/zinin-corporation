"""Tests for RatingStore — post ratings storage and aggregation."""

import json
import os
import tempfile
import pytest

from src.telegram_yuki.ratings import RatingStore, _RATINGS_PATH, _DATA_DIR


@pytest.fixture(autouse=True)
def _clean_ratings(monkeypatch, tmp_path):
    """Use temp file for ratings during tests."""
    tmp_file = str(tmp_path / "ratings.json")
    import src.telegram_yuki.ratings as mod
    monkeypatch.setattr(mod, "_RATINGS_PATH", tmp_file)
    yield


class TestRatingStore:

    def test_record_rating_creates_entry(self):
        entry = RatingStore.record_rating(
            post_id="abc123",
            author="kristina",
            brand="sborka",
            platform="linkedin",
            topic="Test topic",
            text_score=4,
            image_score=3,
            overall_score=5,
        )
        assert entry["post_id"] == "abc123"
        assert entry["author"] == "kristina"
        assert entry["text_score"] == 4
        assert entry["image_score"] == 3
        assert entry["overall_score"] == 5
        assert "timestamp" in entry

    def test_record_rating_truncates_long_fields(self):
        entry = RatingStore.record_rating(
            post_id="x",
            author="tim",
            topic="A" * 500,
            image_feedback="B" * 1000,
        )
        assert len(entry["topic"]) == 200
        assert len(entry["image_feedback"]) == 500

    def test_get_author_stats_empty(self):
        stats = RatingStore.get_author_stats("nonexistent")
        assert stats["count"] == 0
        assert stats["avg_text"] == 0.0
        assert stats["avg_image"] == 0.0
        assert stats["avg_overall"] == 0.0
        assert stats["common_image_feedback"] == []

    def test_get_author_stats_calculated(self):
        for i in range(5):
            RatingStore.record_rating(
                post_id=f"p{i}",
                author="tim",
                text_score=3 + (i % 2),
                image_score=4,
                overall_score=4,
            )
        stats = RatingStore.get_author_stats("tim")
        assert stats["count"] == 5
        assert stats["avg_text"] > 0
        assert stats["avg_image"] == 4.0
        assert stats["avg_overall"] == 4.0

    def test_get_recent_issues_empty(self):
        issues = RatingStore.get_recent_issues()
        assert issues == []

    def test_get_recent_issues_with_feedback(self):
        RatingStore.record_rating(post_id="a", author="tim", image_feedback="Too dark")
        RatingStore.record_rating(post_id="b", author="tim", image_feedback="")
        RatingStore.record_rating(post_id="c", author="tim", image_feedback="Needs more contrast")

        issues = RatingStore.get_recent_issues()
        assert len(issues) == 2
        assert "Needs more contrast" in issues
        assert "Too dark" in issues

    def test_get_recent_issues_filtered_by_author(self):
        RatingStore.record_rating(post_id="a", author="tim", image_feedback="Issue A")
        RatingStore.record_rating(post_id="b", author="kristina", image_feedback="Issue B")

        tim_issues = RatingStore.get_recent_issues(author="tim")
        assert len(tim_issues) == 1
        assert "Issue A" in tim_issues

    def test_aggregation_updates_on_record(self):
        RatingStore.record_rating(post_id="x", author="kristina", text_score=5, overall_score=4)
        RatingStore.record_rating(post_id="y", author="kristina", text_score=3, overall_score=2)

        stats = RatingStore.get_author_stats("kristina")
        assert stats["count"] == 2
        assert stats["avg_text"] == 4.0  # (5+3)/2
        assert stats["avg_overall"] == 3.0  # (4+2)/2

    def test_format_stats_empty(self):
        result = RatingStore.format_stats()
        assert "пока нет данных" in result

    def test_format_stats_with_data(self):
        RatingStore.record_rating(post_id="a", author="kristina", text_score=4, overall_score=5)
        result = RatingStore.format_stats()
        assert "Кристина" in result
        assert "1 постов" in result

    def test_format_stats_shows_tim(self):
        RatingStore.record_rating(post_id="a", author="tim", text_score=3, overall_score=3)
        result = RatingStore.format_stats()
        assert "Тим" in result

    def test_max_ratings_limit(self):
        """Ensure ratings are capped at 500."""
        for i in range(510):
            RatingStore.record_rating(post_id=f"p{i}", author="tim", text_score=3)

        # Verify: we only keep 500
        from src.telegram_yuki.ratings import _load
        data = _load()
        assert len(data["ratings"]) <= 500

    def test_common_image_feedback_deduplication(self):
        RatingStore.record_rating(post_id="a", author="tim", image_feedback="too dark")
        RatingStore.record_rating(post_id="b", author="tim", image_feedback="Too Dark")
        RatingStore.record_rating(post_id="c", author="tim", image_feedback="needs color")

        stats = RatingStore.get_author_stats("tim")
        feedbacks = stats["common_image_feedback"]
        # "too dark" and "Too Dark" should be deduplicated (case-insensitive)
        assert len(feedbacks) == 2
