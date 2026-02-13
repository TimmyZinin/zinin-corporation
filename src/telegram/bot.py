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
        logger.info(f"AuthMiddleware: allowed_ids={allowed_ids}")

    async def __call__(self, handler, event: Message, data: dict):
        if not self.allowed_ids:
            logger.debug("AuthMiddleware: no whitelist, allowing all")
            return await handler(event, data)
        if hasattr(event, "from_user") and event.from_user:
            uid = event.from_user.id
            if uid in self.allowed_ids:
                return await handler(event, data)
            else:
                logger.warning(f"AuthMiddleware: blocked user {uid}")
        return None


def _detach_router(router):
    """Detach a router from its parent so it can be re-included."""
    if hasattr(router, 'parent_router') and router.parent_router is not None:
        # Remove from parent's sub_routers list
        parent = router.parent_router
        if hasattr(parent, '_sub_routers'):
            try:
                parent._sub_routers.remove(router)
            except (ValueError, AttributeError):
                pass
        router.parent_router = None


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    config = TelegramConfig.from_env()
    logger.info(f"Config: token={'set' if config.bot_token else 'EMPTY'}, allowed_ids={config.allowed_user_ids}")
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

    # Detach routers from any previous dispatcher (needed for retry)
    _detach_router(commands.router)
    _detach_router(messages.router)

    # Register handlers (order matters: commands first, catch-all last)
    dp.include_router(commands.router)

    # Photo handler (imported lazily to avoid issues if vision deps missing)
    try:
        from .handlers import photos
        _detach_router(photos.router)
        dp.include_router(photos.router)
    except ImportError as e:
        logger.warning(f"Photo handler not available: {e}")

    # Document handler (CSV statements)
    from .handlers import documents
    _detach_router(documents.router)
    dp.include_router(documents.router)

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

    # Force-disconnect any previous polling session
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        logger.warning(f"delete_webhook failed: {e}")

    logger.info("Маттиас Telegram bot starting polling...")

    try:
        await dp.start_polling(bot, drop_pending_updates=True)
    finally:
        if scheduler:
            scheduler.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(main())
