"""APScheduler jobs for proactive messages from Маттиас."""

import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .bridge import AgentBridge
from .config import TelegramConfig
from .formatters import format_for_telegram

logger = logging.getLogger(__name__)


def setup_scheduler(bot: Bot, config: TelegramConfig) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    if not config.allowed_user_ids:
        logger.warning("No allowed users — scheduler jobs skipped")
        return scheduler

    chat_id = config.allowed_user_ids[0]

    # 1) Weekly financial summary (Monday 9:00 UTC)
    async def weekly_summary():
        try:
            report = await AgentBridge.run_financial_report()
            for chunk in format_for_telegram(report):
                await bot.send_message(chat_id, chunk)
        except Exception as e:
            logger.error(f"Weekly summary failed: {e}")
            await bot.send_message(
                chat_id,
                f"Маттиас: Не удалось подготовить отчёт. Ошибка: {str(e)[:200]}",
            )

    scheduler.add_job(
        weekly_summary,
        CronTrigger(
            day_of_week=config.weekly_summary_day,
            hour=config.weekly_summary_hour,
        ),
        id="weekly_summary",
        replace_existing=True,
    )

    # 2) Screenshot reminder (Friday 10:00 UTC)
    async def screenshot_reminder():
        await bot.send_message(
            chat_id,
            "Маттиас напоминает:\n\n"
            "Тим, для финансового отчёта мне нужны актуальные данные:\n\n"
            "1. Скриншот баланса TBC Bank (TBC Online)\n"
            "2. Скриншот баланса Telegram @wallet (вкладка Crypto)\n\n"
            "Просто пришли фото в этот чат — я автоматически распознаю данные.",
        )

    scheduler.add_job(
        screenshot_reminder,
        CronTrigger(
            day_of_week=config.screenshot_reminder_day,
            hour=config.screenshot_reminder_hour,
        ),
        id="screenshot_reminder",
        replace_existing=True,
    )

    # 3) Daily anomaly check (18:00 UTC)
    async def anomaly_check():
        try:
            report = await AgentBridge.send_to_agent(
                message=(
                    "Проведи быструю проверку портфеля на аномалии. "
                    "Используй full_portfolio. "
                    "Если всё в норме — ответь ТОЛЬКО: 'Аномалий нет'. "
                    "Если есть аномалии (>$1000, резкие изменения) — дай алерт."
                ),
                agent_name="accountant",
            )
            if "аномалий нет" not in report.lower():
                await bot.send_message(
                    chat_id,
                    f"Финансовый алерт от Маттиаса:\n\n{report}",
                )
        except Exception as e:
            logger.error(f"Anomaly check failed: {e}")

    scheduler.add_job(
        anomaly_check,
        CronTrigger(hour=config.anomaly_check_hour),
        id="anomaly_check",
        replace_existing=True,
    )

    logger.info(
        f"Scheduler configured: summary={config.weekly_summary_day} {config.weekly_summary_hour}:00, "
        f"reminder={config.screenshot_reminder_day} {config.screenshot_reminder_hour}:00, "
        f"anomaly=daily {config.anomaly_check_hour}:00"
    )

    return scheduler
