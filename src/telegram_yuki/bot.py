"""Telegram bot entry point — Юки SMM bot."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from ..telegram.bot import AuthMiddleware
from ..telegram.bridge import AgentBridge
from .config import YukiTelegramConfig
from .handlers import commands, messages, callbacks

logger = logging.getLogger(__name__)


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    config = YukiTelegramConfig.from_env()
    logger.info(f"Yuki Config: token={'set' if config.bot_token else 'EMPTY'}, allowed_ids={config.allowed_user_ids}")
    if not config.bot_token:
        logger.error("TELEGRAM_YUKI_BOT_TOKEN not set — Yuki bot not starting")
        return

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=None),
    )
    dp = Dispatcher()

    # Auth middleware
    dp.message.middleware(AuthMiddleware(config.allowed_user_ids))

    # Register handlers (commands first, callbacks, catch-all text last)
    dp.include_router(commands.router)
    dp.include_router(callbacks.router)
    dp.include_router(messages.router)

    # Pre-initialize corporation to avoid cold start on first message
    logger.info("Pre-initializing corporation (agents + ONNX embedder)...")
    try:
        await asyncio.to_thread(lambda: AgentBridge._get_corp())
        logger.info("Corporation pre-initialized and ready")
    except Exception as e:
        logger.error(f"Corporation pre-init failed: {e} — will retry on first message")

    logger.info("Юки SMM Telegram bot starting...")

    try:
        await dp.start_polling(bot)
    finally:
        pass


if __name__ == "__main__":
    asyncio.run(main())
