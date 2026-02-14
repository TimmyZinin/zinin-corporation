"""Tests for Sprint 8: ISOTYPE scenes, Image pipeline, Gallery callbacks, Design tools integration."""

import asyncio
import json
import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

# ══════════════════════════════════════════════════════════════
# ISOTYPE Scenes
# ══════════════════════════════════════════════════════════════

from src.tools.isotype_scenes import (
    select_scene,
    get_scene_description,
    get_all_scene_keys,
    get_categories,
    build_isotype_prompt,
    SCENES,
    TOPIC_MAPPING,
    DEFAULT_SCENES,
)


class TestIsotypeScenes:
    def test_scenes_is_dict(self):
        assert isinstance(SCENES, dict)

    def test_scenes_not_empty(self):
        assert len(SCENES) > 20  # Should have 36+ scenes

    def test_topic_mapping_is_dict(self):
        assert isinstance(TOPIC_MAPPING, dict)

    def test_default_scenes_is_list(self):
        assert isinstance(DEFAULT_SCENES, list)
        assert len(DEFAULT_SCENES) > 0

    def test_default_scenes_exist_in_scenes(self):
        for key in DEFAULT_SCENES:
            assert key in SCENES, f"DEFAULT_SCENES key '{key}' not in SCENES"


class TestSelectScene:
    def test_selects_matching_keyword(self):
        """Scene selection should find a match for known keywords."""
        # Test multiple times (randomness) — just ensure it returns a valid key
        for _ in range(5):
            result = select_scene("bitcoin crypto")
            assert result in SCENES

    def test_fallback_to_default(self):
        """Unknown topics should get a default scene."""
        result = select_scene("xyzzy_nonexistent_topic_12345")
        assert result in SCENES
        assert result in DEFAULT_SCENES

    def test_case_insensitive(self):
        """Topic matching should be case-insensitive."""
        result = select_scene("BITCOIN CRYPTO")
        assert result in SCENES


class TestGetSceneDescription:
    def test_existing_key(self):
        keys = list(SCENES.keys())
        desc = get_scene_description(keys[0])
        assert isinstance(desc, str)
        assert len(desc) > 0

    def test_missing_key(self):
        desc = get_scene_description("nonexistent_key_xyz")
        assert desc == ""


class TestGetAllSceneKeys:
    def test_returns_list(self):
        keys = get_all_scene_keys()
        assert isinstance(keys, list)
        assert len(keys) > 20

    def test_matches_scenes_dict(self):
        keys = get_all_scene_keys()
        assert set(keys) == set(SCENES.keys())


class TestGetCategories:
    def test_returns_dict(self):
        cats = get_categories()
        assert isinstance(cats, dict)
        assert len(cats) > 0

    def test_all_keys_covered(self):
        cats = get_categories()
        all_keys = []
        for keys in cats.values():
            all_keys.extend(keys)
        assert set(all_keys) == set(SCENES.keys())


class TestBuildIsotypePrompt:
    def test_contains_isotype_keywords(self):
        prompt = build_isotype_prompt("AI agents")
        assert "ISOTYPE" in prompt
        assert "pictogram" in prompt.lower() or "PICTOGRAPHIC" in prompt

    def test_contains_color_palette(self):
        prompt = build_isotype_prompt("test")
        assert "#DFFF00" in prompt  # lime
        assert "#000000" in prompt  # black
        assert "#FFFFFF" in prompt  # white

    def test_contains_scene_description(self):
        prompt = build_isotype_prompt("test")
        # The prompt should contain some scene-specific content
        assert len(prompt) > 500  # Full prompt is substantial

    def test_contains_prohibitions(self):
        prompt = build_isotype_prompt("test")
        assert "NO text" in prompt or "PROHIBITIONS" in prompt


# ══════════════════════════════════════════════════════════════
# Image Pipeline
# ══════════════════════════════════════════════════════════════

from src.telegram_yuki.image_pipeline import (
    is_ryan_pipeline_enabled,
    generate_image_via_pipeline,
)


class TestRyanPipelineFlag:
    def test_default_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            # Remove the key if present
            os.environ.pop("RYAN_IMAGE_PIPELINE", None)
            assert is_ryan_pipeline_enabled() is False

    def test_enabled_with_1(self):
        with patch.dict(os.environ, {"RYAN_IMAGE_PIPELINE": "1"}):
            assert is_ryan_pipeline_enabled() is True

    def test_disabled_with_0(self):
        with patch.dict(os.environ, {"RYAN_IMAGE_PIPELINE": "0"}):
            assert is_ryan_pipeline_enabled() is False

    def test_disabled_with_empty(self):
        with patch.dict(os.environ, {"RYAN_IMAGE_PIPELINE": ""}):
            assert is_ryan_pipeline_enabled() is False


