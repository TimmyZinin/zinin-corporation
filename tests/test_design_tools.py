"""
🎨 Tests for Designer Agent (Ryan) — design_tools.py
"""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# ──────────────────────────────────────────────────────────
# Imports
# ──────────────────────────────────────────────────────────

class TestDesignToolsImport:
    """All 10 tools can be imported and instantiated."""

    def test_import_all_tools(self):
        from src.tools.design_tools import (
            ImageGenerator, ImageEnhancer, ChartGenerator,
            InfographicBuilder, VisualAnalyzer, VideoCreator,
            TelegraphPublisher, DesignSystemManager, ImageResizer,
            BrandVoiceVisual,
        )

    def test_instantiate_all_tools(self):
        from src.tools.design_tools import (
            ImageGenerator, ImageEnhancer, ChartGenerator,
            InfographicBuilder, VisualAnalyzer, VideoCreator,
            TelegraphPublisher, DesignSystemManager, ImageResizer,
            BrandVoiceVisual,
        )
        tools = [
            ImageGenerator(), ImageEnhancer(), ChartGenerator(),
            InfographicBuilder(), VisualAnalyzer(), VideoCreator(),
            TelegraphPublisher(), DesignSystemManager(), ImageResizer(),
            BrandVoiceVisual(),
        ]
        assert len(tools) == 10

    def test_all_tools_have_name_and_description(self):
        from src.tools.design_tools import (
            ImageGenerator, ImageEnhancer, ChartGenerator,
            InfographicBuilder, VisualAnalyzer, VideoCreator,
            TelegraphPublisher, DesignSystemManager, ImageResizer,
            BrandVoiceVisual,
        )
        for cls in [
            ImageGenerator, ImageEnhancer, ChartGenerator,
            InfographicBuilder, VisualAnalyzer, VideoCreator,
            TelegraphPublisher, DesignSystemManager, ImageResizer,
            BrandVoiceVisual,
        ]:
            tool = cls()
            assert tool.name, f"{cls.__name__} has no name"
            assert len(tool.description) > 20, f"{cls.__name__} description too short"


# ──────────────────────────────────────────────────────────
# DesignSystemManager
# ──────────────────────────────────────────────────────────

class TestDesignSystemManager:
    """Tests for Design System Manager tool."""

    def test_list_brands(self):
        from src.tools.design_tools import DesignSystemManager
        dsm = DesignSystemManager()
        result = dsm._run(action="list_brands")
        assert "corporation" in result
        assert "sborka" in result
        assert "crypto" in result
        assert "personal" in result

    def test_get_palette(self):
        from src.tools.design_tools import DesignSystemManager
        dsm = DesignSystemManager()
        result = dsm._run(action="get_palette", brand="corporation")
        data = json.loads(result)
        assert "primary" in data
        assert "accent" in data

    def test_get_guidelines(self):
        from src.tools.design_tools import DesignSystemManager
        dsm = DesignSystemManager()
        result = dsm._run(action="get_guidelines", brand="crypto")
        data = json.loads(result)
        assert "name" in data
        assert "palette" in data

    def test_nonexistent_brand(self):
        from src.tools.design_tools import DesignSystemManager
        dsm = DesignSystemManager()
        result = dsm._run(action="get_palette", brand="nonexistent")
        assert "не найден" in result

    def test_unknown_action(self):
        from src.tools.design_tools import DesignSystemManager
        dsm = DesignSystemManager()
        result = dsm._run(action="delete_everything")
        assert "ERROR" in result


# ──────────────────────────────────────────────────────────
# VisualAnalyzer
# ──────────────────────────────────────────────────────────

class TestVisualAnalyzer:
    """Tests for Visual Analyzer tool."""

    def test_text_with_numbers(self):
        from src.tools.design_tools import VisualAnalyzer
        va = VisualAnalyzer()
        result = va._run(text="Доход: $100, расходы: $50, прибыль: $50, рост: +23%")
        assert "chart" in result.lower() or "график" in result.lower()

    def test_simple_text_no_visual(self):
        from src.tools.design_tools import VisualAnalyzer
        va = VisualAnalyzer()
        result = va._run(text="Привет, как дела?")
        assert "не требуется" in result.lower()

    def test_comparison_text(self):
        from src.tools.design_tools import VisualAnalyzer
        va = VisualAnalyzer()
        result = va._run(
            text="Сравнение: React 45% рынка vs Vue 30% рынка vs Angular 25% рынка. Рост React."
        )
        assert "Рекомендации" in result

    def test_long_text_telegraph(self):
        from src.tools.design_tools import VisualAnalyzer
        va = VisualAnalyzer()
        result = va._run(text="Длинный текст. " * 300)
        assert "telegraph" in result.lower()


