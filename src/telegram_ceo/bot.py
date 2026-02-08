"""Telegram bot entry point — Алексей CEO bot."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from ..telegram.bot import AuthMiddleware, _detach_router
from ..telegram.bridge import AgentBridge
from .config import CeoTelegramConfig
from .handlers import commands, messages

logger = logging.getLogger(__name__)


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    config = CeoTelegramConfig.from_env()
    logger.info(f"CEO Config: token={'set' if config.bot_token else 'EMPTY'}, allowed_ids={config.allowed_user_ids}")
    if not config.bot_token:
        logger.error("TELEGRAM_CEO_BOT_TOKEN not set — CEO bot not starting")
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

    # Register handlers (commands first, catch-all last)
    dp.include_router(commands.router)
    dp.include_router(messages.router)

    # Scheduler for proactive messages
    scheduler = None
    try:
        from .scheduler import setup_ceo_scheduler
        scheduler = setup_ceo_scheduler(bot, config)
        scheduler.start()
        logger.info("CEO scheduler started")
    except ImportError:
        logger.warning("APScheduler not available — CEO proactive messages disabled")

    # Pre-initialize corporation to avoid cold start on first message
    logger.info("Pre-initializing corporation (agents + ONNX embedder)...")
    try:
        await asyncio.to_thread(lambda: AgentBridge._get_corp())
        logger.info("Corporation pre-initialized and ready")
    except Exception as e:
        logger.error(f"Corporation pre-init failed: {e} — will retry on first message")

    logger.info("Алексей CEO Telegram bot starting...")

    try:
        await dp.start_polling(bot, drop_pending_updates=True)
    finally:
        if scheduler:
            scheduler.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(main())
