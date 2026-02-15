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

    sent = []
    for path in paths:
        if not os.path.isfile(path):
            logger.warning(f"Media path in response but file missing: {path}")
            continue
        ext = _get_extension(path)
        try:
            media = FSInputFile(path)
            if ext in _VIDEO_EXTENSIONS:
                await bot.send_video(chat_id, video=media)
                sent.append(path)
                logger.info(f"Sent video to chat {chat_id}: {path}")
            elif ext in _IMAGE_EXTENSIONS:
                await bot.send_photo(chat_id, photo=media)
                sent.append(path)
                logger.info(f"Sent image to chat {chat_id}: {path}")
        except Exception as e:
            logger.warning(f"Failed to send media {path}: {e}")

    for path in sent:
        ext = _get_extension(path)
        if ext in _VIDEO_EXTENSIONS:
            text = text.replace(path, "[🎬 видео отправлено выше]")
        else:
            text = text.replace(path, "[📷 отправлено выше]")

    return text
