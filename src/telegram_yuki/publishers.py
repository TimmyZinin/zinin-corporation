"""Multi-platform publisher registry — LinkedIn, Telegram, Threads, extensible."""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class BasePublisher:
    """Base class for all platform publishers."""

    name: str = "unknown"
    label: str = "Unknown"
    emoji: str = "📤"

    async def publish(self, text: str, image_path: str = "") -> str:
        """Publish content. Returns status message."""
        raise NotImplementedError

    async def check_status(self) -> str:
        """Check if publisher is configured and ready."""
        raise NotImplementedError

    @property
    def is_configured(self) -> bool:
        """Quick check without async."""
        return False


class LinkedInPublisher(BasePublisher):
    name = "linkedin"
    label = "LinkedIn"
    emoji = "💼"

    async def publish(self, text: str, image_path: str = "") -> str:
        from ..telegram.bridge import AgentBridge
        return await AgentBridge.run_linkedin_publish(text=text, image_path=image_path)

    async def check_status(self) -> str:
        from ..telegram.bridge import AgentBridge
        return await AgentBridge.run_linkedin_status()

    @property
    def is_configured(self) -> bool:
        return bool(os.getenv("LINKEDIN_ACCESS_TOKEN"))


class TelegramChannelPublisher(BasePublisher):
    """Publish to a Telegram channel via bot."""

    name = "telegram"
    label = "Telegram канал"
    emoji = "📱"

    def __init__(self):
        self.channel_id = os.getenv("TELEGRAM_YUKI_CHANNEL_ID", "")

    async def publish(self, text: str, image_path: str = "", bot=None) -> str:
        if not self.channel_id:
            return "TELEGRAM_YUKI_CHANNEL_ID не настроен"
        if not bot:
            return "Bot instance не передан"

        try:
            if image_path and os.path.exists(image_path):
                from aiogram.types import FSInputFile
                photo = FSInputFile(image_path)
                msg = await bot.send_photo(
                    chat_id=self.channel_id,
                    photo=photo,
                    caption=text[:1024],
                )
            else:
                msg = await bot.send_message(
                    chat_id=self.channel_id,
                    text=text,
                )
            return f"Опубликовано в Telegram канал (msg_id: {msg.message_id})"
        except Exception as e:
            return f"Ошибка публикации в Telegram: {e}"

    async def check_status(self) -> str:
        if not self.channel_id:
            return "TELEGRAM_YUKI_CHANNEL_ID не настроен"
        return f"Telegram канал: {self.channel_id} (настроен)"

    @property
    def is_configured(self) -> bool:
        return bool(self.channel_id)


class ThreadsPublisher(BasePublisher):
    """Threads publisher — stub, awaiting API access."""

    name = "threads"
    label = "Threads"
    emoji = "🧵"

    async def publish(self, text: str, image_path: str = "") -> str:
        # Threads API requires Instagram Business account + Meta app review
        return "Threads: публикация пока не настроена (ожидается доступ к API)"

    async def check_status(self) -> str:
        token = os.getenv("THREADS_ACCESS_TOKEN", "")
        if not token:
            return "Threads: THREADS_ACCESS_TOKEN не настроен"
        return "Threads: токен настроен (API в разработке)"

    @property
    def is_configured(self) -> bool:
        return bool(os.getenv("THREADS_ACCESS_TOKEN"))


# ── Publisher Registry ──────────────────────────────────────────────────────

_PUBLISHERS: dict[str, BasePublisher] = {}


def _init_publishers():
    global _PUBLISHERS
    if not _PUBLISHERS:
        _PUBLISHERS = {
            "linkedin": LinkedInPublisher(),
            "telegram": TelegramChannelPublisher(),
            "threads": ThreadsPublisher(),
        }


def get_publisher(name: str) -> Optional[BasePublisher]:
    """Get a publisher by name."""
    _init_publishers()
    return _PUBLISHERS.get(name)


def get_all_publishers() -> dict[str, BasePublisher]:
    """Get all registered publishers."""
    _init_publishers()
    return _PUBLISHERS


def get_configured_publishers() -> dict[str, BasePublisher]:
    """Get only publishers that have valid configuration."""
    _init_publishers()
    return {k: v for k, v in _PUBLISHERS.items() if v.is_configured}


def register_publisher(name: str, publisher: BasePublisher):
    """Register a new publisher (for future extensions)."""
    _init_publishers()
    _PUBLISHERS[name] = publisher
    logger.info(f"Registered publisher: {name} ({publisher.label})")


# ── Author / Brand routing ──────────────────────────────────────────────────

AUTHORS = {
    "kristina": {
        "label": "Кристина",
        "brands": ["sborka"],  # СБОРКА only
        "default_platforms": ["linkedin"],
    },
    "tim": {
        "label": "Тим",
        "brands": ["sborka", "personal"],  # СБОРКА + personal brand
        "default_platforms": ["linkedin"],
    },
}

BRANDS = {
    "sborka": {
        "label": "СБОРКА",
        "authors": ["kristina", "tim"],
        "signature": "СБОРКА — клуб карьерной дисциплины",
    },
    "personal": {
        "label": "Личный бренд Тима",
        "authors": ["tim"],  # only Tim
        "signature": "",
    },
}


def validate_author_brand(author: str, brand: str = "sborka") -> tuple[bool, str]:
    """Check if author can write for this brand. Returns (ok, error_msg)."""
    if author not in AUTHORS:
        return False, f"Неизвестный автор: {author}. Доступные: {', '.join(AUTHORS)}"
    if brand not in BRANDS:
        return False, f"Неизвестный бренд: {brand}. Доступные: {', '.join(BRANDS)}"
    if author not in BRANDS[brand]["authors"]:
        allowed = ", ".join(BRANDS[brand]["authors"])
        return False, f"{AUTHORS[author]['label']} не может писать для {BRANDS[brand]['label']}. Доступные авторы: {allowed}"
    return True, ""