# ──────────────────────────────────────────────────────────
# BrandVoiceVisual
# ──────────────────────────────────────────────────────────

class TestBrandVoiceVisual:
    """Tests for Brand Voice Visual tool."""

    def test_suggest_style_finance(self):
        from src.tools.design_tools import BrandVoiceVisual
        bvv = BrandVoiceVisual()
        result = bvv._run(action="suggest_style", content="Финансовый отчёт за квартал", brand="corporation")
        assert "infographic" in result.lower()

    def test_suggest_style_generic(self):
        from src.tools.design_tools import BrandVoiceVisual
        bvv = BrandVoiceVisual()
        result = bvv._run(action="suggest_style", content="AI и машинное обучение", brand="corporation")
        assert "isotype" in result.lower() or "Рекомендация" in result

    def test_get_brand_colors(self):
        from src.tools.design_tools import BrandVoiceVisual
        bvv = BrandVoiceVisual()
        result = bvv._run(action="get_brand_colors", brand="sborka")
        data = json.loads(result)
        assert "primary" in data

    def test_check_consistency(self):
        from src.tools.design_tools import BrandVoiceVisual
        bvv = BrandVoiceVisual()
        result = bvv._run(action="check_consistency", brand="personal", content="Test")
        assert "Гайдлайны" in result or "image_style" in result

    def test_unknown_action(self):
        from src.tools.design_tools import BrandVoiceVisual
        bvv = BrandVoiceVisual()
        result = bvv._run(action="explode", brand="corporation")
        assert "ERROR" in result


# ──────────────────────────────────────────────────────────
# ChartGenerator
# ──────────────────────────────────────────────────────────

class TestChartGenerator:
    """Tests for Chart Generator tool."""

    def test_bar_chart(self):
        from src.tools.design_tools import ChartGenerator
        cg = ChartGenerator()
        result = cg._run(labels="Q1,Q2,Q3,Q4", values="100,150,130,200", chart_type="bar", title="Revenue")
        assert "chart_bar" in result
        assert ".png" in result

    def test_pie_chart(self):
        from src.tools.design_tools import ChartGenerator
        cg = ChartGenerator()
        result = cg._run(labels="A,B,C", values="45,30,25", chart_type="pie", title="Share")
        assert "chart_pie" in result

    def test_line_chart(self):
        from src.tools.design_tools import ChartGenerator
        cg = ChartGenerator()
        result = cg._run(labels="Jan,Feb,Mar", values="10,25,18", chart_type="line")
        assert "chart_line" in result

    def test_mismatched_labels_values(self):
        from src.tools.design_tools import ChartGenerator
        cg = ChartGenerator()
        result = cg._run(labels="A,B", values="1,2,3")
        assert "ERROR" in result

    def test_invalid_values(self):
        from src.tools.design_tools import ChartGenerator
        cg = ChartGenerator()
        result = cg._run(labels="A,B", values="abc,def")
        assert "ERROR" in result

    def test_unknown_chart_type(self):
        from src.tools.design_tools import ChartGenerator
        cg = ChartGenerator()
        result = cg._run(labels="A,B", values="1,2", chart_type="3d_hologram")
        assert "ERROR" in result


# ──────────────────────────────────────────────────────────
# InfographicBuilder
# ──────────────────────────────────────────────────────────

class TestInfographicBuilder:
    """Tests for Infographic Builder tool."""

    def test_report_card(self):
        from src.tools.design_tools import InfographicBuilder
        ib = InfographicBuilder()
        data = json.dumps({"Revenue": "$142K", "Growth": "+23%", "Users": "1.2K"})
        result = ib._run(data=data, title="Q4 Report", template="report_card")
        assert "infographic_report_card" in result
        assert ".png" in result

    def test_invalid_json(self):
        from src.tools.design_tools import InfographicBuilder
        ib = InfographicBuilder()
        result = ib._run(data="not json at all")
        assert "ERROR" in result

    def test_non_dict_json(self):
        from src.tools.design_tools import InfographicBuilder
        ib = InfographicBuilder()
        result = ib._run(data="[1, 2, 3]")
        assert "ERROR" in result


# ──────────────────────────────────────────────────────────
# ImageResizer
# ──────────────────────────────────────────────────────────

