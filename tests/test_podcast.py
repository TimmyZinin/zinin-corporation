"""Tests for podcast generation pipeline."""

import json
import os
import re
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ──────────────────────────────────────────────────────────
# Test: podcast_gen — text chunking
# ──────────────────────────────────────────────────────────

class TestSplitTextChunks:
    def test_short_text_single_chunk(self):
        from src.telegram_yuki.podcast_gen import _split_text_chunks
        result = _split_text_chunks("Короткий текст.", max_chars=100)
        assert result == ["Короткий текст."]

    def test_empty_text(self):
        from src.telegram_yuki.podcast_gen import _split_text_chunks
        result = _split_text_chunks("")
        assert result == []

    def test_whitespace_only(self):
        from src.telegram_yuki.podcast_gen import _split_text_chunks
        result = _split_text_chunks("   ")
        assert result == []

    def test_splits_at_sentence_boundaries(self):
        from src.telegram_yuki.podcast_gen import _split_text_chunks
        text = "Первое предложение. Второе предложение. Третье предложение."
        result = _split_text_chunks(text, max_chars=50)
        assert len(result) >= 2
        for chunk in result:
            assert len(chunk) <= 50

    def test_respects_max_chars(self):
        from src.telegram_yuki.podcast_gen import _split_text_chunks
        text = ". ".join([f"Предложение номер {i}" for i in range(100)])
        result = _split_text_chunks(text, max_chars=200)
        for chunk in result:
            assert len(chunk) <= 200

    def test_long_sentence_split_at_commas(self):
        from src.telegram_yuki.podcast_gen import _split_text_chunks
        text = ", ".join([f"часть {i}" for i in range(50)])
        result = _split_text_chunks(text, max_chars=100)
        for chunk in result:
            assert len(chunk) <= 100

    def test_hard_split_no_boundaries(self):
        from src.telegram_yuki.podcast_gen import _split_text_chunks
        text = "слово " * 1000  # ~6000 chars with no sentence/comma boundaries
        result = _split_text_chunks(text, max_chars=100)
        assert len(result) > 1
        for chunk in result:
            assert len(chunk) <= 100

    def test_realistic_podcast_text(self):
        from src.telegram_yuki.podcast_gen import _split_text_chunks, MAX_CHUNK_CHARS
        text = ". ".join(
            [f"Предложение номер {i} с достаточно длинным текстом" for i in range(200)]
        )
        result = _split_text_chunks(text)
        for chunk in result:
            assert len(chunk) <= MAX_CHUNK_CHARS

    def test_preserves_all_content(self):
        from src.telegram_yuki.podcast_gen import _split_text_chunks
        text = "Один. Два. Три. Четыре. Пять."
        result = _split_text_chunks(text, max_chars=20)
        joined = " ".join(result)
        assert "Один." in joined
        assert "Пять." in joined


# ──────────────────────────────────────────────────────────
# Test: podcast_gen — clean_script
# ──────────────────────────────────────────────────────────

class TestCleanScript:
    def test_removes_crewai_headers(self):
        from src.telegram_yuki.podcast_gen import _clean_script
        text = (
            "POST GENERATED (score: 0.85)\n"
            "Author: Юки\n"
            "Topic: AI\n"
            "---\n"
            "Привет! Текст подкаста."
        )
        result = _clean_script(text)
        assert result == "Привет! Текст подкаста."

    def test_clean_text_without_headers(self):
        from src.telegram_yuki.podcast_gen import _clean_script
        text = "Просто текст подкаста без заголовков."
        result = _clean_script(text)
        assert result == "Просто текст подкаста без заголовков."

    def test_empty_string(self):
        from src.telegram_yuki.podcast_gen import _clean_script
        result = _clean_script("")
        assert result == ""

    def test_only_headers_returns_original(self):
        from src.telegram_yuki.podcast_gen import _clean_script
        text = "POST GENERATED\nAuthor: Юки"
        result = _clean_script(text)
        # Falls through skip_header=False, includes "Author: Юки"
        assert len(result) > 0

    def test_score_line(self):
        from src.telegram_yuki.podcast_gen import _clean_script
        text = "Score: 0.9\n---\nТекст"
        result = _clean_script(text)
        assert result == "Текст"

    def test_length_line(self):
        from src.telegram_yuki.podcast_gen import _clean_script
        text = "Length: 5000\n---\nТекст"
        result = _clean_script(text)
        assert result == "Текст"


# ──────────────────────────────────────────────────────────
# Test: podcast_gen — generate_podcast_audio
# ──────────────────────────────────────────────────────────

