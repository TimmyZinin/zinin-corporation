"""Inline keyboards for CEO Telegram bot — CTO proposals, API diagnostics, Task Pool, Gallery."""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# ── Task Pool keyboards ──────────────────────────────────────────────────────

def task_menu_keyboard() -> InlineKeyboardMarkup:
    """Main task menu — shown on /task without arguments."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📝 Новая задача", callback_data="task_new"),
            InlineKeyboardButton(text="📋 Все задачи", callback_data="task_all"),
        ],
        [
            InlineKeyboardButton(text="✅ Готовые", callback_data="task_filter:TODO"),
            InlineKeyboardButton(text="🔄 В работе", callback_data="task_filter:IN_PROGRESS"),
            InlineKeyboardButton(text="🚫 Заблок.", callback_data="task_filter:BLOCKED"),
        ],
    ])


def task_detail_keyboard(task_id: str, status: str) -> InlineKeyboardMarkup:
    """Actions for a specific task, depends on current status."""
    buttons = []

    if status == "TODO":
        buttons.append([
            InlineKeyboardButton(text="👤 Назначить", callback_data=f"task_assign:{task_id}"),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"task_delete:{task_id}"),
        ])
    elif status == "ASSIGNED":
        buttons.append([
            InlineKeyboardButton(text="▶️ Начать", callback_data=f"task_start:{task_id}"),
            InlineKeyboardButton(text="👤 Переназначить", callback_data=f"task_assign:{task_id}"),
        ])
    elif status == "IN_PROGRESS":
        buttons.append([
            InlineKeyboardButton(text="✅ Завершить", callback_data=f"task_done:{task_id}"),
            InlineKeyboardButton(text="🚫 Блок", callback_data=f"task_block:{task_id}"),
        ])
    elif status == "BLOCKED":
        buttons.append([
            InlineKeyboardButton(text="👤 Назначить", callback_data=f"task_assign:{task_id}"),
        ])

    buttons.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data="task_all"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def task_assign_keyboard(task_id: str) -> InlineKeyboardMarkup:
    """Choose agent to assign the task to."""
    agents = [
        ("Маттиас (CFO)", "accountant"),
        ("Мартин (CTO)", "automator"),
        ("Юки (SMM)", "smm"),
        ("Райан (Design)", "designer"),
        ("Софи (CPO)", "cpo"),
    ]
    buttons = []
    for label, key in agents:
        buttons.append([
            InlineKeyboardButton(
                text=label,
                callback_data=f"task_do_assign:{task_id}:{key}",
            ),
        ])
    buttons.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data=f"task_detail:{task_id}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def escalation_keyboard(task_id: str) -> InlineKeyboardMarkup:
    """Escalation options when no agent matches the task tags."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔧 Расширить промпт",
                callback_data=f"esc_extend:{task_id}",
            ),
            InlineKeyboardButton(
                text="🤖 Создать агента",
                callback_data=f"esc_create:{task_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="✂️ Разделить задачу",
                callback_data=f"esc_split:{task_id}",
            ),
            InlineKeyboardButton(
                text="👤 Назначить вручную",
                callback_data=f"esc_manual:{task_id}",
            ),
        ],
    ])


def stale_task_keyboard(task_id: str) -> InlineKeyboardMarkup:
    """Actions for a stale task found by Orphan Patrol."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="👤 Переназначить",
                callback_data=f"task_assign:{task_id}",
            ),
            InlineKeyboardButton(
                text="🚫 Заблокировать",
                callback_data=f"task_block:{task_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="📋 Подробнее",
                callback_data=f"task_detail:{task_id}",
            ),
        ],
    ])


def action_keyboard(action_id: str) -> InlineKeyboardMarkup:
    """Action keyboard for proactive planner items — [Launch] [Skip]."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🚀 Запустить",
                callback_data=f"action_launch:{action_id}",
            ),
            InlineKeyboardButton(
                text="⏭ Пропустить",
                callback_data=f"action_skip:{action_id}",
            ),
        ],
    ])


def evening_review_keyboard() -> InlineKeyboardMarkup:
    """Evening review keyboard — [Approve plan] [Adjust]."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Утвердить план",
                callback_data="evening_approve",
            ),
            InlineKeyboardButton(
                text="✏️ Скорректировать",
                callback_data="evening_adjust",
            ),
        ],
    ])


def diagnostic_keyboard(diag_id: str) -> InlineKeyboardMarkup:
    """Action keyboard for CTO API diagnostic reports."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔄 Перепроверить",
                callback_data=f"api_recheck:{diag_id}",
            ),
            InlineKeyboardButton(
                text="📋 Подробнее",
                callback_data=f"api_detail:{diag_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="🔇 Принято",
                callback_data=f"api_ack:{diag_id}",
            ),
        ],
    ])


def proposal_keyboard(proposal_id: str) -> InlineKeyboardMarkup:
    """Approval keyboard for CTO improvement proposals."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Одобрить",
                callback_data=f"cto_approve:{proposal_id}",
            ),
            InlineKeyboardButton(
                text="❌ Отклонить",
                callback_data=f"cto_reject:{proposal_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="📝 Условия",
                callback_data=f"cto_conditions:{proposal_id}",
            ),
            InlineKeyboardButton(
                text="📋 Подробнее",
                callback_data=f"cto_detail:{proposal_id}",
            ),
        ],
    ])


# ── Gallery keyboards ────────────────────────────────────────────────────────

def gallery_keyboard(
    image_id: str = "",
    page: int = 0,
    pages: int = 1,
) -> InlineKeyboardMarkup:
    """Gallery keyboard: approve/reject/forward + pagination."""
    rows = []

    # Action buttons for current image (if any pending)
    if image_id:
        rows.append([
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"gal_ok:{image_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"gal_no:{image_id}"),
            InlineKeyboardButton(text="📱 → Юки", callback_data=f"gal_fwd:{image_id}"),
        ])

    # Pagination
    if pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️", callback_data=f"gal_page:{page - 1}"))
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data="gal_noop"))
        if page < pages - 1:
            nav.append(InlineKeyboardButton(text="▶️", callback_data=f"gal_page:{page + 1}"))
        rows.append(nav)

    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else InlineKeyboardMarkup(inline_keyboard=[])