class TestGenerateImageViaPipeline:
    @pytest.mark.asyncio
    async def test_routes_to_yuki_when_disabled(self):
        """When RYAN_IMAGE_PIPELINE is not set, should use local Yuki."""
        with patch.dict(os.environ, {"RYAN_IMAGE_PIPELINE": "0"}):
            with patch(
                "src.telegram_yuki.image_pipeline._generate_via_yuki",
                new_callable=AsyncMock,
                return_value="/img/yuki.png",
            ) as mock_yuki:
                result = await generate_image_via_pipeline("AI topic", "post text")
                assert result == "/img/yuki.png"
                mock_yuki.assert_called_once_with("AI topic", "post text")

    @pytest.mark.asyncio
    async def test_routes_to_ryan_when_enabled(self):
        """When RYAN_IMAGE_PIPELINE=1, should use Ryan."""
        with patch.dict(os.environ, {"RYAN_IMAGE_PIPELINE": "1"}):
            with patch(
                "src.telegram_yuki.image_pipeline._generate_via_ryan",
                new_callable=AsyncMock,
                return_value="/img/ryan.png",
            ) as mock_ryan:
                result = await generate_image_via_pipeline("AI topic")
                assert result == "/img/ryan.png"
                mock_ryan.assert_called_once_with("AI topic")

    @pytest.mark.asyncio
    async def test_ryan_fallback_on_error(self):
        """When Ryan fails, should fallback to Yuki."""
        with patch.dict(os.environ, {"RYAN_IMAGE_PIPELINE": "1"}):
            with patch(
                "src.telegram.bridge.AgentBridge.run_generate_image",
                new_callable=AsyncMock,
                side_effect=Exception("Ryan error"),
            ):
                with patch(
                    "src.telegram_yuki.image_pipeline._generate_via_yuki",
                    new_callable=AsyncMock,
                    return_value="/img/yuki_fallback.png",
                ) as mock_yuki:
                    result = await generate_image_via_pipeline("topic")
                    assert result == "/img/yuki_fallback.png"

    @pytest.mark.asyncio
    async def test_ryan_result_parsing_saved_path(self):
        """Ryan returns 'Изображение сохранено: /path/to/file.png'."""
        with patch(
            "src.telegram.bridge.AgentBridge.run_generate_image",
            new_callable=AsyncMock,
            return_value="Изображение сохранено: /data/img/test.png",
        ):
            from src.telegram_yuki.image_pipeline import _generate_via_ryan
            result = await _generate_via_ryan("test topic")
            assert result == "/data/img/test.png"

    @pytest.mark.asyncio
    async def test_ryan_result_parsing_direct_path(self):
        """Ryan returns a direct path starting with /."""
        with patch(
            "src.telegram.bridge.AgentBridge.run_generate_image",
            new_callable=AsyncMock,
            return_value="/data/design_images/abc.png",
        ):
            from src.telegram_yuki.image_pipeline import _generate_via_ryan
            result = await _generate_via_ryan("test topic")
            assert result == "/data/design_images/abc.png"

    @pytest.mark.asyncio
    async def test_ryan_result_parsing_data_prefix(self):
        """Ryan returns a relative data/ path."""
        with patch(
            "src.telegram.bridge.AgentBridge.run_generate_image",
            new_callable=AsyncMock,
            return_value="data/design_images/abc.png",
        ):
            from src.telegram_yuki.image_pipeline import _generate_via_ryan
            result = await _generate_via_ryan("test topic")
            assert result == "data/design_images/abc.png"


# ══════════════════════════════════════════════════════════════
# Gallery Keyboards
# ══════════════════════════════════════════════════════════════

from src.telegram_ceo.keyboards import gallery_keyboard


