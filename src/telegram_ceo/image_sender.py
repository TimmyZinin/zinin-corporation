"""Extract image file paths from agent responses and send via Telegram."""

import logging
import os
import re

_IMAGE_PATH_RE = re.compile(
    r"((?:/data|/tmp)[/\w\-_.]+\.(?:png|jpg|jpeg|gif|webp))",
    re.IGNORECASE,
)

logger = logging.getLogger(__name__)


def extract_image_paths(text: str) -> list[str]:
    """Find local image file paths in agent response text."""
    return _IMAGE_PATH_RE.findall(text)


async def send_images_from_response(bot, chat_id: int, text: str) -> str:
    """Extract file paths from agent response, send as photos, clean up text.

    Returns the text with sent file paths replaced by a marker.
    """
    from aiogram.types import FSInputFile

    paths = extract_image_paths(text)
    if not paths:
        return text

    sent = []
    for path in paths:
        if not os.path.isfile(path):
            logger.warning(f"Image path in response but file missing: {path}")
            continue
        try:
            photo = FSInputFile(path)
            await bot.send_photo(chat_id, photo=photo)
            sent.append(path)
            logger.info(f"Sent image to chat {chat_id}: {path}")
        except Exception as e:
            logger.warning(f"Failed to send image {path}: {e}")

    for path in sent:
        text = text.replace(path, "[📷 отправлено выше]")

    return text