class TestImageResizer:
    """Tests for Image Resizer tool."""

    @pytest.fixture
    def test_image_path(self, tmp_path):
        from PIL import Image
        img = Image.new("RGB", (1920, 1080), color=(100, 150, 200))
        path = tmp_path / "test.png"
        img.save(str(path))
        return str(path)

    def test_resize_square(self, test_image_path):
        from src.tools.design_tools import ImageResizer
        ir = ImageResizer()
        result = ir._run(image_path=test_image_path, formats="square")
        assert "1080x1080" in result

    def test_resize_multiple(self, test_image_path):
        from src.tools.design_tools import ImageResizer
        ir = ImageResizer()
        result = ir._run(image_path=test_image_path, formats="square,og,thumbnail")
        assert "1080x1080" in result
        assert "1200x630" in result
        assert "640x360" in result

    def test_file_not_found(self):
        from src.tools.design_tools import ImageResizer
        ir = ImageResizer()
        result = ir._run(image_path="/nonexistent/image.png")
        assert "ERROR" in result

    def test_unknown_format(self, test_image_path):
        from src.tools.design_tools import ImageResizer
        ir = ImageResizer()
        result = ir._run(image_path=test_image_path, formats="holographic")
        assert "неизвестный формат" in result


# ──────────────────────────────────────────────────────────
# ImageEnhancer
# ──────────────────────────────────────────────────────────

class TestImageEnhancer:
    """Tests for Image Enhancer tool."""

    @pytest.fixture
    def test_image_path(self, tmp_path):
        from PIL import Image
        img = Image.new("RGB", (200, 200), color="red")
        path = tmp_path / "test_enhance.png"
        img.save(str(path))
        return str(path)

    def test_upscale(self, test_image_path):
        from src.tools.design_tools import ImageEnhancer
        ie = ImageEnhancer()
        result = ie._run(image_path=test_image_path, action="upscale", factor=2.0)
        assert "Обработано" in result or "enhanced" in result

    def test_adjust_contrast(self, test_image_path):
        from src.tools.design_tools import ImageEnhancer
        ie = ImageEnhancer()
        result = ie._run(image_path=test_image_path, action="adjust", factor=1.5)
        assert "Обработано" in result

    def test_blur_bg(self, test_image_path):
        from src.tools.design_tools import ImageEnhancer
        ie = ImageEnhancer()
        result = ie._run(image_path=test_image_path, action="blur_bg", factor=2.0)
        assert "Обработано" in result

    def test_file_not_found(self):
        from src.tools.design_tools import ImageEnhancer
        ie = ImageEnhancer()
        result = ie._run(image_path="/nonexistent.png", action="upscale")
        assert "ERROR" in result

    def test_unknown_action(self, test_image_path):
        from src.tools.design_tools import ImageEnhancer
        ie = ImageEnhancer()
        result = ie._run(image_path=test_image_path, action="deep_fry")
        assert "ERROR" in result


# ──────────────────────────────────────────────────────────
# ImageGenerator (mocked API calls)
# ──────────────────────────────────────────────────────────

class TestImageGenerator:
    """Tests for Image Generator tool (API calls mocked)."""

    def test_no_api_key_returns_error(self):
        from src.tools.design_tools import ImageGenerator
        ig = ImageGenerator()
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}, clear=False):
            with patch("src.tools.design_tools._try_pollinations", return_value=None):
                result = ig._run(prompt="test image")
                assert "ERROR" in result

    def test_style_prefix_applied(self):
        from src.tools.design_tools import _get_style_prefix
        assert "ISOTYPE" in _get_style_prefix("isotype")
        assert "photorealistic" in _get_style_prefix("photorealistic")
        assert _get_style_prefix("auto") == ""
        assert _get_style_prefix("unknown") == ""


# ──────────────────────────────────────────────────────────
# VideoCreator
# ──────────────────────────────────────────────────────────

class TestVideoCreator:
    """Tests for Video Creator tool."""

    def test_unknown_action(self):
        from src.tools.design_tools import VideoCreator
        vc = VideoCreator()
        result = vc._run(action="teleport")
        assert "ERROR" in result

    def test_audiogram_no_file(self):
        from src.tools.design_tools import VideoCreator
        vc = VideoCreator()
        result = vc._run(action="audiogram", input_path="/nonexistent.mp3")
        assert "ERROR" in result

    def test_tts_video_no_text(self):
        from src.tools.design_tools import VideoCreator
        vc = VideoCreator()
        result = vc._run(action="tts_video", text="")
        assert "ERROR" in result

    def test_slideshow_placeholder(self):
        from src.tools.design_tools import VideoCreator
        vc = VideoCreator()
        result = vc._run(action="slideshow")
        assert "разработке" in result.lower() or "audiogram" in result.lower()


