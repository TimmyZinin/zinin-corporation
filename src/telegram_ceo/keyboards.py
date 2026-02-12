"""Inline keyboards for CEO Telegram bot — CTO proposals, API diagnostics, Task Pool."""

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