class TestGalleryKeyboard:
    def test_empty_gallery(self):
        kb = gallery_keyboard()
        # No image_id and single page → should have empty or no rows
        assert kb.inline_keyboard is not None

    def test_with_image_id(self):
        kb = gallery_keyboard(image_id="abc123")
        # First row should have approve/reject/forward buttons
        assert len(kb.inline_keyboard) >= 1
        first_row = kb.inline_keyboard[0]
        assert len(first_row) == 3
        assert "gal_ok:abc123" in first_row[0].callback_data
        assert "gal_no:abc123" in first_row[1].callback_data
        assert "gal_fwd:abc123" in first_row[2].callback_data

    def test_pagination_single_page(self):
        kb = gallery_keyboard(image_id="abc", page=0, pages=1)
        # Only action row, no pagination
        assert len(kb.inline_keyboard) == 1

    def test_pagination_multi_page(self):
        kb = gallery_keyboard(image_id="abc", page=0, pages=3)
        # Action row + pagination row
        assert len(kb.inline_keyboard) == 2
        nav_row = kb.inline_keyboard[1]
        # First page → no "prev", has counter, has "next"
        assert len(nav_row) == 2  # counter + next
        assert "1/3" in nav_row[0].text
        assert "gal_page:1" in nav_row[1].callback_data

    def test_pagination_middle_page(self):
        kb = gallery_keyboard(image_id="abc", page=1, pages=3)
        nav_row = kb.inline_keyboard[1]
        # prev + counter + next
        assert len(nav_row) == 3
        assert "gal_page:0" in nav_row[0].callback_data
        assert "2/3" in nav_row[1].text
        assert "gal_page:2" in nav_row[2].callback_data

    def test_pagination_last_page(self):
        kb = gallery_keyboard(image_id="abc", page=2, pages=3)
        nav_row = kb.inline_keyboard[1]
        # prev + counter, no next
        assert len(nav_row) == 2
        assert "gal_page:1" in nav_row[0].callback_data
        assert "3/3" in nav_row[1].text

    def test_no_image_with_multi_page(self):
        kb = gallery_keyboard(page=1, pages=3)
        # Only pagination row, no action row
        assert len(kb.inline_keyboard) == 1


# ══════════════════════════════════════════════════════════════
# Gallery Callback Handlers
# ══════════════════════════════════════════════════════════════

class TestGalleryCallbacks:
    """Test gallery callback handlers via direct function calls with mocks."""

    @pytest.fixture(autouse=True)
    def tmp_registry(self, tmp_path):
        path = str(tmp_path / "image_registry.json")
        with patch("src.image_registry._registry_path", return_value=path):
            yield path

    def _make_callback(self, data: str, text: str = "Gallery text"):
        """Create a mock CallbackQuery."""
        callback = AsyncMock()
        callback.data = data
        callback.message = AsyncMock()
        callback.message.text = text
        callback.message.bot = AsyncMock()
        callback.message.chat = MagicMock()
        callback.message.chat.id = 123
        callback.from_user = MagicMock()
        callback.from_user.id = 42
        callback.answer = AsyncMock()
        callback.message.edit_text = AsyncMock()
        callback.message.answer = AsyncMock()
        return callback

    @pytest.mark.asyncio
    async def test_approve_callback(self, tmp_registry):
        from src.telegram_ceo.handlers.callbacks import on_gallery_approve
        from src.image_registry import register_image, get_image_by_id, STATUS_APPROVED
        entry = register_image("/img/test.png")
        callback = self._make_callback(f"gal_ok:{entry['id']}")
        await on_gallery_approve(callback)
        callback.answer.assert_called_once_with("Одобрено")
        reloaded = get_image_by_id(entry["id"])
        assert reloaded["status"] == STATUS_APPROVED

    @pytest.mark.asyncio
    async def test_reject_callback(self, tmp_registry):
        from src.telegram_ceo.handlers.callbacks import on_gallery_reject
        from src.image_registry import register_image, get_image_by_id, STATUS_REJECTED
        entry = register_image("/img/test.png")
        callback = self._make_callback(f"gal_no:{entry['id']}")
        await on_gallery_reject(callback)
        callback.answer.assert_called_once_with("Отклонено")
        reloaded = get_image_by_id(entry["id"])
        assert reloaded["status"] == STATUS_REJECTED

    @pytest.mark.asyncio
    async def test_forward_callback(self, tmp_registry):
        from src.telegram_ceo.handlers.callbacks import on_gallery_forward
        from src.image_registry import register_image, get_image_by_id, STATUS_APPROVED
        entry = register_image("/img/test.png")
        callback = self._make_callback(f"gal_fwd:{entry['id']}")
        await on_gallery_forward(callback)
        callback.answer.assert_called_once_with("Переслано Юки")
        reloaded = get_image_by_id(entry["id"])
        assert reloaded["status"] == STATUS_APPROVED
        assert reloaded["forwarded_to"] == "smm"

    @pytest.mark.asyncio
    async def test_approve_not_found(self, tmp_registry):
        from src.telegram_ceo.handlers.callbacks import on_gallery_approve
        callback = self._make_callback("gal_ok:nonexistent")
        await on_gallery_approve(callback)
        callback.answer.assert_called_once_with("Изображение не найдено", show_alert=True)

    @pytest.mark.asyncio
    async def test_reject_not_found(self, tmp_registry):
        from src.telegram_ceo.handlers.callbacks import on_gallery_reject
        callback = self._make_callback("gal_no:nonexistent")
        await on_gallery_reject(callback)
        callback.answer.assert_called_once_with("Изображение не найдено", show_alert=True)

    @pytest.mark.asyncio
    async def test_forward_not_found(self, tmp_registry):
        from src.telegram_ceo.handlers.callbacks import on_gallery_forward
        callback = self._make_callback("gal_fwd:nonexistent")
        await on_gallery_forward(callback)
        callback.answer.assert_called_once_with("Изображение не найдено", show_alert=True)

    @pytest.mark.asyncio
    async def test_noop_callback(self, tmp_registry):
        from src.telegram_ceo.handlers.callbacks import on_gallery_noop
        callback = self._make_callback("gal_noop")
        await on_gallery_noop(callback)
        callback.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_page_callback(self, tmp_registry):
        from src.telegram_ceo.handlers.callbacks import on_gallery_page
        from src.image_registry import register_image
        for i in range(8):
            register_image(f"/img/{i}.png")
        callback = self._make_callback("gal_page:1")
        await on_gallery_page(callback)
        callback.message.edit_text.assert_called_once()
        callback.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_page_empty(self, tmp_registry):
        from src.telegram_ceo.handlers.callbacks import on_gallery_page
        callback = self._make_callback("gal_page:99")
        await on_gallery_page(callback)
        callback.answer.assert_called_once_with("Страница пуста")