class TestGeneratePodcastAudio:
    def test_missing_api_key(self):
        from src.telegram_yuki.podcast_gen import generate_podcast_audio
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RuntimeError, match="ELEVENLABS_API_KEY not set"):
                generate_podcast_audio("script", "title")

    def test_missing_voice_id(self):
        from src.telegram_yuki.podcast_gen import generate_podcast_audio
        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key"}, clear=True):
            with pytest.raises(RuntimeError, match="ELEVENLABS_VOICE_ID not set"):
                generate_podcast_audio("script", "title")

    def test_empty_script(self):
        from src.telegram_yuki.podcast_gen import generate_podcast_audio
        with patch.dict(os.environ, {
            "ELEVENLABS_API_KEY": "key",
            "ELEVENLABS_VOICE_ID": "voice",
        }):
            with pytest.raises(RuntimeError, match="Empty script"):
                generate_podcast_audio("", "title")

    def test_empty_after_cleaning(self):
        from src.telegram_yuki.podcast_gen import generate_podcast_audio
        with patch.dict(os.environ, {
            "ELEVENLABS_API_KEY": "key",
            "ELEVENLABS_VOICE_ID": "voice",
        }):
            with pytest.raises(RuntimeError, match="Empty script"):
                generate_podcast_audio("   \n\n  ", "title")


# ──────────────────────────────────────────────────────────
# Test: podcast_gen — hard_split_words
# ──────────────────────────────────────────────────────────

class TestHardSplitWords:
    def test_basic_split(self):
        from src.telegram_yuki.podcast_gen import _hard_split_words
        text = "one two three four five"
        result = _hard_split_words(text, max_chars=10)
        for chunk in result:
            assert len(chunk) <= 10

    def test_single_word(self):
        from src.telegram_yuki.podcast_gen import _hard_split_words
        result = _hard_split_words("hello", max_chars=100)
        assert result == ["hello"]

    def test_empty(self):
        from src.telegram_yuki.podcast_gen import _hard_split_words
        result = _hard_split_words("", max_chars=100)
        assert result == []


# ──────────────────────────────────────────────────────────
# Test: rss_feed — PodcastRSSManager
# ──────────────────────────────────────────────────────────

