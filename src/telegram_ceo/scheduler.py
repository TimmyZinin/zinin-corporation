"""APScheduler jobs for proactive messages from CEO Алексей."""

import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..telegram.bridge import AgentBridge
from ..telegram.formatters import format_for_telegram
from ..activity_tracker import get_all_statuses, get_agent_task_count
from .config import CeoTelegramConfig

logger = logging.getLogger(__name__)


def setup_ceo_scheduler(bot: Bot, config: CeoTelegramConfig) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    if not config.allowed_user_ids:
        logger.warning("No allowed users — CEO scheduler jobs skipped")
        return scheduler

    chat_id = config.allowed_user_ids[0]

    # 1) Daily morning briefing (no LLM — instant)
    async def morning_briefing():
        try:
            statuses = get_all_statuses()
            agent_labels = {
                "manager": "Алексей (CEO)",
                "accountant": "Маттиас (CFO)",
                "automator": "Мартин (CTO)",
                "smm": "Юки (SMM)",
            }
            lines = ["Доброе утро, Тим. Сводка от Алексея:\n"]
            for key, label in agent_labels.items():
                tasks = get_agent_task_count(key, hours=24)
                s = statuses.get(key, {})
                status = s.get("status", "idle")
                lines.append(f"  {label} — {status}, задач за 24ч: {tasks}")

            await bot.send_message(chat_id, "\n".join(lines))
        except Exception as e:
            logger.error(f"Morning briefing failed: {e}")

    scheduler.add_job(
        morning_briefing,
        CronTrigger(hour=config.morning_briefing_hour),
        id="ceo_morning_briefing",
        replace_existing=True,
    )

    # 2) Weekly strategic review (heavy — 3 agents via LLM)
    async def weekly_review():
        try:
            report = await AgentBridge.run_strategic_review()
            for chunk in format_for_telegram(report):
                await bot.send_message(chat_id, chunk)
        except Exception as e:
            logger.error(f"Weekly strategic review failed: {e}")
            await bot.send_message(
                chat_id,
                f"Алексей: Не удалось подготовить стратобзор. Ошибка: {str(e)[:200]}",
            )

    scheduler.add_job(
        weekly_review,
        CronTrigger(
            day_of_week=config.weekly_review_day,
            hour=config.weekly_review_hour,
        ),
        id="ceo_weekly_review",
        replace_existing=True,
    )

    # 3) API health check every 30 minutes
    async def api_health_check():
        try:
            from ..tools.tech_tools import run_api_health_check
            import asyncio

            result = await asyncio.to_thread(run_api_health_check)
            if result["overall"] == "critical":
                failed = "\n".join(f"  ❌ {api}" for api in result["failed_apis"])
                await bot.send_message(
                    chat_id,
                    f"🚨 КРИТИЧЕСКИЙ СБОЙ API!\n\n"
                    f"Мартин (CTO): обнаружены проблемы с {result['total_fail']} API:\n"
                    f"{failed}\n\n"
                    f"Работают: {result['total_ok']}, не работают: {result['total_fail']}",
                )
            elif result["overall"] == "degraded" and result["total_fail"] > 0:
                failed = "\n".join(f"  ⚠️ {api}" for api in result["failed_apis"])
                await bot.send_message(
                    chat_id,
                    f"⚠️ API Health: деградация\n\n"
                    f"Мартин (CTO): {result['total_fail']} API с проблемами:\n"
                    f"{failed}",
                )
            # If healthy — silent, no spam
            logger.info(
                f"API health check: {result['overall']} "
                f"(OK:{result['total_ok']} Fail:{result['total_fail']})"
            )
        except Exception as e:
            logger.error(f"API health check failed: {e}")

    scheduler.add_job(
        api_health_check,
        "interval",
        minutes=30,
        id="cto_api_health_check",
        replace_existing=True,
    )

    logger.info(
        f"CEO scheduler: briefing=daily {config.morning_briefing_hour}:00, "
        f"review={config.weekly_review_day} {config.weekly_review_hour}:00, "
        f"api_health=every 30min"
    )

    return scheduler
