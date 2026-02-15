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


# ── API Key Requirement ──────────────────────────────────────

class TestAPIKeyRequirement:
    """Test POLLINATIONS_API_KEY requirement."""

    def test_no_api_key_returns_error(self):
        """Without API key, _run should return error immediately."""
        from src.tools.design_tools import AIVideoGenerator
        tool = AIVideoGenerator()

        with patch.dict(os.environ, {}, clear=True):
            result = tool._run(prompt="sunset", model="wan", duration=5)

        assert "ERROR" in result
        assert "POLLINATIONS_API_KEY" in result

    def test_empty_api_key_returns_error(self):
        """Empty API key string should also return error."""
        from src.tools.design_tools import AIVideoGenerator
        tool = AIVideoGenerator()

        with patch.dict(os.environ, {"POLLINATIONS_API_KEY": ""}):
            result = tool._run(prompt="sunset", model="wan", duration=5)

        assert "ERROR" in result
        assert "POLLINATIONS_API_KEY" in result

    def test_with_api_key_proceeds_to_generate(self):
        """With API key, _run should attempt generation."""
        from src.tools.design_tools import AIVideoGenerator
        tool = AIVideoGenerator()

        with patch.dict(os.environ, {"POLLINATIONS_API_KEY": "sk_test123"}), \
             patch.object(tool, "_generate_video", return_value="AI-видео создано: /path/v.mp4"):
            result = tool._run(prompt="sunset", model="wan", duration=5)

        assert "AI-видео создано" in result


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
            result = tool._generate_video("A sunset", "wan", 5, "sk_test123")

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
            result = tool._generate_video("test", "wan", 5, "sk_test123")

        assert result is None

    def test_http_error_retries_then_returns_none(self):
        """Network errors should retry once then return None."""
        from src.tools.design_tools import AIVideoGenerator
        tool = AIVideoGenerator()

        with patch("src.tools.design_tools.urlopen", side_effect=Exception("Connection refused")), \
             patch("src.tools.design_tools.time.sleep"):
            result = tool._generate_video("test", "wan", 5, "sk_test123")

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
            tool._generate_video("sunset beach", "seedance", 10, "sk_test123")

        assert captured_url is not None
        assert "model=seedance" in captured_url
        assert "duration=10" in captured_url
        assert "gen.pollinations.ai" in captured_url

    def test_auth_header_sent(self):
        """Verify Authorization: Bearer header is sent."""
        from src.tools.design_tools import AIVideoGenerator
        tool = AIVideoGenerator()

        captured_headers = {}

        def mock_urlopen(req, timeout=None):
            if hasattr(req, 'headers'):
                captured_headers.update(req.headers)
            raise Exception("stop here")

        with patch("src.tools.design_tools.urlopen", side_effect=mock_urlopen), \
             patch("src.tools.design_tools.time.sleep"):
            tool._generate_video("test", "wan", 5, "sk_mykey")

        assert "Authorization" in captured_headers
        assert captured_headers["Authorization"] == "Bearer sk_mykey"

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
            tool._generate_video("красный грузовик на дороге", "wan", 5, "sk_test")

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
            result = tool._generate_video("test", "wan", 5, "sk_test")

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
            result = tool._generate_video("test", "seedance", 5, "sk_test")

        mp4_files = list(tmp_path.glob("*.mp4"))
        assert "seedance" in mp4_files[0].name


# ── AIVideoGenerator._run (cascade logic) ────────────────────