class TestPodcastRSSManager:
    @pytest.fixture
    def rss_tmpdir(self, tmp_path):
        """Patch RSS module paths to use temp directory."""
        import src.telegram_yuki.rss_feed as rss_mod
        orig_pods = rss_mod.PODCASTS_DIR
        orig_eps = rss_mod.EPISODES_FILE
        orig_feed = rss_mod.FEED_FILE

        rss_mod.PODCASTS_DIR = str(tmp_path)
        rss_mod.EPISODES_FILE = str(tmp_path / "episodes.json")
        rss_mod.FEED_FILE = str(tmp_path / "feed.xml")

        yield tmp_path

        rss_mod.PODCASTS_DIR = orig_pods
        rss_mod.EPISODES_FILE = orig_eps
        rss_mod.FEED_FILE = orig_feed

    def test_init_empty(self, rss_tmpdir):
        from src.telegram_yuki.rss_feed import PodcastRSSManager
        mgr = PodcastRSSManager("https://example.com")
        assert mgr.get_episode_count() == 0

    def test_add_episode(self, rss_tmpdir):
        from src.telegram_yuki.rss_feed import PodcastRSSManager
        mgr = PodcastRSSManager("https://example.com")
        ep = mgr.add_episode(
            title="Тест", description="Описание",
            audio_filename="test.mp3", duration_sec=300,
        )
        assert ep["episode_number"] == 1
        assert mgr.get_episode_count() == 1

    def test_auto_increment_episode_number(self, rss_tmpdir):
        from src.telegram_yuki.rss_feed import PodcastRSSManager
        mgr = PodcastRSSManager("https://example.com")
        mgr.add_episode("Ep1", "D", "ep1.mp3", 300)
        ep2 = mgr.add_episode("Ep2", "D", "ep2.mp3", 400)
        assert ep2["episode_number"] == 2

    def test_feed_xml_generated(self, rss_tmpdir):
        from src.telegram_yuki.rss_feed import PodcastRSSManager
        mgr = PodcastRSSManager("https://example.com")
        mgr.add_episode("Ep1", "D", "ep1.mp3", 300)
        feed_path = mgr.get_feed_path()
        assert os.path.exists(feed_path)

    def test_feed_xml_valid_structure(self, rss_tmpdir):
        import xml.etree.ElementTree as ET
        from src.telegram_yuki.rss_feed import PodcastRSSManager
        mgr = PodcastRSSManager("https://example.com")
        mgr.add_episode("Ep1", "D", "ep1.mp3", 300)

        tree = ET.parse(mgr.get_feed_path())
        root = tree.getroot()
        channel = root.find("channel")
        assert channel is not None
        assert channel.find("title").text == "AI Corporation Podcast"
        items = channel.findall("item")
        assert len(items) == 1

    def test_feed_has_enclosure(self, rss_tmpdir):
        import xml.etree.ElementTree as ET
        from src.telegram_yuki.rss_feed import PodcastRSSManager
        mgr = PodcastRSSManager("https://example.com")
        mgr.add_episode("Ep1", "D", "ep1.mp3", 300)

        tree = ET.parse(mgr.get_feed_path())
        items = tree.getroot().find("channel").findall("item")
        enc = items[0].find("enclosure")
        assert enc is not None
        assert "ep1.mp3" in enc.get("url")

    def test_feed_without_base_url(self, rss_tmpdir):
        from src.telegram_yuki.rss_feed import PodcastRSSManager
        mgr = PodcastRSSManager()  # No base_url
        mgr.add_episode("Ep1", "D", "ep1.mp3", 300)
        assert os.path.exists(mgr.get_feed_path())

    def test_episodes_json_persists(self, rss_tmpdir):
        from src.telegram_yuki.rss_feed import PodcastRSSManager
        import src.telegram_yuki.rss_feed as rss_mod

        mgr = PodcastRSSManager("https://example.com")
        mgr.add_episode("Ep1", "D", "ep1.mp3", 300)

        with open(rss_mod.EPISODES_FILE, "r") as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["title"] == "Ep1"

    def test_get_episodes(self, rss_tmpdir):
        from src.telegram_yuki.rss_feed import PodcastRSSManager
        mgr = PodcastRSSManager("https://example.com")
        mgr.add_episode("Ep1", "D", "ep1.mp3", 300)
        mgr.add_episode("Ep2", "D", "ep2.mp3", 400)
        eps = mgr.get_episodes()
        assert len(eps) == 2

    def test_feed_itunes_metadata(self, rss_tmpdir):
        from src.telegram_yuki.rss_feed import PodcastRSSManager
        mgr = PodcastRSSManager("https://example.com")
        mgr.add_episode("Ep1", "D", "ep1.mp3", 300)

        with open(mgr.get_feed_path(), "r") as f:
            content = f.read()
        assert "itunes:author" in content
        assert "itunes:category" in content
        assert "itunes:explicit" in content

    def test_multiple_episodes_in_feed(self, rss_tmpdir):
        import xml.etree.ElementTree as ET
        from src.telegram_yuki.rss_feed import PodcastRSSManager
        mgr = PodcastRSSManager("https://example.com")
        mgr.add_episode("First", "D", "ep1.mp3", 300)
        mgr.add_episode("Second", "D", "ep2.mp3", 400)

        tree = ET.parse(mgr.get_feed_path())
        items = tree.getroot().find("channel").findall("item")
        assert len(items) == 2
        titles = {item.find("title").text for item in items}
        assert "First" in titles
        assert "Second" in titles


# ──────────────────────────────────────────────────────────
# Test: PodcastScriptGenerator tool
# ──────────────────────────────────────────────────────────

class TestPodcastScriptGenerator:
    def test_import_and_create(self):
        from src.tools.smm_tools import PodcastScriptGenerator
        tool = PodcastScriptGenerator()
        assert tool.name == "Podcast Script Generator"

    def test_schema_fields(self):
        from src.tools.smm_tools import PodcastScriptInput
        fields = PodcastScriptInput.model_fields
        assert "topic" in fields
        assert "duration_minutes" in fields
        assert fields["duration_minutes"].default == 10

    def test_run_without_llm_keys(self):
        from src.tools.smm_tools import PodcastScriptGenerator
        tool = PodcastScriptGenerator()
        with patch.dict(os.environ, {}, clear=True):
            result = tool._run(topic="тест", duration_minutes=5)
            assert "Error" in result or "PODCAST SCRIPT" in result

    @patch("src.tools.smm_tools._call_llm")
    def test_run_with_mock_llm(self, mock_llm):
        from src.tools.smm_tools import PodcastScriptGenerator
        mock_llm.return_value = "Привет! Это тестовый подкаст. Конец."
        tool = PodcastScriptGenerator()
        result = tool._run(topic="тест", duration_minutes=5)
        assert "PODCAST SCRIPT GENERATED" in result
        assert "тест" in result
        assert "chars" in result
        mock_llm.assert_called_once()

    @patch("src.tools.smm_tools._call_llm")
    def test_target_chars_in_prompt(self, mock_llm):
        from src.tools.smm_tools import PodcastScriptGenerator
        mock_llm.return_value = "Текст"
        tool = PodcastScriptGenerator()
        tool._run(topic="AI", duration_minutes=10)
        # _call_llm(user_prompt, system=system_prompt, max_tokens=4000)
        call_args = mock_llm.call_args
        system_prompt = call_args.kwargs.get("system", "")
        # 10 min * 900 = 9000
        assert "9000" in system_prompt

    @patch("src.tools.smm_tools._call_llm")
    def test_llm_failure_returns_error(self, mock_llm):
        from src.tools.smm_tools import PodcastScriptGenerator
        mock_llm.return_value = None
        tool = PodcastScriptGenerator()
        result = tool._run(topic="тест")
        assert "Error" in result


