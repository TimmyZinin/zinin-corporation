"""Tests for comment digest module."""

import time
import pytest
from unittest.mock import patch, MagicMock


class TestCommentDigestLoadSave:
    """Test JSON load/save persistence."""

    @patch("src.comment_digest._DIGEST_PATH", "/tmp/test_comment_digest.json")
    def test_load_returns_empty_when_no_file(self):
        import os
        try:
            os.remove("/tmp/test_comment_digest.json")
        except FileNotFoundError:
            pass
        from src.comment_digest import _load_digest
        data = _load_digest()
        assert data["digests"] == []
        assert data["updated_at"] == ""

    @patch("src.comment_digest._DIGEST_PATH", "/tmp/test_comment_digest_rw.json")
    def test_save_and_load_roundtrip(self):
        from src.comment_digest import _load_digest, _save_digest
        data = {"digests": [{"id": "cd_1", "summary": "test"}], "updated_at": ""}
        _save_digest(data)
        loaded = _load_digest()
        assert len(loaded["digests"]) == 1
        assert loaded["digests"][0]["id"] == "cd_1"
        assert loaded["updated_at"] != ""


class TestAddDigestEntry:
    """Test add_digest_entry function."""

    @patch("src.comment_digest._DIGEST_PATH", "/tmp/test_cd_add.json")
    def test_returns_entry_with_fields(self):
        from src.comment_digest import add_digest_entry
        entry = add_digest_entry("5 new comments on AI post", 5, source="test")
        assert entry["id"].startswith("cd_")
        assert entry["summary"] == "5 new comments on AI post"
        assert entry["comment_count"] == 5
        assert entry["source"] == "test"

    @patch("src.comment_digest._DIGEST_PATH", "/tmp/test_cd_add2.json")
    def test_keeps_max_50_entries(self):
        from src.comment_digest import add_digest_entry, _load_digest, _save_digest
        data = {"digests": [{"id": f"cd_{i}", "summary": f"test {i}"} for i in range(50)], "updated_at": ""}
        _save_digest(data)
        add_digest_entry("overflow entry", 1)
        loaded = _load_digest()
        assert len(loaded["digests"]) == 50


class TestGetCommentCount:
    """Test get_comment_count function."""

    @patch("src.comment_digest._DIGEST_PATH", "/tmp/test_cd_count.json")
    def test_counts_recent_comments(self):
        from src.comment_digest import _save_digest, get_comment_count
        data = {
            "digests": [
                {"id": "cd_1", "comment_count": 3, "timestamp": time.time() - 3600},
                {"id": "cd_2", "comment_count": 7, "timestamp": time.time() - 7200},
                {"id": "cd_3", "comment_count": 10, "timestamp": time.time() - 86400},
            ],
            "updated_at": "",
        }
        _save_digest(data)
        count = get_comment_count(hours=3)
        assert count == 10  # cd_1 + cd_2

    @patch("src.comment_digest._DIGEST_PATH", "/tmp/test_cd_count2.json")
    def test_returns_zero_when_no_recent(self):
        from src.comment_digest import _save_digest, get_comment_count
        data = {
            "digests": [
                {"id": "cd_1", "comment_count": 5, "timestamp": time.time() - 86400},
            ],
            "updated_at": "",
        }
        _save_digest(data)
        count = get_comment_count(hours=1)
        assert count == 0


class TestGetRecentDigests:
    """Test get_recent_digests function."""

    @patch("src.comment_digest._DIGEST_PATH", "/tmp/test_cd_recent.json")
    def test_returns_recent_only(self):
        from src.comment_digest import _save_digest, get_recent_digests
        now = time.time()
        data = {
            "digests": [
                {"id": "cd_1", "timestamp": now - 3600},
                {"id": "cd_2", "timestamp": now - 86400 * 2},
            ],
            "updated_at": "",
        }
        _save_digest(data)
        recent = get_recent_digests(hours=24)
        assert len(recent) == 1
        assert recent[0]["id"] == "cd_1"


class TestFormatCommentDigest:
    """Test format_comment_digest function."""

    def test_empty_digests(self):
        from src.comment_digest import format_comment_digest
        result = format_comment_digest([])
        assert "Нет новых" in result

    def test_with_digests(self):
        from src.comment_digest import format_comment_digest
        digests = [
            {"summary": "AI post got 5 comments", "comment_count": 5},
            {"summary": "Career post got 3 comments", "comment_count": 3},
        ]
        result = format_comment_digest(digests)
        assert "8" in result  # total
        assert "AI post" in result