class TestAIVideoGeneratorRun:
    """Test the _run method with cascade fallback logic."""

    def _mock_env(self):
        return patch.dict(os.environ, {"POLLINATIONS_API_KEY": "sk_test123"})

    def test_first_model_success_no_fallback(self):
        """If first model works, no fallback is tried."""
        from src.tools.design_tools import AIVideoGenerator
        tool = AIVideoGenerator()

        with self._mock_env(), \
             patch.object(tool, "_generate_video", return_value="AI-видео создано: /path/to/video.mp4"):
            result = tool._run(prompt="sunset", model="wan", duration=5)

        assert "AI-видео создано" in result

    def test_cascade_to_second_model(self):
        """If first model fails, try next in cascade."""
        from src.tools.design_tools import AIVideoGenerator
        tool = AIVideoGenerator()

        call_count = 0

        def mock_gen(prompt, model, duration, api_key):
            nonlocal call_count
            call_count += 1
            if model == "wan":
                return None  # fail
            return f"AI-видео создано: /path/{model}.mp4"

        with self._mock_env(), \
             patch.object(tool, "_generate_video", side_effect=mock_gen):
            result = tool._run(prompt="sunset", model="wan", duration=5)

        assert "seedance" in result
        assert call_count == 2

    def test_cascade_to_third_model(self):
        """If first two models fail, try third."""
        from src.tools.design_tools import AIVideoGenerator
        tool = AIVideoGenerator()

        def mock_gen(prompt, model, duration, api_key):
            if model in ("wan", "seedance"):
                return None
            return f"AI-видео создано: /path/{model}.mp4"

        with self._mock_env(), \
             patch.object(tool, "_generate_video", side_effect=mock_gen):
            result = tool._run(prompt="sunset", model="wan", duration=5)

        assert "grok-video" in result

    def test_all_models_fail_returns_error(self):
        """If all models fail, return error message (no TTS fallback)."""
        from src.tools.design_tools import AIVideoGenerator
        tool = AIVideoGenerator()

        with self._mock_env(), \
             patch.object(tool, "_generate_video", return_value=None):
            result = tool._run(prompt="sunset", model="wan", duration=5)

        assert "ERROR" in result
        assert "недоступны" in result

    def test_error_result_triggers_cascade(self):
        """Results starting with 'ERROR' should trigger cascade."""
        from src.tools.design_tools import AIVideoGenerator
        tool = AIVideoGenerator()

        def mock_gen(prompt, model, duration, api_key):
            if model == "wan":
                return "ERROR: timeout"
            return f"AI-видео создано: /path/{model}.mp4"

        with self._mock_env(), \
             patch.object(tool, "_generate_video", side_effect=mock_gen):
            result = tool._run(prompt="test", model="wan", duration=5)

        assert "seedance" in result

    def test_unknown_model_uses_all_cascade(self):
        """Unknown model should not be tried, all 3 default models tried."""
        from src.tools.design_tools import AIVideoGenerator
        tool = AIVideoGenerator()

        tried_models = []

        def mock_gen(prompt, model, duration, api_key):
            tried_models.append(model)
            return None

        with self._mock_env(), \
             patch.object(tool, "_generate_video", side_effect=mock_gen):
            tool._run(prompt="test", model="unknown_model", duration=5)

        assert tried_models == ["wan", "seedance", "grok-video"]

    def test_duration_clamped_min(self):
        """Duration below 2 should be clamped to 2."""
        from src.tools.design_tools import AIVideoGenerator
        tool = AIVideoGenerator()

        with self._mock_env(), \
             patch.object(tool, "_generate_video", return_value="AI-видео создано: /path/v.mp4") as mock:
            tool._run(prompt="test", model="wan", duration=0)

        mock.assert_called_once_with("test", "wan", 2, "sk_test123")

    def test_duration_clamped_max(self):
        """Duration above 15 should be clamped to 15."""
        from src.tools.design_tools import AIVideoGenerator
        tool = AIVideoGenerator()

        with self._mock_env(), \
             patch.object(tool, "_generate_video", return_value="AI-видео создано: /path/v.mp4") as mock:
            tool._run(prompt="test", model="wan", duration=999)

        mock.assert_called_once_with("test", "wan", 15, "sk_test123")

    def test_requested_model_tried_first(self):
        """If user specifies 'grok-video', it should be tried first."""
        from src.tools.design_tools import AIVideoGenerator
        tool = AIVideoGenerator()

        tried_models = []

        def mock_gen(prompt, model, duration, api_key):
            tried_models.append(model)
            if model == "grok-video":
                return f"AI-видео создано: /path/{model}.mp4"
            return None

        with self._mock_env(), \
             patch.object(tool, "_generate_video", side_effect=mock_gen):
            result = tool._run(prompt="test", model="grok-video", duration=5)

        assert tried_models[0] == "grok-video"
        assert "grok-video" in result


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

    def test_tool_description_mentions_api_key(self):
        from src.tools.design_tools import AIVideoGenerator
        tool = AIVideoGenerator()
        assert "POLLINATIONS_API_KEY" in tool.description

    def test_tool_description_mentions_models(self):
        from src.tools.design_tools import AIVideoGenerator
        tool = AIVideoGenerator()
        assert "wan" in tool.description.lower()
        assert "seedance" in tool.description.lower()

    def test_args_schema_set(self):
        from src.tools.design_tools import AIVideoGenerator, AIVideoGeneratorInput
        tool = AIVideoGenerator()
        assert tool.args_schema is AIVideoGeneratorInput