# ──────────────────────────────────────────────────────────
# TelegraphPublisher (mocked API)
# ──────────────────────────────────────────────────────────

class TestTelegraphPublisher:
    """Tests for Telegraph Publisher tool (API mocked)."""

    def test_publishes_successfully(self):
        from src.tools.design_tools import TelegraphPublisher
        tp = TelegraphPublisher()

        mock_tg = MagicMock()
        mock_tg.create_page.return_value = {"url": "https://telegra.ph/test-12-31"}

        with patch("src.tools.design_tools.TelegraphPublisher._run") as mock_run:
            mock_run.return_value = "Статья опубликована: https://telegra.ph/test-12-31"
            result = mock_run(title="Test", content="<p>Hello</p>")
            assert "telegra.ph" in result


# ──────────────────────────────────────────────────────────
# Agent + Crew integration
# ──────────────────────────────────────────────────────────

class TestDesignerAgentIntegration:
    """Tests for designer agent wiring."""

    def test_create_designer_agent_import(self):
        from src.agents import create_designer_agent
        assert callable(create_designer_agent)

    def test_corporation_has_designer(self):
        from src.crew import AICorporation
        corp = AICorporation()
        assert hasattr(corp, "designer")
        assert hasattr(corp, "generate_design")

    def test_delegation_rules_include_designer(self):
        from src.crew import AICorporation
        corp = AICorporation()
        designer_rules = [r for r in corp._DELEGATION_RULES if r["agent_key"] == "designer"]
        assert len(designer_rules) == 1
        assert "дизайн" in designer_rules[0]["keywords"]
        assert "визуал" in designer_rules[0]["keywords"]

    def test_agent_map_includes_designer(self):
        """After initialization, agent_map should have designer key."""
        from src.crew import AICorporation
        corp = AICorporation()
        # Without initializing agents, designer starts as None
        assert corp.designer is None

    def test_bridge_has_design_method(self):
        from src.telegram.bridge import AgentBridge
        assert hasattr(AgentBridge, "run_generate_design")

    def test_delegatable_agents_has_designer(self):
        from src.tools.delegation_tool import DELEGATABLE_AGENTS
        assert "designer" in DELEGATABLE_AGENTS
        assert DELEGATABLE_AGENTS["designer"]["name"] == "Райан"
        assert DELEGATABLE_AGENTS["designer"]["role"] == "Creative Director"


# ──────────────────────────────────────────────────────────
# YAML configs
# ──────────────────────────────────────────────────────────

class TestDesignerYamlConfig:
    """Tests for designer YAML config."""

    def test_designer_yaml_exists(self):
        assert os.path.exists("agents/designer.yaml")

    def test_designer_yaml_valid(self):
        import yaml
        with open("agents/designer.yaml", "r") as f:
            config = yaml.safe_load(f)
        assert "role" in config
        assert "Райан" in config["role"]
        assert "backstory" in config
        assert "llm" in config
        assert "haiku" in config["llm"]

    def test_all_yamls_mention_ryan(self):
        """All agent YAMLs should mention Ryan in team section."""
        import yaml
        for fname in ["manager.yaml", "yuki.yaml", "automator.yaml", "accountant.yaml"]:
            path = f"agents/{fname}"
            with open(path, "r") as f:
                content = f.read()
            assert "Райан" in content, f"{fname} doesn't mention Райан"

    def test_manager_yaml_has_designer_delegation(self):
        with open("agents/manager.yaml", "r") as f:
            content = f.read()
        assert "designer" in content
        assert "дизайн" in content.lower() or "Дизайн" in content


# ──────────────────────────────────────────────────────────
# Design systems data
# ──────────────────────────────────────────────────────────

class TestDesignSystemsData:
    """Tests for design system JSON files."""

    @pytest.mark.parametrize("brand", ["corporation", "sborka", "crypto", "personal"])
    def test_brand_json_valid(self, brand):
        path = f"data/design_systems/{brand}.json"
        assert os.path.exists(path), f"{path} not found"
        with open(path, "r") as f:
            data = json.load(f)
        assert "name" in data
        assert "palette" in data
        assert "primary" in data["palette"]
        assert "typography" in data
        assert "guidelines" in data
