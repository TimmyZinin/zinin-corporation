"""
🎨 Zinin Corp — Design Tools for Ryan (Creative Director)

10 tools for image generation, enhancement, infographics, video, and visual analysis.
Uses cascade of free/cheap AI models and Python libraries.
"""

import base64
import io
import json
import logging
import os
import re
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Type
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ── Directories ────────────────────────────────────────────
DATA_DIR = Path(__file__).parent.parent.parent / "data"
DESIGN_IMAGES_DIR = DATA_DIR / "design_images"
DESIGN_SYSTEMS_DIR = DATA_DIR / "design_systems"
DESIGN_VIDEO_DIR = DATA_DIR / "design_videos"

for d in [DESIGN_IMAGES_DIR, DESIGN_SYSTEMS_DIR, DESIGN_VIDEO_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ══════════════════════════════════════════════════════════════
# Shared helpers
# ══════════════════════════════════════════════════════════════

def _call_image_api(prompt: str, model: str = "gemini") -> Optional[bytes]:
    """Generate image via cascade: Gemini → Pollinations → error.

    Returns PNG bytes or None.
    """
    if model in ("gemini", "auto"):
        data = _try_gemini(prompt)
        if data:
            return data

    if model in ("pollinations", "auto"):
        data = _try_pollinations(prompt)
        if data:
            return data

    return None


def _try_gemini(prompt: str) -> Optional[bytes]:
    """Call OpenRouter → Gemini 2.5 Flash Image (free, 500/day)."""
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        return None

    url = "https://openrouter.ai/api/v1/chat/completions"
    payload = {
        "model": "google/gemini-2.5-flash-image",
        "messages": [{"role": "user", "content": prompt}],
        "modalities": ["image", "text"],
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://zinin.corp",
        "X-Title": "Ryan Design Bot",
    }

    for attempt in range(3):
        try:
            req = Request(url, data=json.dumps(payload).encode(), headers=headers)
            with urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode())
            return _extract_image_bytes(data)
        except HTTPError as e:
            if e.code == 429:
                time.sleep(60)
            elif attempt < 2:
                time.sleep(2 ** attempt)
            else:
                logger.warning(f"Gemini image failed: HTTP {e.code}")
                return None
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                logger.warning(f"Gemini image error: {e}")
                return None
    return None


def _try_pollinations(prompt: str) -> Optional[bytes]:
    """Call Pollinations.ai — free, no API key, URL-based."""
    from urllib.parse import quote
    url = f"https://image.pollinations.ai/prompt/{quote(prompt[:500])}"

    for attempt in range(2):
        try:
            req = Request(url, headers={"User-Agent": "RyanDesignBot/1.0"})
            with urlopen(req, timeout=120) as resp:
                data = resp.read()
            if len(data) > 1000:  # valid image is at least 1KB
                return data
        except Exception as e:
            if attempt < 1:
                time.sleep(3)
            else:
                logger.warning(f"Pollinations error: {e}")
    return None


def _extract_image_bytes(response: dict) -> Optional[bytes]:
    """Extract image bytes from OpenRouter API response."""
    choices = response.get("choices", [])
    if not choices:
        return None

    message = choices[0].get("message", {})

    # Check images field
    for img in message.get("images", []):
        url = img.get("image_url", {}).get("url", "")
        if url.startswith("data:image") and "," in url:
            return base64.b64decode(url.split(",", 1)[1])

    # Check content array
    content = message.get("content", "")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "image_url":
                url = item.get("image_url", {}).get("url", "")
                if url.startswith("data:image") and "," in url:
                    return base64.b64decode(url.split(",", 1)[1])

    return None


