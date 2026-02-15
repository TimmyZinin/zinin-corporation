"""Extract media file paths from agent responses and send via Telegram."""

import logging
import os
import re

_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
_VIDEO_EXTENSIONS = {"mp4", "mov", "avi", "mkv"}
_ALL_EXTENSIONS = _IMAGE_EXTENSIONS | _VIDEO_EXTENSIONS

_MEDIA_PATH_RE = re.compile(
    r"((?:/(?:app/)?data|/tmp)[/\w\-_.]+\.(?:" + "|".join(_ALL_EXTENSIONS) + r"))",
    re.IGNORECASE,
)

# Backward-compatible alias
_IMAGE_PATH_RE = _MEDIA_PATH_RE

logger = logging.getLogger(__name__)


def _normalize_path(path: str) -> str:
    """Normalize media path — handle /data/ vs /app/data/ Docker mismatch.

    CrewAI agents sometimes strip the /app/ prefix from paths in their responses.
    This function tries the original path first, then /app/ prefixed version.
    """
    if os.path.isfile(path):
        return path
    # Agent returned /data/... but file is at /app/data/...
    if path.startswith("/data/") and not path.startswith("/app/"):
        alt = "/app" + path
        if os.path.isfile(alt):
            return alt
    # Agent returned /tmp/... but file is at /app/tmp/...
    if path.startswith("/tmp/") and not path.startswith("/app/"):
        alt = "/app" + path
        if os.path.isfile(alt):
            return alt
    return path


def _get_extension(path: str) -> str:
    """Get lowercase file extension without dot."""
    return os.path.splitext(path)[1].lstrip(".").lower()


def extract_image_paths(text: str) -> list[str]:
    """Find local image file paths in agent response text."""
    return [p for p in _MEDIA_PATH_RE.findall(text) if _get_extension(p) in _IMAGE_EXTENSIONS]


def extract_video_paths(text: str) -> list[str]:
    """Find local video file paths in agent response text."""
    return [p for p in _MEDIA_PATH_RE.findall(text) if _get_extension(p) in _VIDEO_EXTENSIONS]


def extract_media_paths(text: str) -> list[str]:
    """Find all media file paths (images + videos) in agent response text."""
    return _MEDIA_PATH_RE.findall(text)


async def send_images_from_response(bot, chat_id: int, text: str) -> str:
    """Extract media paths from agent response, send as photos/videos, clean up text.

    Returns the text with sent file paths replaced by a marker.
    """
    from aiogram.types import FSInputFile

    paths = extract_media_paths(text)
    if not paths:
        return text

    sent = []  # (original_path, resolved_path) tuples
    for path in paths:
        resolved = _normalize_path(path)
        if not os.path.isfile(resolved):
            logger.warning(f"Media path in response but file missing: {path}")
            continue
        if resolved != path:
            logger.info(f"Normalized media path: {path} -> {resolved}")
        ext = _get_extension(resolved)
        try:
            media = FSInputFile(resolved)
            if ext in _VIDEO_EXTENSIONS:
                await bot.send_video(chat_id, video=media)
                sent.append((path, resolved))
                logger.info(f"Sent video to chat {chat_id}: {resolved}")
            elif ext in _IMAGE_EXTENSIONS:
                await bot.send_photo(chat_id, photo=media)
                sent.append((path, resolved))
                logger.info(f"Sent image to chat {chat_id}: {resolved}")
        except Exception as e:
            logger.warning(f"Failed to send media {resolved}: {e}")

    for original_path, resolved_path in sent:
        ext = _get_extension(resolved_path)
        marker = "[🎬 видео отправлено выше]" if ext in _VIDEO_EXTENSIONS else "[📷 отправлено выше]"
        # Replace both original and resolved paths in text
        text = text.replace(original_path, marker)
        if resolved_path != original_path:
            text = text.replace(resolved_path, marker)

    return text
