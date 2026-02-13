"""
🚀 Zinin Corp — Proactive Daily Planner

100% rule-based, ZERO LLM cost.
Generates action items from revenue gap + content calendar + task pool.
Used by CEO bot scheduler for 3 daily touchpoints (09:00, 14:00, 20:00 MSK).

Paradigm: System proposes → Tim decides → Agent executes → System proposes next step.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# ActionItem model
# ──────────────────────────────────────────────────────────


@dataclass
class ActionItem:
    id: str = ""
    title: str = ""
    target_agent: str = ""        # "smm", "accountant", "automator", etc.
    agent_method: str = ""        # "run_generate_post", "send_to_agent", etc.
    method_kwargs: dict = field(default_factory=dict)
    priority: int = 3             # 1=critical, 2=high, 3=medium, 4=low
    category: str = ""            # "content", "revenue", "ops"
    status: str = "pending"       # "pending", "launched", "skipped", "completed"
    created_at: float = 0.0

    def __post_init__(self):
        if not self.id:
            self.id = f"act_{uuid4().hex[:8]}"
        if not self.created_at:
            self.created_at = time.time()


# ──────────────────────────────────────────────────────────
# In-memory action store with 24h TTL
# ──────────────────────────────────────────────────────────

_actions: dict[str, ActionItem] = {}
ACTION_TTL = 86400  # 24 hours


def store_action(action: ActionItem) -> None:
    """Store an action item in the in-memory store."""
    _actions[action.id] = action


def get_action(action_id: str) -> ActionItem | None:
    """Get an action by ID, returns None if not found or expired."""
    action = _actions.get(action_id)
    if action and (time.time() - action.created_at) > ACTION_TTL:
        del _actions[action_id]
        return None
    return action


def set_action_status(action_id: str, status: str) -> None:
    """Set action status (idempotent)."""
    action = _actions.get(action_id)
    if action:
        action.status = status


def get_pending_actions() -> list[ActionItem]:
    """Get all pending actions, sorted by priority."""
    cleanup_expired_actions()
    return sorted(
        [a for a in _actions.values() if a.status == "pending"],
        key=lambda a: a.priority,
    )


def get_next_pending_action() -> ActionItem | None:
    """Get the highest-priority pending action."""
    pending = get_pending_actions()
    return pending[0] if pending else None


def get_actions_summary() -> dict:
    """Get summary of current actions by status."""
    cleanup_expired_actions()
    summary = {"pending": 0, "launched": 0, "skipped": 0, "completed": 0, "total": 0}
    for action in _actions.values():
        summary[action.status] = summary.get(action.status, 0) + 1
        summary["total"] += 1
    return summary


def cleanup_expired_actions() -> int:
    """Remove actions older than TTL. Returns count removed."""
    now = time.time()
    expired = [aid for aid, a in _actions.items() if (now - a.created_at) > ACTION_TTL]
    for aid in expired:
        del _actions[aid]
    return len(expired)


def clear_all_actions() -> None:
    """Clear all actions (for testing)."""
    _actions.clear()


# ──────────────────────────────────────────────────────────
# Morning Plan Generation (rule-based)
# ──────────────────────────────────────────────────────────

MAX_MORNING_ACTIONS = 5


def generate_morning_plan() -> list[ActionItem]:
    """
    Generate 3-5 action items for the morning touchpoint.

    Rules (in priority order):
    1. Revenue gap > $1500 → add CFO analysis action
    2. Content calendar today → convert to SMM actions
    3. Content calendar overdue → add catch-up actions (high priority)
    4. Task pool > 5 unassigned → add triage action
    5. Cap at 5 actions, sort by priority
    """
    actions: list[ActionItem] = []

    # Rule 1: Revenue gap check
    try:
        from src.revenue_tracker import get_gap, get_days_left, format_revenue_summary
        gap = get_gap()
        days = get_days_left()
        if gap > 1500:
            actions.append(ActionItem(
                title=f"CFO: анализ revenue gap (${gap:,.0f}, {days} дней)",
                target_agent="accountant",
                agent_method="run_financial_report",
                method_kwargs={},
                priority=1,
                category="revenue",
            ))
    except Exception as e:
        logger.warning(f"Revenue check failed: {e}")

    # Rule 2: Content calendar — today's entries
    try:
        from src.content_calendar import get_today
        today_entries = get_today()
        for entry in today_entries:
            if entry.get("status") == "done":
                continue
            author = entry.get("author", "tim")
            topic = entry.get("topic", "пост")
            platform = entry.get("platform", "linkedin")
            actions.append(ActionItem(
                title=f"Юки: пост '{topic[:30]}' для {platform} ({author})",
                target_agent="smm",
                agent_method="run_generate_post",
                method_kwargs={"topic": topic, "author": author},
                priority=2,
                category="content",
            ))
    except Exception as e:
        logger.warning(f"Content calendar check failed: {e}")

    # Rule 3: Overdue content
    try:
        from src.content_calendar import get_overdue
        overdue = get_overdue()
        for entry in overdue[:2]:  # Max 2 overdue actions
            topic = entry.get("topic", "просроченный пост")
            author = entry.get("author", "tim")
            actions.append(ActionItem(
                title=f"⚠️ Просрочено: '{topic[:30]}' ({author})",
                target_agent="smm",
                agent_method="run_generate_post",
                method_kwargs={"topic": topic, "author": author},
                priority=1,
                category="content",
            ))
    except Exception as e:
        logger.warning(f"Overdue check failed: {e}")

    # Rule 4: Task pool triage
    try:
        from src.task_pool import get_tasks_by_status, TaskStatus
        todo_tasks = get_tasks_by_status(TaskStatus.TODO)
        if len(todo_tasks) > 5:
            actions.append(ActionItem(
                title=f"CEO: разобрать {len(todo_tasks)} непривязанных задач",
                target_agent="manager",
                agent_method="send_to_agent",
                method_kwargs={"message": f"Нужно разобрать {len(todo_tasks)} задач в Task Pool со статусом TODO. Посмотри приоритеты и назначь исполнителей."},
                priority=3,
                category="ops",
            ))
    except Exception as e:
        logger.warning(f"Task pool check failed: {e}")

    # Sort by priority, cap at MAX
    actions.sort(key=lambda a: a.priority)
    actions = actions[:MAX_MORNING_ACTIONS]

    # Store all actions
    for action in actions:
        store_action(action)

    return actions


# ──────────────────────────────────────────────────────────
# Midday Check Generation
# ──────────────────────────────────────────────────────────

MAX_MIDDAY_ACTIONS = 2


def generate_midday_check() -> list[ActionItem]:
    """
    Generate 1-2 action items for midday touchpoint.

    Rules:
    1. Count morning actions launched vs skipped
    2. If content from calendar was not started → urgent reminder
    3. Max 2 items
    """
    actions: list[ActionItem] = []
    summary = get_actions_summary()

    # Check if any content actions are still pending
    pending = get_pending_actions()
    content_pending = [a for a in pending if a.category == "content"]

    if content_pending:
        top = content_pending[0]
        actions.append(ActionItem(
            title=f"📢 Напоминание: {top.title}",
            target_agent=top.target_agent,
            agent_method=top.agent_method,
            method_kwargs=top.method_kwargs,
            priority=1,
            category="content",
        ))

    # If nothing pending, check revenue
    if not actions:
        try:
            from src.revenue_tracker import get_gap
            gap = get_gap()
            if gap > 1000:
                actions.append(ActionItem(
                    title=f"Revenue gap: ${gap:,.0f}. Что можно сделать сегодня?",
                    target_agent="manager",
                    agent_method="send_to_agent",
                    method_kwargs={"message": "Кратко: какой один шаг мы можем сделать сегодня для revenue?"},
                    priority=2,
                    category="revenue",
                ))
        except Exception:
            pass

    actions = actions[:MAX_MIDDAY_ACTIONS]
    for action in actions:
        store_action(action)
    return actions


# ──────────────────────────────────────────────────────────
# Evening Review Generation
# ──────────────────────────────────────────────────────────


def generate_evening_review() -> tuple[str, list[ActionItem]]:
    """
    Generate evening review summary + tomorrow's preview actions.

    Returns: (summary_text, tomorrow_actions)
    """
    summary = get_actions_summary()
    completed = summary.get("completed", 0)
    skipped = summary.get("skipped", 0)
    total = summary.get("total", 0)

    # Build summary text
    lines = [
        "📊 Итоги дня",
        "",
        f"Выполнено: {completed}/{total}",
        f"Пропущено: {skipped}/{total}",
    ]

    # Revenue snapshot
    try:
        from src.revenue_tracker import get_revenue_summary
        rev = get_revenue_summary()
        lines.append(f"\n💰 MRR: ${rev['total_mrr']:,.0f} / ${rev['target_mrr']:,.0f}")
        lines.append(f"Gap: ${rev['gap']:,.0f} | {rev['days_left']} дней")
    except Exception:
        pass

    # Content status
    try:
        from src.content_calendar import get_today
        today_entries = get_today()
        done_count = sum(1 for e in today_entries if e.get("status") == "done")
        lines.append(f"\n📝 Контент: {done_count}/{len(today_entries)} опубликовано")
    except Exception:
        pass

    summary_text = "\n".join(lines)

    # Tomorrow preview (just peek at calendar)
    tomorrow_actions: list[ActionItem] = []
    try:
        from src.content_calendar import get_date
        from datetime import date, timedelta
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        tomorrow_entries = get_date(tomorrow)
        for entry in tomorrow_entries[:3]:
            topic = entry.get("topic", "пост")
            author = entry.get("author", "tim")
            tomorrow_actions.append(ActionItem(
                title=f"Завтра: '{topic[:30]}' ({author})",
                target_agent="smm",
                agent_method="run_generate_post",
                method_kwargs={"topic": topic, "author": author},
                priority=2,
                category="content",
            ))
    except Exception:
        pass

    return summary_text, tomorrow_actions


# ──────────────────────────────────────────────────────────
# Telegram message formatters
# ──────────────────────────────────────────────────────────


def format_morning_message(actions: list[ActionItem]) -> str:
    """Format morning plan for Telegram."""
    if not actions:
        return "☀️ Доброе утро! Сегодня нет запланированных действий."

    lines = ["☀️ Утренний план"]

    # Revenue header
    try:
        from src.revenue_tracker import format_revenue_summary
        lines.append("")
        lines.append(format_revenue_summary())
    except Exception:
        pass

    lines.append(f"\n📋 Действия на сегодня ({len(actions)}):")
    for i, action in enumerate(actions, 1):
        priority_icon = {1: "🔴", 2: "🟡", 3: "🟢", 4: "⚪"}.get(action.priority, "⚪")
        lines.append(f"\n{i}. {priority_icon} {action.title}")

    return "\n".join(lines)


def format_midday_message(actions: list[ActionItem]) -> str:
    """Format midday check for Telegram."""
    summary = get_actions_summary()

    lines = [
        "🕐 Дневная проверка",
        "",
        f"Статус: {summary['completed']} выполнено, {summary['pending']} в ожидании",
    ]

    if actions:
        lines.append(f"\n📋 Что нужно сделать:")
        for action in actions:
            lines.append(f"  • {action.title}")

    return "\n".join(lines)


def format_evening_message(summary: str, tomorrow: list[ActionItem]) -> str:
    """Format evening review for Telegram."""
    lines = [summary]

    if tomorrow:
        lines.append(f"\n📅 Завтра ({len(tomorrow)}):")
        for action in tomorrow:
            lines.append(f"  • {action.title}")

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────
# Agent method routing map
# ──────────────────────────────────────────────────────────

# Maps agent_method string → actual method name on AgentBridge
# Used by CEO bot callback handler to route [Запустить] presses
AGENT_METHOD_MAP = {
    "run_generate_post": "run_generate_post",
    "run_financial_report": "run_financial_report",
    "run_strategic_review": "run_strategic_review",
    "run_linkedin_status": "run_linkedin_status",
    "run_corporation_report": "run_corporation_report",
    "run_generate_podcast": "run_generate_podcast",
    "run_api_health_report": "run_api_health_report",
    "run_cto_proposal": "run_cto_proposal",
    "send_to_agent": "send_to_agent",
}
