"""Tests for Threads publisher in Yuki bot (src/telegram_yuki/publishers.py)."""

import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class TestThreadsPublisherYuki:
    """Verify ThreadsPublisher in Yuki bot delegates to real ThreadsTimPublisher."""

    def test_threads_publisher_class_exists(self):
        from src.telegram_yuki.publishers import ThreadsPublisher
        pub = ThreadsPublisher()
        assert pub.name == "threads"
        assert pub.label == "Threads"
        assert pub.emoji == "🧵"

    def test_is_configured_needs_both_token_and_user_id(self, monkeypatch):
        from src.telegram_yuki.publishers import ThreadsPublisher
        monkeypatch.delenv("THREADS_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("THREADS_USER_ID", raising=False)
        pub = ThreadsPublisher()
        assert pub.is_configured is False

    def test_is_configured_token_only_not_enough(self, monkeypatch):
        from src.telegram_yuki.publishers import ThreadsPublisher
        monkeypatch.setenv("THREADS_ACCESS_TOKEN", "some-token")
        monkeypatch.delenv("THREADS_USER_ID", raising=False)
        pub = ThreadsPublisher()
        assert pub.is_configured is False

    def test_is_configured_both_set(self, monkeypatch):
        from src.telegram_yuki.publishers import ThreadsPublisher
        monkeypatch.setenv("THREADS_ACCESS_TOKEN", "some-token")
        monkeypatch.setenv("THREADS_USER_ID", "12345")
        pub = ThreadsPublisher()
        assert pub.is_configured is True

    @pytest.mark.asyncio
    async def test_publish_delegates_to_threads_tim_publisher(self, monkeypatch):
        from src.telegram_yuki.publishers import ThreadsPublisher

        mock_run = MagicMock(return_value="✅ Published to Threads!\nPost ID: 123")
        with patch("src.tools.smm_tools.ThreadsTimPublisher._run", mock_run):
            pub = ThreadsPublisher()
            result = await pub.publish("Test post text")
            mock_run.assert_called_once_with(action="publish_text", text="Test post text")
            assert "Published" in result or "Threads" in result

    @pytest.mark.asyncio
    async def test_check_status_delegates_to_check_token(self, monkeypatch):
        from src.telegram_yuki.publishers import ThreadsPublisher

        mock_run = MagicMock(return_value="✅ Threads token valid. User: Tim")
        with patch("src.tools.smm_tools.ThreadsTimPublisher._run", mock_run):
            pub = ThreadsPublisher()
            result = await pub.check_status()
            mock_run.assert_called_once_with(action="check_token")
            assert "Threads" in result

    @pytest.mark.asyncio
    async def test_publish_with_image_falls_back_to_text(self, monkeypatch, tmp_path):
        """Image paths can't be used directly with Threads API (needs URL)."""
        from src.telegram_yuki.publishers import ThreadsPublisher

        fake_img = tmp_path / "test.png"
        fake_img.write_text("fake")

        mock_run = MagicMock(return_value="✅ Published text")
        with patch("src.tools.smm_tools.ThreadsTimPublisher._run", mock_run):
            pub = ThreadsPublisher()
            result = await pub.publish("Post with image", image_path=str(fake_img))
            mock_run.assert_called_once_with(action="publish_text", text="Post with image")

    def test_publisher_registry_includes_threads(self):
        from src.telegram_yuki.publishers import get_publisher, _PUBLISHERS
        _PUBLISHERS.clear()  # force re-init
        pub = get_publisher("threads")
        assert pub is not None
        assert pub.name == "threads"

    def test_get_all_publishers_has_threads(self):
        from src.telegram_yuki.publishers import get_all_publishers, _PUBLISHERS
        _PUBLISHERS.clear()
        all_pubs = get_all_publishers()
        assert "threads" in all_pubs

    def test_get_configured_threads_when_env_set(self, monkeypatch):
        from src.telegram_yuki.publishers import get_configured_publishers, _PUBLISHERS
        _PUBLISHERS.clear()
        monkeypatch.setenv("THREADS_ACCESS_TOKEN", "tok")
        monkeypatch.setenv("THREADS_USER_ID", "uid")
        monkeypatch.setenv("LINKEDIN_ACCESS_TOKEN", "lin")
        configured = get_configured_publishers()
        assert "threads" in configured

    def test_get_configured_threads_when_env_missing(self, monkeypatch):
        from src.telegram_yuki.publishers import get_configured_publishers, _PUBLISHERS
        _PUBLISHERS.clear()
        monkeypatch.delenv("THREADS_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("THREADS_USER_ID", raising=False)
        monkeypatch.delenv("LINKEDIN_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_YUKI_CHANNEL_ID", raising=False)
        configured = get_configured_publishers()
        assert "threads" not in configured
