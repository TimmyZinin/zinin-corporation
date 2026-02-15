"""Tests for AIVideoGenerator — Pollinations.ai video generation tool."""

import os
import pytest
from unittest.mock import patch, MagicMock, mock_open
from io import BytesIO


# ── Constants & Input Schema ─────────────────────────────────

class TestAIVideoGeneratorInput:
    """Test the Pydantic input schema."""

    def test_default_values(self):
        from src.tools.design_tools import AIVideoGeneratorInput
        inp = AIVideoGeneratorInput(prompt="A sunset scene")
        assert inp.model == "wan"
        assert inp.duration == 5

    def test_custom_values(self):
        from src.tools.design_tools import AIVideoGeneratorInput
        inp = AIVideoGeneratorInput(prompt="A car driving", model="seedance", duration=10)
        assert inp.model == "seedance"
        assert inp.duration == 10

    def test_prompt_required(self):
        from src.tools.design_tools import AIVideoGeneratorInput
        with pytest.raises(Exception):
            AIVideoGeneratorInput()


class TestVideoModels:
    """Test model list and timeout constants."""

    def test_video_models_list(self):
        from src.tools.design_tools import _VIDEO_MODELS
        assert "wan" in _VIDEO_MODELS
        assert "seedance" in _VIDEO_MODELS
        assert "grok-video" in _VIDEO_MODELS
        assert len(_VIDEO_MODELS) == 3

    def test_timeout_value(self):
        from src.tools.design_tools import _VIDEO_GEN_TIMEOUT
        assert _VIDEO_GEN_TIMEOUT == 180


# ── AIVideoGenerator._generate_video ─────────────────────────

class TestGenerateVideo:
    """Test _generate_video HTTP calls."""

    def test_successful_generation(self, tmp_path):
        from src.tools.design_tools import AIVideoGenerator
        tool = AIVideoGenerator()

        fake_video = b"\x00" * 10000  # >5000 bytes
        mock_resp = MagicMock()
        mock_resp.read.return_value = fake_video
        mock_resp.headers = {"Content-Type": "video/mp4"}
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("src.tools.design_tools.urlopen", return_value=mock_resp), \
             patch("src.tools.design_tools.DESIGN_VIDEO_DIR", tmp_path):
            result = tool._generate_video("A sunset", "wan", 5)

        assert result is not None
        assert "AI-видео создано:" in result
        assert ".mp4" in result

    def test_small_response_returns_none(self, tmp_path):
        """Responses < 5000 bytes are rejected as errors."""
        from src.tools.design_tools import AIVideoGenerator
        tool = AIVideoGenerator()

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"error page"  # tiny
        mock_resp.headers = {"Content-Type": "text/html"}
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("src.tools.design_tools.urlopen", return_value=mock_resp):
            result = tool._generate_video("test", "wan", 5)

        assert result is None

    def test_http_error_retries_then_returns_none(self):
        """Network errors should retry once then return None."""
        from src.tools.design_tools import AIVideoGenerator
        tool = AIVideoGenerator()

        with patch("src.tools.design_tools.urlopen", side_effect=Exception("Connection refused")), \
             patch("src.tools.design_tools.time.sleep"):
            result = tool._generate_video("test", "wan", 5)

        assert result is None

    def test_url_contains_model_and_duration(self):
        """Verify the constructed URL has correct query parameters."""
        from src.tools.design_tools import AIVideoGenerator
        tool = AIVideoGenerator()

        captured_url = None

        def mock_urlopen(req, timeout=None):
            nonlocal captured_url
            captured_url = req.full_url if hasattr(req, 'full_url') else str(req)
            raise Exception("stop here")

        with patch("src.tools.design_tools.urlopen", side_effect=mock_urlopen), \
             patch("src.tools.design_tools.time.sleep"):
            tool._generate_video("sunset beach", "seedance", 10)

        assert captured_url is not None
        assert "model=seedance" in captured_url
        assert "duration=10" in captured_url
        assert "gen.pollinations.ai" in captured_url

    def test_prompt_is_url_encoded(self):
        """Prompt with spaces/special chars should be URL-encoded."""
        from src.tools.design_tools import AIVideoGenerator
        tool = AIVideoGenerator()

        captured_url = None

        def mock_urlopen(req, timeout=None):
            nonlocal captured_url
            captured_url = req.full_url if hasattr(req, 'full_url') else str(req)
            raise Exception("stop here")

        with patch("src.tools.design_tools.urlopen", side_effect=mock_urlopen), \
             patch("src.tools.design_tools.time.sleep"):
            tool._generate_video("красный грузовик на дороге", "wan", 5)

        assert captured_url is not None
        # URL-encoded Russian text should not have spaces
        assert " " not in captured_url.split("?")[0]

    def test_saves_mp4_file(self, tmp_path):
        """Verify MP4 file is actually saved to disk."""
        from src.tools.design_tools import AIVideoGenerator
        tool = AIVideoGenerator()

        fake_video = b"\x00\x01\x02" * 3000  # 9000 bytes

        mock_resp = MagicMock()
        mock_resp.read.return_value = fake_video
        mock_resp.headers = {"Content-Type": "video/mp4"}
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("src.tools.design_tools.urlopen", return_value=mock_resp), \
             patch("src.tools.design_tools.DESIGN_VIDEO_DIR", tmp_path):
            result = tool._generate_video("test", "wan", 5)

        # Find the saved file
        mp4_files = list(tmp_path.glob("*.mp4"))
        assert len(mp4_files) == 1
        assert mp4_files[0].stat().st_size == 9000

    def test_filename_contains_model(self, tmp_path):
        """Saved filename should contain the model name."""
        from src.tools.design_tools import AIVideoGenerator
        tool = AIVideoGenerator()

        fake_video = b"\x00" * 10000

        mock_resp = MagicMock()
        mock_resp.read.return_value = fake_video
        mock_resp.headers = {"Content-Type": "video/mp4"}
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("src.tools.design_tools.urlopen", return_value=mock_resp), \
             patch("src.tools.design_tools.DESIGN_VIDEO_DIR", tmp_path):
            result = tool._generate_video("test", "seedance", 5)

        mp4_files = list(tmp_path.glob("*.mp4"))
        assert "seedance" in mp4_files[0].name