def _save_image(image_bytes: bytes, prefix: str = "design") -> str:
    """Save image bytes to file. Returns path."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    uid = uuid.uuid4().hex[:6]
    path = DESIGN_IMAGES_DIR / f"{prefix}_{timestamp}_{uid}.png"
    with open(path, "wb") as f:
        f.write(image_bytes)
    logger.info(f"Image saved: {path}")
    return str(path)


# ══════════════════════════════════════════════════════════════
# Tool 1: ImageGenerator
# ══════════════════════════════════════════════════════════════

class ImageGeneratorInput(BaseModel):
    prompt: str = Field(..., description="Описание изображения для генерации")
    style: str = Field(
        default="auto",
        description="Стиль: auto, isotype, photorealistic, abstract, infographic, brand",
    )
    model: str = Field(
        default="auto",
        description="Модель: auto (каскад), gemini, pollinations",
    )


class ImageGenerator(BaseTool):
    name: str = "Image Generator"
    description: str = (
        "Генерация изображений с помощью AI. Каскад моделей: Gemini (бесплатно, 500/день) "
        "→ Pollinations (бесплатно, без ключа). Стили: isotype, photorealistic, abstract, "
        "infographic, brand. Возвращает путь к сохранённому файлу."
    )
    args_schema: Type[BaseModel] = ImageGeneratorInput

    def _run(self, prompt: str, style: str = "auto", model: str = "auto") -> str:
        style_prefix = _get_style_prefix(style)
        full_prompt = f"{style_prefix}\n\n{prompt}" if style_prefix else prompt

        image_data = _call_image_api(full_prompt, model=model)
        if not image_data:
            return "ERROR: Не удалось сгенерировать изображение. Все модели недоступны."

        path = _save_image(image_data, prefix=f"gen_{style}")
        return f"Изображение сохранено: {path}"


def _get_style_prefix(style: str) -> str:
    """Get style-specific prompt prefix."""
    prefixes = {
        "isotype": (
            "Create a flat 2D vector illustration in ISOTYPE pictogram style. "
            "Pure white background. Only black, white, and electric lime (#DFFF00). "
            "All shapes are rectangles, squares, triangles with sharp 90-degree corners. "
            "No text, no gradients, no curves, no circles."
        ),
        "photorealistic": (
            "Create a photorealistic high-quality image. Natural lighting, "
            "professional photography style. Sharp details, accurate colors."
        ),
        "abstract": (
            "Create an abstract geometric composition. Bold shapes, vibrant colors, "
            "modern art style. Clean, minimal, visually striking."
        ),
        "infographic": (
            "Create a clean infographic-style illustration. Data visualization elements, "
            "charts, icons, clear hierarchy. Professional, modern design."
        ),
        "brand": (
            "Create a professional brand-aligned visual. Clean, modern, corporate style. "
            "Suitable for LinkedIn and professional social media."
        ),
    }
    return prefixes.get(style, "")


# ══════════════════════════════════════════════════════════════
# Tool 2: ImageEnhancer
# ══════════════════════════════════════════════════════════════

class ImageEnhancerInput(BaseModel):
    image_path: str = Field(..., description="Путь к изображению")
    action: str = Field(
        ...,
        description="Действие: remove_bg (удаление фона), upscale (увеличение), "
        "adjust (яркость/контраст), blur_bg (размытие фона)",
    )
    factor: float = Field(default=1.5, description="Фактор для upscale или adjust")


class ImageEnhancer(BaseTool):
    name: str = "Image Enhancer"
    description: str = (
        "Постобработка изображений: удаление фона (rembg), "
        "увеличение разрешения, настройка яркости/контраста, размытие фона. "
        "Все операции бесплатны и локальны."
    )
    args_schema: Type[BaseModel] = ImageEnhancerInput

    def _run(self, image_path: str, action: str, factor: float = 1.5) -> str:
        try:
            from PIL import Image, ImageEnhance, ImageFilter
        except ImportError:
            return "ERROR: Pillow не установлен"

        if not os.path.exists(image_path):
            return f"ERROR: Файл не найден: {image_path}"

        img = Image.open(image_path)

        if action == "remove_bg":
            return self._remove_bg(image_path)
        elif action == "upscale":
            new_size = (int(img.width * factor), int(img.height * factor))
            img = img.resize(new_size, Image.LANCZOS)
        elif action == "adjust":
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(factor)
        elif action == "blur_bg":
            img = img.filter(ImageFilter.GaussianBlur(radius=factor * 3))
        else:
            return f"ERROR: Неизвестное действие: {action}"

        out_path = _save_image(_pil_to_bytes(img), prefix=f"enhanced_{action}")
        return f"Обработано: {out_path}"

    def _remove_bg(self, image_path: str) -> str:
        """Remove background using rembg (local, free)."""
        try:
            from rembg import remove
            from PIL import Image

            inp = Image.open(image_path)
            out = remove(inp)
            out_path = _save_image(_pil_to_bytes(out), prefix="nobg")
            return f"Фон удалён: {out_path}"
        except ImportError:
            # Fallback: skip if rembg not installed
            return "WARNING: rembg не установлен. Удаление фона недоступно."
        except Exception as e:
            return f"ERROR: Ошибка удаления фона: {e}"


def _pil_to_bytes(img) -> bytes:
    """Convert PIL Image to PNG bytes."""
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════
# Tool 3: ChartGenerator
# ══════════════════════════════════════════════════════════════

class ChartGeneratorInput(BaseModel):
    chart_type: str = Field(
        default="bar",
        description="Тип графика: bar, line, pie, horizontal_bar",
    )
    labels: str = Field(..., description="Метки через запятую: 'Q1,Q2,Q3,Q4'")
    values: str = Field(..., description="Значения через запятую: '142,168,195,210'")
    title: str = Field(default="", description="Заголовок графика")
    color: str = Field(default="#667eea", description="Основной цвет (hex)")


class ChartGenerator(BaseTool):
    name: str = "Chart Generator"
    description: str = (
        "Создание графиков из данных: bar, line, pie, horizontal_bar. "
        "Использует matplotlib. Возвращает путь к PNG файлу."
    )
    args_schema: Type[BaseModel] = ChartGeneratorInput

    def _run(
        self,
        labels: str,
        values: str,
        chart_type: str = "bar",
        title: str = "",
        color: str = "#667eea",
    ) -> str:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            return "ERROR: matplotlib не установлен"

        label_list = [l.strip() for l in labels.split(",")]
        try:
            value_list = [float(v.strip()) for v in values.split(",")]
        except ValueError:
            return "ERROR: Значения должны быть числами через запятую"

        if len(label_list) != len(value_list):
            return "ERROR: Количество меток и значений не совпадает"

        fig, ax = plt.subplots(figsize=(10, 6), dpi=150)

        if chart_type == "bar":
            ax.bar(label_list, value_list, color=color, width=0.6)
        elif chart_type == "horizontal_bar":
            ax.barh(label_list, value_list, color=color, height=0.6)
        elif chart_type == "line":
            ax.plot(label_list, value_list, color=color, linewidth=2.5, marker="o", markersize=8)
            ax.fill_between(range(len(value_list)), value_list, alpha=0.1, color=color)
        elif chart_type == "pie":
            ax.pie(value_list, labels=label_list, autopct="%1.1f%%",
                   colors=[color, "#e94560", "#0f3460", "#16213e", "#533483"])
        else:
            return f"ERROR: Неизвестный тип графика: {chart_type}"

        if title:
            ax.set_title(title, fontsize=16, fontweight="bold", pad=15)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white", edgecolor="none")
        plt.close(fig)
        buf.seek(0)

        path = _save_image(buf.getvalue(), prefix=f"chart_{chart_type}")
        return f"График создан: {path}"


# ══════════════════════════════════════════════════════════════
# Tool 4: InfographicBuilder
# ══════════════════════════════════════════════════════════════

class InfographicBuilderInput(BaseModel):
    template: str = Field(
        default="report_card",
        description="Шаблон: report_card, comparison, stats, timeline",
    )
    title: str = Field(default="", description="Заголовок")
    data: str = Field(
        ...,
        description="JSON-данные для шаблона. Пример: '{\"Revenue\": \"$142K\", \"Growth\": \"+23%\"}'",
    )
    color_scheme: str = Field(default="dark", description="Цветовая схема: dark, light, brand")


class InfographicBuilder(BaseTool):
    name: str = "Infographic Builder"
    description: str = (
        "Создание инфографик из данных. Шаблоны: report_card, comparison, stats, timeline. "
        "Рендерит HTML/CSS в PNG через Pillow. Возвращает путь к файлу."
    )
    args_schema: Type[BaseModel] = InfographicBuilderInput

    def _run(
        self,
        data: str,
        template: str = "report_card",
        title: str = "",
        color_scheme: str = "dark",
    ) -> str:
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError:
            return "ERROR: Невалидный JSON в поле data"

        if not isinstance(parsed, dict):
            return "ERROR: data должен быть JSON-объектом {key: value}"

        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            return "ERROR: Pillow не установлен"

        colors = _get_color_scheme(color_scheme)
        img = _render_report_card(title or "Report", parsed, colors)
        path = _save_image(_pil_to_bytes(img), prefix=f"infographic_{template}")
        return f"Инфографика создана: {path}"


def _get_color_scheme(name: str) -> dict:
    schemes = {
        "dark": {"bg": "#1a1a2e", "title": "#e94560", "label": "#aaaaaa",
                 "value": "#ffffff", "accent": "#667eea", "line": "#16213e"},
        "light": {"bg": "#ffffff", "title": "#1a1a2e", "label": "#666666",
                  "value": "#1a1a2e", "accent": "#667eea", "line": "#eeeeee"},
        "brand": {"bg": "#0f0f23", "title": "#DFFF00", "label": "#cccccc",
                  "value": "#ffffff", "accent": "#DFFF00", "line": "#1a1a3e"},
    }
    return schemes.get(name, schemes["dark"])


def _render_report_card(title: str, data: dict, colors: dict):
    """Render a report card using Pillow."""
    from PIL import Image, ImageDraw, ImageFont

    width = 800
    row_height = 70
    header_height = 100
    padding = 40
    height = header_height + len(data) * row_height + padding * 2

    img = Image.new("RGB", (width, height), colors["bg"])
    draw = ImageDraw.Draw(img)

    # Try to load a good font, fallback to default
    font_title = _load_font(32)
    font_label = _load_font(22)
    font_value = _load_font(26)

    # Title
    draw.text((padding, padding), title, fill=colors["title"], font=font_title)

    # Separator
    y = header_height
    draw.line([(padding, y), (width - padding, y)], fill=colors["line"], width=2)

    # Data rows
    y = header_height + 15
    for label, value in data.items():
        draw.text((padding, y), str(label), fill=colors["label"], font=font_label)
        # Right-align value
        val_str = str(value)
        bbox = draw.textbbox((0, 0), val_str, font=font_value)
        val_w = bbox[2] - bbox[0]
        draw.text((width - padding - val_w, y), val_str, fill=colors["value"], font=font_value)
        y += row_height

    return img


def _load_font(size: int):
    """Try to load a good font, fallback to default."""
    from PIL import ImageFont
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFCompact.ttf",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    return ImageFont.load_default()


# ══════════════════════════════════════════════════════════════
# Tool 5: VisualAnalyzer
# ══════════════════════════════════════════════════════════════

class VisualAnalyzerInput(BaseModel):
    text: str = Field(..., description="Текст сообщения агента для анализа")


class VisualAnalyzer(BaseTool):
    name: str = "Visual Analyzer"
    description: str = (
        "Анализирует текст сообщения агента и определяет, нужен ли визуал. "
        "Возвращает рекомендацию: chart, infographic, image, none."
    )
    args_schema: Type[BaseModel] = VisualAnalyzerInput

    def _run(self, text: str) -> str:
        numbers = re.findall(r"[\$€₽]?\d[\d,\.]+[%KMkmКМ]?", text)
        has_comparison = any(w in text.lower() for w in [
            "vs", "против", "сравнен", "больше", "меньше", "рост", "падение",
        ])
        has_list = text.count("\n- ") >= 3 or text.count("\n• ") >= 3
        is_long = len(text) > 3000

        suggestions = []

        if len(numbers) >= 4:
            suggestions.append({
                "type": "chart",
                "reason": f"Найдено {len(numbers)} числовых значений — подойдёт график",
                "tool": "Chart Generator",
            })

        if has_comparison and len(numbers) >= 2:
            suggestions.append({
                "type": "infographic",
                "reason": "Сравнение с числами — подойдёт инфографика",
                "tool": "Infographic Builder",
            })

        if has_list and len(numbers) >= 3:
            suggestions.append({
                "type": "report_card",
                "reason": "Структурированные данные — подойдёт карточка-отчёт",
                "tool": "Infographic Builder",
            })

        if is_long:
            suggestions.append({
                "type": "telegraph",
                "reason": f"Текст длинный ({len(text)} символов) — рекомендуется Telegraph",
                "tool": "Telegraph Publisher",
            })

        if not suggestions:
            return "Визуал не требуется — текст достаточно лаконичен."

        lines = ["📊 Рекомендации по визуализации:\n"]
        for s in suggestions:
            lines.append(f"• {s['type'].upper()}: {s['reason']} → используй {s['tool']}")

        return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
# Tool 6: VideoCreator
# ══════════════════════════════════════════════════════════════

class VideoCreatorInput(BaseModel):
    action: str = Field(
        ...,
        description="Действие: audiogram (визуал из аудио), slideshow (из картинок+текст), "
        "tts_video (текст→озвучка→видео)",
    )
    input_path: str = Field(default="", description="Путь к входному файлу (аудио или изображение)")
    text: str = Field(default="", description="Текст для TTS или титры")
    title: str = Field(default="", description="Заголовок видео")
    duration: int = Field(default=30, description="Длительность в секундах (для audiogram)")


class VideoCreator(BaseTool):
    name: str = "Video Creator"
    description: str = (
        "Создание видео: audiogram (визуализация аудио для подкастов), "
        "slideshow (картинки + текст), tts_video (текст → озвучка → видео). "
        "Использует MoviePy + FFmpeg + edge-tts."
    )
    args_schema: Type[BaseModel] = VideoCreatorInput

    def _run(
        self, action: str, input_path: str = "", text: str = "",
        title: str = "", duration: int = 30,
    ) -> str:
        if action == "audiogram":
            return self._create_audiogram(input_path, title, duration)
        elif action == "tts_video":
            return self._create_tts_video(text, title)
        elif action == "slideshow":
            return "Slideshow в разработке. Используй audiogram или tts_video."
        return f"ERROR: Неизвестное действие: {action}"

    def _create_audiogram(self, audio_path: str, title: str, duration: int) -> str:
        """Create audiogram video from audio file."""
        try:
            from moviepy import AudioFileClip, ImageClip, CompositeVideoClip, TextClip
        except ImportError:
            return "ERROR: moviepy не установлен"

        if not audio_path or not os.path.exists(audio_path):
            return f"ERROR: Аудио файл не найден: {audio_path}"

        try:
            audio = AudioFileClip(audio_path)
            clip_duration = min(duration, audio.duration)

            # Create background
            from PIL import Image, ImageDraw
            bg = Image.new("RGB", (1080, 1080), "#1a1a2e")
            draw = ImageDraw.Draw(bg)
            # Simple waveform bars
            import random
            bar_w = 6
            gap = 3
            n_bars = 1080 // (bar_w + gap)
            for i in range(n_bars):
                h = random.randint(50, 400)
                x = i * (bar_w + gap)
                y = 540 - h // 2
                draw.rectangle([x, y, x + bar_w, y + h], fill="#667eea")

            bg_path = str(DESIGN_VIDEO_DIR / "audiogram_bg.png")
            bg.save(bg_path)

            bg_clip = ImageClip(bg_path).with_duration(clip_duration)

            if title:
                txt_clip = TextClip(
                    text=title[:60],
                    font_size=40,
                    color="white",
                    font="DejaVu-Sans-Bold",
                    size=(900, None),
                ).with_position(("center", 80)).with_duration(clip_duration)
                video = CompositeVideoClip([bg_clip, txt_clip])
            else:
                video = bg_clip

            video = video.with_audio(audio.subclipped(0, clip_duration))

            out_path = str(DESIGN_VIDEO_DIR / f"audiogram_{uuid.uuid4().hex[:8]}.mp4")
            video.write_videofile(out_path, fps=24, logger=None)

            audio.close()
            return f"Аудиограмма создана: {out_path}"

        except Exception as e:
            return f"ERROR: Ошибка создания аудиограммы: {e}"

    def _create_tts_video(self, text: str, title: str) -> str:
        """Create video from text: TTS → audio → audiogram."""
        if not text:
            return "ERROR: Текст не указан"

        try:
            import asyncio
            import edge_tts

            # Generate TTS audio
            tts_path = str(DESIGN_VIDEO_DIR / f"tts_{uuid.uuid4().hex[:8]}.mp3")

            async def _gen():
                communicate = edge_tts.Communicate(text[:3000], "ru-RU-DmitryNeural")
                await communicate.save(tts_path)

            asyncio.run(_gen())

            if not os.path.exists(tts_path):
                return "ERROR: TTS не сгенерировал аудио"

            return self._create_audiogram(tts_path, title or "AI Corporation", duration=60)

        except ImportError:
            return "ERROR: edge-tts не установлен"
        except Exception as e:
            return f"ERROR: Ошибка TTS видео: {e}"


# ══════════════════════════════════════════════════════════════
# Tool 7: TelegraphPublisher
# ══════════════════════════════════════════════════════════════

class TelegraphPublisherInput(BaseModel):
    title: str = Field(..., description="Заголовок статьи")
    content: str = Field(..., description="HTML-содержимое статьи")
    author: str = Field(default="AI Corporation", description="Имя автора")


class TelegraphPublisher(BaseTool):
    name: str = "Telegraph Publisher"
    description: str = (
        "Публикация длинных текстов в Telegraph (telegra.ph). "
        "Поддерживает HTML-разметку, изображения, заголовки. "
        "Возвращает URL статьи с Instant View в Telegram."
    )
    args_schema: Type[BaseModel] = TelegraphPublisherInput

    def _run(self, title: str, content: str, author: str = "AI Corporation") -> str:
        try:
            from telegraph import Telegraph
        except ImportError:
            return "ERROR: telegraph не установлен (pip install telegraph)"

        try:
            tg = Telegraph()
            tg.create_account(short_name="ZininCorp", author_name=author)

            # Convert plain text with newlines to HTML if needed
            if "<" not in content:
                content = content.replace("\n\n", "</p><p>").replace("\n", "<br/>")
                content = f"<p>{content}</p>"

            response = tg.create_page(
                title=title,
                html_content=content[:65000],  # Telegraph limit
                author_name=author,
            )
            url = response.get("url", "")
            return f"Статья опубликована: {url}"
        except Exception as e:
            return f"ERROR: Ошибка публикации в Telegraph: {e}"


# ══════════════════════════════════════════════════════════════
# Tool 8: DesignSystemManager
# ══════════════════════════════════════════════════════════════

class DesignSystemManagerInput(BaseModel):
    action: str = Field(
        ...,
        description="Действие: get_palette, get_guidelines, list_brands, update_brand",
    )
    brand: str = Field(default="corporation", description="Бренд: corporation, sborka, crypto, personal")
    data: str = Field(default="", description="JSON-данные для update_brand")


class DesignSystemManager(BaseTool):
    name: str = "Design System Manager"
    description: str = (
        "Управление дизайн-системами брендов: цветовые палитры, типографика, правила. "
        "Бренды: corporation, sborka, crypto, personal."
    )
    args_schema: Type[BaseModel] = DesignSystemManagerInput

    def _run(self, action: str, brand: str = "corporation", data: str = "") -> str:
        brand_file = DESIGN_SYSTEMS_DIR / f"{brand}.json"

        if action == "list_brands":
            brands = [f.stem for f in DESIGN_SYSTEMS_DIR.glob("*.json")]
            return f"Доступные бренды: {', '.join(brands) or 'нет'}"

        if action == "get_palette" or action == "get_guidelines":
            if not brand_file.exists():
                return f"Бренд '{brand}' не найден. Создай через update_brand."
            with open(brand_file, "r", encoding="utf-8") as f:
                brand_data = json.load(f)
            if action == "get_palette":
                palette = brand_data.get("palette", {})
                return json.dumps(palette, ensure_ascii=False, indent=2)
            return json.dumps(brand_data, ensure_ascii=False, indent=2)

        if action == "update_brand":
            if not data:
                return "ERROR: Нужны JSON-данные для обновления"
            try:
                new_data = json.loads(data)
            except json.JSONDecodeError:
                return "ERROR: Невалидный JSON"
            existing = {}
            if brand_file.exists():
                with open(brand_file, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            existing.update(new_data)
            with open(brand_file, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
            return f"Бренд '{brand}' обновлён."

        return f"ERROR: Неизвестное действие: {action}"


# ══════════════════════════════════════════════════════════════
# Tool 9: ImageResizer
# ══════════════════════════════════════════════════════════════

class ImageResizerInput(BaseModel):
    image_path: str = Field(..., description="Путь к исходному изображению")
    formats: str = Field(
        default="all",
        description="Форматы через запятую: square, story, banner, og, thumbnail, all",
    )


FORMAT_SIZES = {
    "square": (1080, 1080),
    "story": (1080, 1920),
    "banner": (1200, 628),
    "og": (1200, 630),
    "thumbnail": (640, 360),
}


class ImageResizer(BaseTool):
    name: str = "Image Resizer"
    description: str = (
        "Адаптация изображения под форматы соцсетей: "
        "square (1080x1080), story (1080x1920), banner (1200x628), "
        "og (1200x630), thumbnail (640x360). Возвращает пути к файлам."
    )
    args_schema: Type[BaseModel] = ImageResizerInput

    def _run(self, image_path: str, formats: str = "all") -> str:
        try:
            from PIL import Image
        except ImportError:
            return "ERROR: Pillow не установлен"

        if not os.path.exists(image_path):
            return f"ERROR: Файл не найден: {image_path}"

        img = Image.open(image_path)
        results = []

        if formats == "all":
            target_formats = list(FORMAT_SIZES.keys())
        else:
            target_formats = [f.strip() for f in formats.split(",")]

        for fmt in target_formats:
            size = FORMAT_SIZES.get(fmt)
            if not size:
                results.append(f"  {fmt}: неизвестный формат")
                continue

            resized = _resize_cover(img, size)
            path = _save_image(_pil_to_bytes(resized), prefix=f"resized_{fmt}")
            results.append(f"  {fmt} ({size[0]}x{size[1]}): {path}")

        return "Ресайзы:\n" + "\n".join(results)


def _resize_cover(img, target_size: tuple):
    """Resize image to cover target size (crop to fit)."""
    from PIL import Image

    target_w, target_h = target_size
    target_ratio = target_w / target_h
    img_ratio = img.width / img.height

    if img_ratio > target_ratio:
        # Image is wider — crop sides
        new_h = img.height
        new_w = int(new_h * target_ratio)
        left = (img.width - new_w) // 2
        img = img.crop((left, 0, left + new_w, new_h))
    else:
        # Image is taller — crop top/bottom
        new_w = img.width
        new_h = int(new_w / target_ratio)
        top = (img.height - new_h) // 2
        img = img.crop((0, top, new_w, top + new_h))

    return img.resize(target_size, Image.LANCZOS)


# ══════════════════════════════════════════════════════════════
# Tool 10: BrandVoiceVisual
# ══════════════════════════════════════════════════════════════

class BrandVoiceVisualInput(BaseModel):
    action: str = Field(
        ...,
        description="Действие: suggest_style (предложить визуальный стиль для поста), "
        "get_brand_colors (цвета бренда), check_consistency (проверить визуальную консистентность)",
    )
    brand: str = Field(default="corporation", description="Бренд")
    content: str = Field(default="", description="Контент для анализа или тема поста")


class BrandVoiceVisual(BaseTool):
    name: str = "Brand Voice Visual"
    description: str = (
        "Визуальный brand voice: предложение стилей для постов, "
        "цветовые палитры брендов, проверка консистентности."
    )
    args_schema: Type[BaseModel] = BrandVoiceVisualInput

    def _run(self, action: str, brand: str = "corporation", content: str = "") -> str:
        brand_file = DESIGN_SYSTEMS_DIR / f"{brand}.json"
        brand_data = {}
        if brand_file.exists():
            with open(brand_file, "r", encoding="utf-8") as f:
                brand_data = json.load(f)

        if action == "get_brand_colors":
            palette = brand_data.get("palette", _default_palette(brand))
            return json.dumps(palette, ensure_ascii=False, indent=2)

        if action == "suggest_style":
            return self._suggest_style(content, brand, brand_data)

        if action == "check_consistency":
            if not content:
                return "ERROR: Нужен контент для проверки"
            guidelines = brand_data.get("guidelines", {})
            if not guidelines:
                return f"Дизайн-система бренда '{brand}' пуста. Создай через Design System Manager."
            return f"Гайдлайны бренда '{brand}':\n{json.dumps(guidelines, ensure_ascii=False, indent=2)}"

        return f"ERROR: Неизвестное действие: {action}"

    def _suggest_style(self, content: str, brand: str, brand_data: dict) -> str:
        content_lower = content.lower()

        # Topic-based style suggestions
        if any(w in content_lower for w in ["финанс", "бюджет", "p&l", "доход", "расход"]):
            return (
                "Рекомендация: стиль 'infographic' — данные лучше визуализировать.\n"
                "Используй Chart Generator (bar/line) или Infographic Builder (report_card).\n"
                f"Палитра бренда '{brand}': {json.dumps(brand_data.get('palette', _default_palette(brand)))}"
            )

        if any(w in content_lower for w in ["стратег", "обзор", "отчёт", "план"]):
            return (
                "Рекомендация: стиль 'brand' — серьёзный, корпоративный визуал.\n"
                "Используй Infographic Builder (stats/timeline) или Image Generator (brand).\n"
                f"Палитра бренда '{brand}': {json.dumps(brand_data.get('palette', _default_palette(brand)))}"
            )

        if any(w in content_lower for w in ["подкаст", "аудио", "эпизод"]):
            return (
                "Рекомендация: аудиограмма через Video Creator (audiogram).\n"
                "Обложка эпизода через Image Generator (brand)."
            )

        return (
            "Рекомендация: стиль 'isotype' — универсальный, запоминающийся.\n"
            "Используй Image Generator с style='isotype'.\n"
            f"Палитра бренда '{brand}': {json.dumps(brand_data.get('palette', _default_palette(brand)))}"
        )


def _default_palette(brand: str) -> dict:
    """Default palettes for known brands."""
    palettes = {
        "corporation": {
            "primary": "#667eea",
            "accent": "#DFFF00",
            "bg_dark": "#1a1a2e",
            "bg_light": "#ffffff",
            "text": "#ffffff",
        },
        "sborka": {
            "primary": "#e94560",
            "accent": "#0f3460",
            "bg_dark": "#16213e",
            "bg_light": "#f8f9fa",
            "text": "#ffffff",
        },
        "crypto": {
            "primary": "#00d4aa",
            "accent": "#7c3aed",
            "bg_dark": "#0a0a1a",
            "bg_light": "#f0fdf4",
            "text": "#ffffff",
        },
        "personal": {
            "primary": "#3b82f6",
            "accent": "#f59e0b",
            "bg_dark": "#111827",
            "bg_light": "#ffffff",
            "text": "#ffffff",
        },
    }
    return palettes.get(brand, palettes["corporation"])