# ──────────────────────────────────────────────────────────
# Test: agent/crew/bridge wiring
# ──────────────────────────────────────────────────────────

class TestPodcastWiring:
    def test_agent_has_podcast_tool(self):
        from src.tools.smm_tools import (
            ContentGenerator, YukiMemory, LinkedInPublisherTool, PodcastScriptGenerator,
        )
        tools = [ContentGenerator(), YukiMemory(), LinkedInPublisherTool(), PodcastScriptGenerator()]
        names = [t.name for t in tools]
        assert "Podcast Script Generator" in names

    def test_crew_has_generate_podcast(self):
        from src.crew import AICorporation
        assert hasattr(AICorporation, "generate_podcast")
        import inspect
        params = list(inspect.signature(AICorporation.generate_podcast).parameters.keys())
        assert "topic" in params
        assert "duration_minutes" in params

    def test_bridge_has_run_generate_podcast(self):
        from src.telegram.bridge import AgentBridge
        import inspect
        assert hasattr(AgentBridge, "run_generate_podcast")
        assert inspect.iscoroutinefunction(AgentBridge.run_generate_podcast)


# ──────────────────────────────────────────────────────────
# Test: Telegram handlers
# ──────────────────────────────────────────────────────────

class TestPodcastTriggers:
    def test_trigger_match(self):
        from src.telegram_yuki.handlers.messages import PODCAST_TRIGGERS
        assert PODCAST_TRIGGERS.search("сделай подкаст про AI")
        assert PODCAST_TRIGGERS.search("создай выпуск о бизнесе")
        assert PODCAST_TRIGGERS.search("запиши подкаст")
        assert PODCAST_TRIGGERS.search("генерируй эпизод")
        assert PODCAST_TRIGGERS.search("подготовь подкаст на тему")

    def test_trigger_no_match(self):
        from src.telegram_yuki.handlers.messages import PODCAST_TRIGGERS
        assert not PODCAST_TRIGGERS.search("напиши пост про AI")
        assert not PODCAST_TRIGGERS.search("подкаст")
        assert not PODCAST_TRIGGERS.search("сделай пост")
        assert not PODCAST_TRIGGERS.search("привет")

    def test_trigger_topic_extraction(self):
        from src.telegram_yuki.handlers.messages import PODCAST_TRIGGERS
        text = "сделай подкаст про AI-агентов"
        topic = PODCAST_TRIGGERS.sub("", text).strip()
        assert topic == "про AI-агентов"


class TestPodcastCommandHandler:
    def test_cmd_podcast_importable(self):
        from src.telegram_yuki.handlers.commands import cmd_podcast
        assert cmd_podcast is not None

    def test_generate_podcast_flow_importable(self):
        from src.telegram_yuki.handlers.commands import _generate_podcast_flow
        assert _generate_podcast_flow is not None

    def test_help_mentions_podcast(self):
        """Help text should mention /подкаст command."""
        import inspect
        from src.telegram_yuki.handlers.commands import cmd_help
        src = inspect.getsource(cmd_help)
        assert "подкаст" in src.lower()

    def test_health_mentions_elevenlabs(self):
        """Health check should mention ElevenLabs."""
        import inspect
        from src.telegram_yuki.handlers.commands import cmd_health
        src = inspect.getsource(cmd_health)
        assert "ELEVENLABS" in src

    def test_status_mentions_podcasts(self):
        """Status should show podcast count."""
        import inspect
        from src.telegram_yuki.handlers.commands import cmd_status
        src = inspect.getsource(cmd_status)
        assert "podcast" in src.lower() or "подкаст" in src.lower()
