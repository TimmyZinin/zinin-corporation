"""Telegram bot entry point — Юки SMM bot."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from ..telegram.bot import AuthMiddleware, _detach_router
from ..telegram.bridge import AgentBridge
from .config import YukiTelegramConfig
from .handlers import commands, messages, callbacks

logger = logging.getLogger(__name__)


async def _scheduler_loop(bot: Bot):
    """Background loop that checks for scheduled posts every 60 seconds."""
    from .scheduler import PostScheduler
    from .drafts import DraftManager
    from .publishers import get_publisher
    from .safety import circuit_breaker

    while True:
        try:
            await asyncio.sleep(60)
            due = PostScheduler.get_due_posts()
            for entry in due:
                post_id = entry["post_id"]
                platforms = entry.get("platforms", ["linkedin"])
                draft = DraftManager.get_draft(post_id)
                if not draft:
                    PostScheduler.mark_failed(post_id, "draft not found")
                    continue

                if circuit_breaker.is_open:
                    PostScheduler.mark_failed(post_id, "circuit breaker open")
                    continue

                results = []
                for platform_name in platforms:
                    pub = get_publisher(platform_name)
                    if not pub:
                        results.append(f"❌ {platform_name}: неизвестная платформа")
                        continue
                    try:
                        if platform_name == "telegram":
                            result = await pub.publish(
                                draft["text"], draft.get("image_path", ""), bot=bot
                            )
                        else:
                            result = await pub.publish(
                                draft["text"], draft.get("image_path", "")
                            )
                        results.append(f"✅ {pub.emoji} {pub.label}: {result[:80]}")
                        circuit_breaker.record_success()
                    except Exception as e:
                        results.append(f"❌ {pub.emoji} {pub.label}: {str(e)[:80]}")
                        circuit_breaker.record_failure()

                PostScheduler.mark_published(post_id)
                DraftManager.update_draft(post_id, status="published")

                # Auto mark_done in content calendar
                if draft.get("calendar_entry_id"):
                    try:
                        from ..content_calendar import mark_done
                        mark_done(draft["calendar_entry_id"], post_id=post_id)
                    except Exception as cal_err:
                        logger.warning(f"Failed to mark calendar done: {cal_err}")

                # Notify user about scheduled publish
                config = YukiTelegramConfig.from_env()
                for uid in config.allowed_user_ids:
                    try:
                        await bot.send_message(
                            uid,
                            f"📅 Запланированный пост опубликован!\n"
                            f"Тема: {draft.get('topic', '?')[:40]}\n\n"
                            + "\n".join(results),
                        )
                    except Exception:
                        pass

            # Periodic cleanup
            PostScheduler.cleanup_old()

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Scheduler loop error: {e}", exc_info=True)


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

    # Detach routers from any previous dispatcher (needed for retry)
    _detach_router(commands.router)
    _detach_router(callbacks.router)
    _detach_router(messages.router)

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

    # Start scheduler background task
    scheduler_task = asyncio.create_task(_scheduler_loop(bot))
    logger.info("Scheduler background task started")

    logger.info("Юки SMM Telegram bot starting...")

    try:
        await dp.start_polling(bot, drop_pending_updates=True)
    finally:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    asyncio.run(main())