# ── AIVideoGenerator._run (cascade logic) ────────────────────

class TestAIVideoGeneratorRun:
    """Test the _run method with cascade fallback logic."""

    def test_first_model_success_no_fallback(self):
        """If first model works, no fallback is tried."""
        from src.tools.design_tools import AIVideoGenerator
        tool = AIVideoGenerator()

        with patch.object(tool, "_generate_video", return_value="AI-видео создано: /path/to/video.mp4"):
            result = tool._run(prompt="sunset", model="wan", duration=5)

        assert "AI-видео создано" in result

    def test_cascade_to_second_model(self):
        """If first model fails, try next in cascade."""
        from src.tools.design_tools import AIVideoGenerator
        tool = AIVideoGenerator()

        call_count = 0

        def mock_gen(prompt, model, duration):
            nonlocal call_count
            call_count += 1
            if model == "wan":
                return None  # fail
            return f"AI-видео создано: /path/{model}.mp4"

        with patch.object(tool, "_generate_video", side_effect=mock_gen):
            result = tool._run(prompt="sunset", model="wan", duration=5)

        assert "seedance" in result
        assert call_count == 2

    def test_cascade_to_third_model(self):
        """If first two models fail, try third."""
        from src.tools.design_tools import AIVideoGenerator
        tool = AIVideoGenerator()

        def mock_gen(prompt, model, duration):
            if model in ("wan", "seedance"):
                return None
            return f"AI-видео создано: /path/{model}.mp4"

        with patch.object(tool, "_generate_video", side_effect=mock_gen):
            result = tool._run(prompt="sunset", model="wan", duration=5)

        assert "grok-video" in result

    def test_all_models_fail_fallback_to_tts(self):
        """If all models fail, fall back to TTS audiogram."""
        from src.tools.design_tools import AIVideoGenerator
        tool = AIVideoGenerator()

        with patch.object(tool, "_generate_video", return_value=None), \
             patch("src.tools.design_tools.VideoCreator") as MockVC:
            mock_vc = MockVC.return_value
            mock_vc._create_tts_video.return_value = "Аудиограмма создана: /path/fallback.mp4"
            result = tool._run(prompt="sunset scene", model="wan", duration=5)

        assert "Аудиограмма" in result
        mock_vc._create_tts_video.assert_called_once()

    def test_error_result_triggers_cascade(self):
        """Results starting with 'ERROR' should trigger cascade."""
        from src.tools.design_tools import AIVideoGenerator
        tool = AIVideoGenerator()

        def mock_gen(prompt, model, duration):
            if model == "wan":
                return "ERROR: timeout"
            return f"AI-видео создано: /path/{model}.mp4"

        with patch.object(tool, "_generate_video", side_effect=mock_gen):
            result = tool._run(prompt="test", model="wan", duration=5)

        assert "seedance" in result

    def test_unknown_model_uses_all_cascade(self):
        """Unknown model should not be tried, all 3 default models tried."""
        from src.tools.design_tools import AIVideoGenerator
        tool = AIVideoGenerator()

        tried_models = []

        def mock_gen(prompt, model, duration):
            tried_models.append(model)
            return None

        with patch.object(tool, "_generate_video", side_effect=mock_gen), \
             patch("src.tools.design_tools.VideoCreator") as MockVC:
            mock_vc = MockVC.return_value
            mock_vc._create_tts_video.return_value = "fallback"
            tool._run(prompt="test", model="unknown_model", duration=5)

        assert tried_models == ["wan", "seedance", "grok-video"]

    def test_duration_clamped_min(self):
        """Duration below 2 should be clamped to 2."""
        from src.tools.design_tools import AIVideoGenerator
        tool = AIVideoGenerator()

        with patch.object(tool, "_generate_video", return_value="AI-видео создано: /path/v.mp4") as mock:
            tool._run(prompt="test", model="wan", duration=0)

        mock.assert_called_once_with("test", "wan", 2)

    def test_duration_clamped_max(self):
        """Duration above 15 should be clamped to 15."""
        from src.tools.design_tools import AIVideoGenerator
        tool = AIVideoGenerator()

        with patch.object(tool, "_generate_video", return_value="AI-видео создано: /path/v.mp4") as mock:
            tool._run(prompt="test", model="wan", duration=999)

        mock.assert_called_once_with("test", "wan", 15)

    def test_requested_model_tried_first(self):
        """If user specifies 'grok-video', it should be tried first."""
        from src.tools.design_tools import AIVideoGenerator
        tool = AIVideoGenerator()

        tried_models = []

        def mock_gen(prompt, model, duration):
            tried_models.append(model)
            if model == "grok-video":
                return f"AI-видео создано: /path/{model}.mp4"
            return None

        with patch.object(tool, "_generate_video", side_effect=mock_gen):
            result = tool._run(prompt="test", model="grok-video", duration=5)

        assert tried_models[0] == "grok-video"
        assert "grok-video" in result

    def test_tts_fallback_truncates_prompt(self):
        """Fallback to TTS should truncate prompt to 500 chars."""
        from src.tools.design_tools import AIVideoGenerator
        tool = AIVideoGenerator()

        long_prompt = "x" * 1000

        with patch.object(tool, "_generate_video", return_value=None), \
             patch("src.tools.design_tools.VideoCreator") as MockVC:
            mock_vc = MockVC.return_value
            mock_vc._create_tts_video.return_value = "fallback"
            tool._run(prompt=long_prompt, model="wan", duration=5)

        call_args = mock_vc._create_tts_video.call_args
        text_arg = call_args[1].get("text", call_args[0][0] if call_args[0] else "")
        assert len(text_arg) <= 500


# ── Tool metadata ────────────────────────────────────────────

class TestAIVideoGeneratorMeta:
    """Test tool class attributes."""

    def test_tool_name(self):
        from src.tools.design_tools import AIVideoGenerator
        tool = AIVideoGenerator()
        assert tool.name == "AI Video Generator"

    def test_tool_description_mentions_pollinations(self):
        from src.tools.design_tools import AIVideoGenerator
        tool = AIVideoGenerator()
        assert "Pollinations" in tool.description

    def test_tool_description_mentions_models(self):
        from src.tools.design_tools import AIVideoGenerator
        tool = AIVideoGenerator()
        assert "wan" in tool.description.lower()
        assert "seedance" in tool.description.lower()

    def test_args_schema_set(self):
        from src.tools.design_tools import AIVideoGenerator, AIVideoGeneratorInput
        tool = AIVideoGenerator()
        assert tool.args_schema is AIVideoGeneratorInput