# ── ImageGenerator defaults (Sprint 12 fix) ──────────────────

class TestImageGeneratorDefaults:
    """Test that ImageGenerator defaults to photorealistic, not isotype."""

    def test_input_schema_default_photorealistic(self):
        from src.tools.design_tools import ImageGeneratorInput
        inp = ImageGeneratorInput(prompt="a mountain scene")
        assert inp.style == "photorealistic"

    def test_run_default_style_photorealistic(self):
        """The _run method default should be photorealistic."""
        from src.tools.design_tools import ImageGenerator
        import inspect
        sig = inspect.signature(ImageGenerator._run)
        assert sig.parameters["style"].default == "photorealistic"

    def test_photorealistic_style_prefix_applied(self):
        """photorealistic style should produce quality-oriented prompt."""
        from src.tools.design_tools import _get_style_prefix
        prefix = _get_style_prefix("photorealistic")
        assert "photorealistic" in prefix.lower() or "photo" in prefix.lower()
        assert len(prefix) > 20

    def test_isotype_only_when_explicit(self):
        """isotype prefix should exist but not be default."""
        from src.tools.design_tools import _get_style_prefix
        prefix = _get_style_prefix("isotype")
        assert "ISOTYPE" in prefix or "isotype" in prefix.lower()

    def test_tool_description_warns_about_isotype(self):
        """Description should warn that isotype is not default."""
        from src.tools.design_tools import ImageGenerator
        tool = ImageGenerator()
        desc_lower = tool.description.lower()
        assert "photorealistic" in desc_lower
        assert "по умолчанию" in desc_lower


# ── Bridge default style (Sprint 12 fix) ─────────────────────

class TestBridgeImageDefaults:
    """Test that bridge.run_generate_image defaults to photorealistic."""

    def test_bridge_default_style_photorealistic(self):
        import inspect
        from src.telegram.bridge import AgentBridge
        sig = inspect.signature(AgentBridge.run_generate_image)
        assert sig.parameters["style"].default == "photorealistic"


# ── Ryan YAML structure (Sprint 12 fix) ──────────────────────

class TestRyanYAMLStructure:
    """Test that Ryan's YAML has proper prompt engineering structure."""

    @pytest.fixture
    def yaml_content(self):
        import yaml
        with open("agents/designer.yaml") as f:
            return yaml.safe_load(f)

    @pytest.fixture
    def backstory(self, yaml_content):
        return yaml_content.get("backstory", "")

    def test_has_pseudocode_section(self, backstory):
        assert "АЛГОРИТМ" in backstory or "псевдокод" in backstory

    def test_has_priority_section(self, backstory):
        assert "ПРИОРИТЕТ" in backstory

    def test_has_critical_priorities(self, backstory):
        assert "🔴" in backstory

    def test_has_self_check_section(self, backstory):
        assert "САМОПРОВЕРКА" in backstory

    def test_self_check_has_file_path_check(self, backstory):
        assert "путь к файлу" in backstory.lower() or "/data/" in backstory

    def test_self_check_has_style_check(self, backstory):
        assert "photorealistic" in backstory

    def test_has_output_format(self, backstory):
        assert "ФОРМАТ ОТВЕТА" in backstory

    def test_has_examples(self, backstory):
        assert "Пример" in backstory

    def test_photorealistic_default_mentioned(self, backstory):
        assert "photorealistic" in backstory

    def test_isotype_restriction(self, backstory):
        # isotype should be mentioned as restricted
        assert "isotype" in backstory.lower()
        assert "ТОЛЬКО" in backstory

    def test_no_fabrication_rule(self, backstory):
        assert "ЗАПРЕТ НА ВЫДУМКИ" in backstory

    def test_concise_backstory(self, backstory):
        """Backstory should be under 3000 chars (was 3500+ before restructure)."""
        assert len(backstory) < 3000
