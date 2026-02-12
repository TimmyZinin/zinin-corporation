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

    # 1) Daily morning briefing (no LLM — instant) — enhanced with Task Pool + alerts
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

            # Task Pool summary
            try:
                from ..task_pool import get_all_tasks, TaskStatus
                all_tasks = get_all_tasks()
                todo = sum(1 for t in all_tasks if t.status == TaskStatus.TODO)
                in_prog = sum(1 for t in all_tasks if t.status == TaskStatus.IN_PROGRESS)
                blocked = sum(1 for t in all_tasks if t.status == TaskStatus.BLOCKED)
                lines.append(f"\n📋 Task Pool: TODO={todo}, In Progress={in_prog}, Blocked={blocked}")
            except Exception:
                pass

            # Rate limit alerts overnight
            try:
                from ..rate_monitor import get_rate_alerts
                alerts = get_rate_alerts(hours=12)
                if alerts:
                    lines.append(f"\n⚠️ Rate алертов за ночь: {len(alerts)}")
            except Exception:
                pass

            await bot.send_message(chat_id, "\n".join(lines))
        except Exception as e:
            logger.error(f"Morning briefing failed: {e}")

    scheduler.add_job(
        morning_briefing,
        CronTrigger(hour=config.morning_briefing_hour),
        id="ceo_morning_briefing",
        replace_existing=True,
    )

    # 2) Weekly full corporation report (heavy — all agents via LLM)
    async def weekly_review():
        try:
            report = await AgentBridge.run_corporation_report()
            for chunk in format_for_telegram(report):
                await bot.send_message(chat_id, chunk)
        except Exception as e:
            logger.error(f"Weekly corporation report failed: {e}")
            await bot.send_message(
                chat_id,
                f"Алексей: Не удалось подготовить еженедельный отчёт. Ошибка: {str(e)[:200]}",
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

    # 3) API health check every 30 minutes — with CTO diagnostics + action buttons
    async def api_health_check():
        try:
            from ..tools.tech_tools import (
                run_api_health_check, _check_single_api, _API_REGISTRY, _call_llm_tech,
            )
            from .handlers.callbacks import _load_diagnostics, _save_diagnostics
            from .keyboards import diagnostic_keyboard
            import asyncio
            from datetime import datetime, timedelta

            result = await asyncio.to_thread(run_api_health_check)

            # If healthy — silent, no spam
            if result["overall"] == "healthy":
                logger.info("API health check: all healthy")
                return

            # Collect detailed per-API results for failures
            failed_api_keys = []
            detailed_results = {}
            for api_key in _API_REGISTRY:
                check = await asyncio.to_thread(_check_single_api, api_key)
                if not check.get("ok") and check.get("configured", True):
                    failed_api_keys.append(api_key)
                    detailed_results[api_key] = check

            if not failed_api_keys:
                logger.info("API health check: failures are unconfigured APIs only — skipping")
                return

            # Cooldown: only call LLM if last_analysis > 15 min ago
            diag_data = _load_diagnostics()
            last_analysis_str = diag_data.get("last_analysis")
            should_run_llm = True
            if last_analysis_str:
                try:
                    last_time = datetime.fromisoformat(last_analysis_str)
                    if datetime.now() - last_time < timedelta(minutes=15):
                        should_run_llm = False
                except (ValueError, TypeError):
                    pass

            now = datetime.now()
            diag_id = f"diag_{now.strftime('%Y%m%d_%H%M')}"

            # CTO LLM analysis
            analysis = None
            if should_run_llm:
                api_details = []
                for api_key in failed_api_keys:
                    api_info = _API_REGISTRY.get(api_key, {})
                    r = detailed_results[api_key]
                    api_details.append(
                        f"- {api_info.get('name', api_key)} ({api_info.get('category', '?')}):\n"
                        f"  Ошибка: {r.get('error', '?')}\n"
                        f"  HTTP код: {r.get('code', 'N/A')}\n"
                        f"  Время ответа: {r.get('ms', 0)}ms\n"
                        f"  Env vars: {', '.join(api_info.get('env_vars', []))}"
                    )

                prompt = (
                    f"Обнаружены сбои API:\n\n"
                    f"{''.join(api_details)}\n\n"
                    f"Для каждого API укажи:\n"
                    f"1. Вероятную причину (1 предложение)\n"
                    f"2. Конкретное решение (1-2 предложения)\n"
                    f"Будь кратким и практичным."
                )
                system = (
                    "Ты — Мартин Эчеверрия, CTO Zinin Corp. "
                    "Анализируй сбои API и предлагай конкретные решения на русском языке. "
                    "Максимум 400 слов."
                )

                try:
                    analysis = await asyncio.to_thread(
                        _call_llm_tech, prompt, system, 800
                    )
                except Exception as e:
                    logger.warning(f"CTO LLM analysis failed: {e}")

                if analysis:
                    diag_data["last_analysis"] = now.isoformat()

            if not analysis:
                analysis = (
                    "Автоматический анализ временно недоступен. "
                    "Нажмите «Подробнее» для просмотра деталей по каждому API."
                )

            # Save diagnostic record
            diagnostic = {
                "id": diag_id,
                "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                "failed_apis": failed_api_keys,
                "results": detailed_results,
                "analysis": analysis,
                "status": "pending",
                "recheck_count": 0,
                "last_recheck": None,
            }
            diag_data["diagnostics"].append(diagnostic)
            diag_data["stats"]["total"] = diag_data["stats"].get("total", 0) + 1
            _save_diagnostics(diag_data)

            # Build message
            severity = "🚨" if result["overall"] == "critical" else "⚠️"
            failed_list = "\n".join(
                f"  ❌ {_API_REGISTRY.get(k, {}).get('name', k)}"
                for k in failed_api_keys[:5]
            )
            if len(failed_api_keys) > 5:
                failed_list += f"\n  ... и ещё {len(failed_api_keys) - 5}"

            analysis_preview = analysis[:400] + "..." if len(analysis) > 400 else analysis

            text = (
                f"{severity} API: {result['total_fail']} из "
                f"{result['total_ok'] + result['total_fail']} с проблемами\n\n"
                f"Мартин (CTO):\n{failed_list}\n\n"
                f"💡 Анализ:\n{analysis_preview}"
            )
            if len(text) > 4000:
                text = text[:4000] + "..."

            await bot.send_message(
                chat_id, text, reply_markup=diagnostic_keyboard(diag_id),
            )

            logger.info(
                f"API diagnostic {diag_id}: {result['overall']} "
                f"({result['total_fail']} fail), LLM={'yes' if should_run_llm and analysis else 'no'}"
            )
        except Exception as e:
            logger.error(f"API health check failed: {e}", exc_info=True)

    scheduler.add_job(
        api_health_check,
        "interval",
        minutes=30,
        id="cto_api_health_check",
        replace_existing=True,
    )

    # 4) CTO improvement proposals — 4 times/day
    async def cto_improvement_check():
        try:
            result = await AgentBridge.run_cto_proposal()
            if "error" in result:
                logger.warning(f"CTO proposal generation failed: {result['error']}")
                return

            # Parse latest proposal from storage
            from ..tools.improvement_advisor import _load_proposals, _AGENT_LABELS
            from .keyboards import proposal_keyboard

            data = _load_proposals()
            proposals = data.get("proposals", [])
            if not proposals:
                logger.info("CTO improvement check: no proposals generated")
                return

            latest = proposals[-1]
            if latest.get("status") != "pending":
                logger.info("CTO improvement check: latest proposal already reviewed")
                return

            target = _AGENT_LABELS.get(
                latest.get("target_agent", ""), latest.get("target_agent", "")
            )
            type_labels = {
                "prompt": "📝 Промпт",
                "tool": "🔧 Инструмент",
                "model_tier": "🧠 Модель",
            }
            ptype = type_labels.get(
                latest.get("proposal_type", ""), latest.get("proposal_type", "?")
            )

            text = (
                f"💡 Предложение от Мартина (CTO):\n\n"
                f"📋 {latest.get('title', '?')}\n"
                f"🎯 Агент: {target}\n"
                f"📊 Тип: {ptype}\n"
                f"📈 Уверенность: {latest.get('confidence_score', 0):.0%}\n\n"
                f"💡 {latest.get('description', '—')[:500]}"
            )

            if len(text) > 4000:
                text = text[:4000] + "..."

            await bot.send_message(
                chat_id,
                text,
                reply_markup=proposal_keyboard(latest["id"]),
            )
            logger.info(f"CTO proposal sent: {latest['id']} — {latest.get('title', '?')}")

        except Exception as e:
            logger.error(f"CTO improvement check failed: {e}", exc_info=True)

    for hour in [9, 13, 17, 21]:
        scheduler.add_job(
            cto_improvement_check,
            CronTrigger(hour=hour, minute=30),
            id=f"cto_improvement_{hour:02d}",
            replace_existing=True,
        )

    # 5) Task Pool Archiver — nightly at 01:00
    async def archive_daily():
        try:
            from ..task_pool import archive_done_tasks
            count = archive_done_tasks(keep_recent_days=1)
            if count > 0:
                await bot.send_message(
                    chat_id, f"📦 Архивировано {count} завершённых задач"
                )
                logger.info(f"Task Pool archive: {count} tasks archived")
            else:
                logger.info("Task Pool archive: nothing to archive")
        except Exception as e:
            logger.error(f"Task Pool archive failed: {e}")

    scheduler.add_job(
        archive_daily,
        CronTrigger(hour=1),
        id="task_pool_archive",
        replace_existing=True,
    )

    # 6) CTO Orphan Task Patrol — daily at 10:00
    async def orphan_patrol():
        try:
            from ..task_pool import get_stale_tasks, format_stale_report
            stale = get_stale_tasks(stale_days=3)
            if not stale:
                logger.info("Orphan patrol: no stale tasks found")
                return
            report = format_stale_report(stale)
            await bot.send_message(chat_id, report)
            logger.info(f"Orphan patrol: {len(stale)} stale tasks reported")
        except Exception as e:
            logger.error(f"Orphan patrol failed: {e}")

    scheduler.add_job(
        orphan_patrol,
        CronTrigger(hour=10),
        id="cto_orphan_patrol",
        replace_existing=True,
    )

    # 7) Daily analytics report at 22:00
    async def daily_analytics():
        try:
            from ..analytics import format_analytics_report
            report = format_analytics_report(hours=24)
            await bot.send_message(chat_id, report)
            logger.info("Daily analytics report sent")
        except Exception as e:
            logger.error(f"Daily analytics failed: {e}")

    scheduler.add_job(
        daily_analytics,
        CronTrigger(hour=22),
        id="daily_analytics",
        replace_existing=True,
    )

    # 8) Evening report at 21:00
    async def evening_report():
        try:
            from ..analytics import get_agent_activity_report, get_cost_estimates
            from ...task_pool import get_all_tasks, TaskStatus

            lines = ["Добрый вечер, Тим. Итоги дня:\n"]

            # Agent activity
            lines.append(get_agent_activity_report(hours=12))

            # Task Pool summary
            try:
                all_tasks = get_all_tasks()
                active = [t for t in all_tasks if t.status != TaskStatus.DONE]
                done_today = sum(
                    1 for t in all_tasks if t.status == TaskStatus.DONE
                )
                lines.append(f"\n📋 Task Pool: {len(active)} активных, {done_today} выполненных")
            except Exception:
                pass

            # Cost
            lines.append(f"\n{get_cost_estimates(hours=12)}")

            await bot.send_message(chat_id, "\n".join(lines))
            logger.info("Evening report sent")
        except Exception as e:
            logger.error(f"Evening report failed: {e}")

    scheduler.add_job(
        evening_report,
        CronTrigger(hour=21),
        id="evening_report",
        replace_existing=True,
    )

    # 9) Weekly digest — Sunday 20:00
    async def weekly_digest():
        try:
            from ..analytics import format_weekly_digest
            digest = format_weekly_digest()
            await bot.send_message(chat_id, digest)
            logger.info("Weekly digest sent")
        except Exception as e:
            logger.error(f"Weekly digest failed: {e}")

    scheduler.add_job(
        weekly_digest,
        CronTrigger(day_of_week="sun", hour=20),
        id="weekly_digest",
        replace_existing=True,
    )

    # 10) Enhanced morning briefing: add Task Pool + rate alerts
    # (enhancement is inside the existing morning_briefing function above)

    logger.info(
        f"CEO scheduler: briefing=daily {config.morning_briefing_hour}:00, "
        f"full_report={config.weekly_review_day} {config.weekly_review_hour}:00, "
        f"api_health=every 30min, "
        f"cto_improvement=4x/day (9:30, 13:30, 17:30, 21:30), "
        f"archive=daily 01:00, orphan_patrol=daily 10:00, "
        f"analytics=daily 22:00, evening=daily 21:00, digest=Sun 20:00"
    )

    return scheduler
