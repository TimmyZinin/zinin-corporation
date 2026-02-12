"""
📊 Zinin Corp — Analytics Module

Aggregates data from rate_monitor and activity_tracker
for Telegram reports. No LLM calls — pure data processing.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from .rate_monitor import (
    get_all_usage,
    get_rate_alerts,
    PROVIDER_LIMITS,
)
from .activity_tracker import (
    get_recent_events,
    get_all_statuses,
    get_quality_summary,
    AGENT_NAMES,
    AGENT_EMOJI,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# Cost estimates per provider (approximate, USD)
# ──────────────────────────────────────────────────────────

COST_PER_REQUEST = {
    "openrouter": 0.003,   # ~$3 per 1K requests avg
    "elevenlabs": 0.015,   # ~$15 per 1K chars
    "openai": 0.002,       # ~$2 per 1K requests avg
    "coingecko": 0.0,      # Free tier
    "groq": 0.0,           # Free tier
}


def get_token_usage_report(hours: int = 24) -> str:
    """Get text report of API call counts per provider."""
    minutes = hours * 60
    all_usage = get_all_usage(minutes=minutes)

    lines = [f"📡 API вызовы ({hours}ч):"]
    total_calls = 0
    total_failed = 0

    for provider, usage in all_usage.items():
        total = usage["total_calls"]
        if total == 0:
            continue
        total_calls += total
        total_failed += usage["failed"]
        name = PROVIDER_LIMITS.get(provider, {}).get("name", provider)
        fail_str = f" | ❌{usage['failed']}" if usage["failed"] else ""
        lat_str = f" | ~{usage['avg_latency_ms']}ms" if usage["avg_latency_ms"] else ""
        lines.append(f"  {name}: {total}{fail_str}{lat_str}")

    if total_calls == 0:
        lines.append("  Нет API-вызовов")
    else:
        lines.append(f"  Итого: {total_calls} (ошибок: {total_failed})")

    return "\n".join(lines)


def get_agent_activity_report(hours: int = 24) -> str:
    """Get text report of agent activity."""
    events = get_recent_events(hours=hours, limit=500)
    statuses = get_all_statuses()

    # Count events per agent
    agent_tasks: dict[str, int] = {}
    agent_delegations: dict[str, int] = {}
    communications = 0

    for e in events:
        etype = e.get("type")
        if etype == "task_end":
            agent = e.get("agent", "")
            agent_tasks[agent] = agent_tasks.get(agent, 0) + 1
        elif etype == "delegation":
            to_agent = e.get("to_agent", "")
            agent_delegations[to_agent] = agent_delegations.get(to_agent, 0) + 1
        elif etype == "communication":
            communications += 1

    lines = [f"👥 Активность агентов ({hours}ч):"]
    for key, name in AGENT_NAMES.items():
        emoji = AGENT_EMOJI.get(key, "")
        tasks_done = agent_tasks.get(key, 0)
        delegated = agent_delegations.get(key, 0)
        status = statuses.get(key, {}).get("status", "idle")
        status_emoji = {"working": "🟢", "idle": "⚪"}.get(status, "⚪")

        parts = [f"  {emoji} {name}: {status_emoji}{status}"]
        if tasks_done:
            parts.append(f"✅{tasks_done}")
        if delegated:
            parts.append(f"📨{delegated}")
        lines.append(" | ".join(parts))

    if communications:
        lines.append(f"  💬 Коммуникаций: {communications}")

    return "\n".join(lines)


def get_cost_estimates(hours: int = 24) -> str:
    """Get estimated cost for API usage."""
    minutes = hours * 60
    all_usage = get_all_usage(minutes=minutes)

    total_cost = 0.0
    lines = [f"💰 Оценка расходов ({hours}ч):"]

    for provider, usage in all_usage.items():
        total = usage["total_calls"]
        if total == 0:
            continue
        cost = total * COST_PER_REQUEST.get(provider, 0.001)
        total_cost += cost
        if cost > 0:
            name = PROVIDER_LIMITS.get(provider, {}).get("name", provider)
            lines.append(f"  {name}: ~${cost:.2f} ({total} запросов)")

    lines.append(f"  Итого: ~${total_cost:.2f}")
    return "\n".join(lines)


def get_alert_summary(hours: int = 24) -> str:
    """Get summary of recent rate limit alerts."""
    alerts = get_rate_alerts(hours=hours)

    if not alerts:
        return "✅ Нет алертов по лимитам"

    lines = [f"⚠️ Алерты ({len(alerts)} за {hours}ч):"]
    for a in alerts[-10:]:
        name = PROVIDER_LIMITS.get(a.provider, {}).get("name", a.provider)
        lines.append(f"  🟡 {name}: {a.pct:.0f}% ({a.window})")

    return "\n".join(lines)


def get_quality_report() -> str:
    """Get quality metrics report."""
    summary = get_quality_summary()
    if summary["count"] == 0:
        return "📊 Нет данных о качестве"

    lines = [
        "📊 Качество ответов (7д):",
        f"  Проверок: {summary['count']}",
        f"  Средний балл: {summary['avg']:.2f}",
        f"  Прошли: {summary['passed_pct']}%",
    ]

    if summary.get("by_agent"):
        lines.append("  По агентам:")
        for agent, score in summary["by_agent"].items():
            name = AGENT_NAMES.get(agent, agent)
            lines.append(f"    {name}: {score:.2f}")

    return "\n".join(lines)


def format_analytics_report(hours: int = 24) -> str:
    """Format full analytics report for Telegram."""
    sections = [
        get_token_usage_report(hours),
        get_agent_activity_report(hours),
        get_cost_estimates(hours),
        get_alert_summary(hours),
        get_quality_report(),
    ]

    header = f"📊 Аналитика Zinin Corp ({hours}ч)\n{'═' * 30}"
    footer = f"\n🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}"

    return f"{header}\n\n" + "\n\n".join(sections) + footer


def format_weekly_digest() -> str:
    """Format weekly digest — pure data aggregation, no LLM.

    Covers: tasks, API usage, agent activity, quality, alerts.
    """
    hours = 168  # 7 days

    # Tasks from activity tracker
    events = get_recent_events(hours=hours, limit=1000)
    tasks_completed = sum(1 for e in events if e.get("type") == "task_end" and e.get("success"))
    tasks_failed = sum(1 for e in events if e.get("type") == "task_end" and not e.get("success"))
    delegations = sum(1 for e in events if e.get("type") == "delegation")
    communications = sum(1 for e in events if e.get("type") == "communication")

    # Task Pool stats
    try:
        from .task_pool import get_all_tasks, TaskStatus, get_archive_stats
        all_tasks = get_all_tasks()
        pool_todo = sum(1 for t in all_tasks if t.status == TaskStatus.TODO)
        pool_in_progress = sum(1 for t in all_tasks if t.status == TaskStatus.IN_PROGRESS)
        pool_blocked = sum(1 for t in all_tasks if t.status == TaskStatus.BLOCKED)
        pool_done = sum(1 for t in all_tasks if t.status == TaskStatus.DONE)
        archive_stats = get_archive_stats()
        archived_total = archive_stats.get("total_archived", 0)
    except Exception:
        pool_todo = pool_in_progress = pool_blocked = pool_done = archived_total = 0

    # API usage
    all_usage = get_all_usage(minutes=hours * 60)
    total_api_calls = sum(u["total_calls"] for u in all_usage.values())
    total_api_failed = sum(u["failed"] for u in all_usage.values())

    # Cost
    total_cost = sum(
        u["total_calls"] * COST_PER_REQUEST.get(p, 0.001)
        for p, u in all_usage.items()
    )

    # Alerts
    alerts = get_rate_alerts(hours=hours)

    # Quality
    quality = get_quality_summary()

    # Agent task counts
    agent_tasks: dict[str, int] = {}
    for e in events:
        if e.get("type") == "task_end":
            agent = e.get("agent", "unknown")
            agent_tasks[agent] = agent_tasks.get(agent, 0) + 1

    # Format
    now = datetime.now()
    week_start = (now - timedelta(days=7)).strftime("%d.%m")
    week_end = now.strftime("%d.%m.%Y")

    lines = [
        f"📋 Еженедельный дайджест ({week_start} — {week_end})",
        "═" * 35,
        "",
        "📌 Задачи:",
        f"  Выполнено: {tasks_completed} | Ошибок: {tasks_failed}",
        f"  Делегаций: {delegations} | Коммуникаций: {communications}",
        "",
        "📦 Task Pool:",
        f"  TODO: {pool_todo} | In Progress: {pool_in_progress} | Blocked: {pool_blocked} | Done: {pool_done}",
        f"  Архивировано (всего): {archived_total}",
        "",
        "📡 API:",
        f"  Вызовов: {total_api_calls} | Ошибок: {total_api_failed}",
        f"  Оценка расходов: ~${total_cost:.2f}",
        f"  Алертов: {len(alerts)}",
    ]

    if agent_tasks:
        lines.extend(["", "👥 Агенты (задач за неделю):"])
        for agent, count in sorted(agent_tasks.items(), key=lambda x: -x[1]):
            emoji = AGENT_EMOJI.get(agent, "")
            name = AGENT_NAMES.get(agent, agent)
            lines.append(f"  {emoji} {name}: {count}")

    if quality["count"] > 0:
        lines.extend([
            "",
            "📊 Качество:",
            f"  Средний балл: {quality['avg']:.2f} | Прошли: {quality['passed_pct']}%",
        ])

    lines.extend(["", f"🕐 {now.strftime('%d.%m.%Y %H:%M')}"])

    return "\n".join(lines)