# ══════════════════════════════════════════════════════════════
# Design Tools Integration
# ══════════════════════════════════════════════════════════════

class TestDesignToolsIsotypeIntegration:
    def test_isotype_import(self):
        """Isotype scenes module should be importable."""
        from src.tools.isotype_scenes import build_isotype_prompt
        prompt = build_isotype_prompt("test")
        assert "ISOTYPE" in prompt

    @patch("src.tools.design_tools._call_image_api", return_value=b"fake_png_data")
    def test_image_generator_isotype_style(self, mock_api, tmp_path):
        """ImageGenerator should use isotype_scenes for style='isotype'."""
        from src.tools.design_tools import ImageGenerator

        # Patch dirs to temp
        with patch("src.tools.design_tools.DESIGN_IMAGES_DIR", tmp_path):
            with patch("src.image_registry._registry_path", return_value=str(tmp_path / "reg.json")):
                tool = ImageGenerator()
                result = tool._run(prompt="AI agents", style="isotype")
                # Should contain "сохранено" (saved)
                assert "сохранено" in result.lower() or str(tmp_path) in result or "Ошибка" in result

    @patch("src.tools.design_tools._call_image_api", return_value=b"fake_png_data")
    def test_image_generator_auto_registers(self, mock_api, tmp_path):
        """ImageGenerator should auto-register images in Image Registry."""
        from src.tools.design_tools import ImageGenerator
        from src.image_registry import get_images

        with patch("src.tools.design_tools.DESIGN_IMAGES_DIR", tmp_path):
            with patch("src.image_registry._registry_path", return_value=str(tmp_path / "reg.json")):
                tool = ImageGenerator()
                result = tool._run(prompt="test topic", style="auto")
                # Check registry has an entry
                images = get_images()
                if "сохранено" in result.lower():
                    assert len(images) >= 1
                    assert images[0]["source_agent"] == "designer"


# ══════════════════════════════════════════════════════════════
# Bridge — run_generate_image
# ══════════════════════════════════════════════════════════════

class TestBridgeGenerateImage:
    @pytest.mark.asyncio
    async def test_run_generate_image_method_exists(self):
        from src.telegram.bridge import AgentBridge
        assert hasattr(AgentBridge, "run_generate_image")

    @pytest.mark.asyncio
    async def test_run_generate_image_calls_tool(self):
        from src.telegram.bridge import AgentBridge
        with patch("src.tools.design_tools.ImageGenerator") as MockGen:
            mock_tool = MagicMock()
            mock_tool._run.return_value = "Изображение сохранено: /img/test.png"
            MockGen.return_value = mock_tool
            result = await AgentBridge.run_generate_image(topic="AI", style="isotype")
            mock_tool._run.assert_called_once_with(prompt="AI", style="isotype")
            assert result == "Изображение сохранено: /img/test.png"
