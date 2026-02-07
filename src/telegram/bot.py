"""Telegram bot entry point — Маттиас CFO bot."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message
from aiogram import BaseMiddleware

from .config import TelegramConfig
from .handlers import commands, messages

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseMiddleware):
    """Allow only whitelisted Telegram user IDs."""

    def __init__(self, allowed_ids: list[int]):
        self.allowed_ids = allowed_ids

    async def __call__(self, handler, event: Message, data: dict):
        if not self.allowed_ids:
            return await handler(event, data)
        if hasattr(event, "from_user") and event.from_user:
            if event.from_user.id in self.allowed_ids:
                return await handler(event, data)
        return None


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    config = TelegramConfig.from_env()
    if not config.bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not set — bot not starting")
        return

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=None),
    )
    dp = Dispatcher()

    # Auth middleware
    dp.message.middleware(AuthMiddleware(config.allowed_user_ids))

    # Register handlers (order matters: commands first, catch-all last)
    dp.include_router(commands.router)

    # Photo handler (imported lazily to avoid issues if vision deps missing)
    try:
        from .handlers import photos
        dp.include_router(photos.router)
    except ImportError as e:
        logger.warning(f"Photo handler not available: {e}")

    dp.include_router(messages.router)  # catch-all, must be last

    # Scheduler for proactive messages
    scheduler = None
    try:
        from .scheduler import setup_scheduler
        scheduler = setup_scheduler(bot, config)
        scheduler.start()
        logger.info("Scheduler started")
    except ImportError:
        logger.warning("APScheduler not available — proactive messages disabled")

    logger.info("Маттиас Telegram bot starting...")

    try:
        await dp.start_polling(bot)
    finally:
        if scheduler:
            scheduler.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(main())
