"""Inline keyboards for CEO Telegram bot — typed CallbackData factories."""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

from .callback_factory import (
    TaskCB, EscCB, CtoCB, ApiCB, ActionCB, EveningCB,
    GalleryCB, VoiceBrainCB, SubMenuCB,
)


# ── Task Pool keyboards ──────────────────────────────────────────────────────

def task_menu_keyboard() -> InlineKeyboardMarkup:
    """Main task menu — shown on /task without arguments."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📝 Новая задача", callback_data=TaskCB(action="new").pack()),
            InlineKeyboardButton(text="📋 Все задачи", callback_data=TaskCB(action="all").pack()),
        ],
        [
            InlineKeyboardButton(text="✅ Готовые", callback_data=TaskCB(action="filter", id="TODO").pack()),
            InlineKeyboardButton(text="🔄 В работе", callback_data=TaskCB(action="filter", id="IN_PROGRESS").pack()),
            InlineKeyboardButton(text="🚫 Заблок.", callback_data=TaskCB(action="filter", id="BLOCKED").pack()),
        ],
    ])


def task_detail_keyboard(task_id: str, status: str) -> InlineKeyboardMarkup:
    """Actions for a specific task, depends on current status."""
    buttons = []

    if status == "TODO":
        buttons.append([
            InlineKeyboardButton(text="👤 Назначить", callback_data=TaskCB(action="assign", id=task_id).pack()),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=TaskCB(action="delete", id=task_id).pack()),
        ])
    elif status == "ASSIGNED":
        buttons.append([
            InlineKeyboardButton(text="▶️ Начать", callback_data=TaskCB(action="start", id=task_id).pack()),
            InlineKeyboardButton(text="👤 Переназначить", callback_data=TaskCB(action="assign", id=task_id).pack()),
        ])
    elif status == "IN_PROGRESS":
        buttons.append([
            InlineKeyboardButton(text="✅ Завершить", callback_data=TaskCB(action="done", id=task_id).pack()),
            InlineKeyboardButton(text="🚫 Блок", callback_data=TaskCB(action="block", id=task_id).pack()),
        ])
    elif status == "BLOCKED":
        buttons.append([
            InlineKeyboardButton(text="👤 Назначить", callback_data=TaskCB(action="assign", id=task_id).pack()),
        ])

    buttons.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data=TaskCB(action="all").pack()),
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
                callback_data=TaskCB(action="do_assign", id=task_id, agent=key).pack(),
            ),
        ])
    buttons.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data=TaskCB(action="detail", id=task_id).pack()),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def escalation_keyboard(task_id: str) -> InlineKeyboardMarkup:
    """Escalation options when no agent matches the task tags."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔧 Расширить промпт", callback_data=EscCB(action="extend", id=task_id).pack()),
            InlineKeyboardButton(text="🤖 Создать агента", callback_data=EscCB(action="create", id=task_id).pack()),
        ],
        [
            InlineKeyboardButton(text="✂️ Разделить задачу", callback_data=EscCB(action="split", id=task_id).pack()),
            InlineKeyboardButton(text="👤 Назначить вручную", callback_data=EscCB(action="manual", id=task_id).pack()),
        ],
    ])


def stale_task_keyboard(task_id: str) -> InlineKeyboardMarkup:
    """Actions for a stale task found by Orphan Patrol."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👤 Переназначить", callback_data=TaskCB(action="assign", id=task_id).pack()),
            InlineKeyboardButton(text="🚫 Заблокировать", callback_data=TaskCB(action="block", id=task_id).pack()),
        ],
        [
            InlineKeyboardButton(text="📋 Подробнее", callback_data=TaskCB(action="detail", id=task_id).pack()),
        ],
    ])


def action_keyboard(action_id: str) -> InlineKeyboardMarkup:
    """Action keyboard for proactive planner items — [Launch] [Skip]."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🚀 Запустить", callback_data=ActionCB(action="launch", id=action_id).pack()),
            InlineKeyboardButton(text="⏭ Пропустить", callback_data=ActionCB(action="skip", id=action_id).pack()),
        ],
    ])


def evening_review_keyboard() -> InlineKeyboardMarkup:
    """Evening review keyboard — [Approve plan] [Adjust]."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Утвердить план", callback_data=EveningCB(action="approve").pack()),
            InlineKeyboardButton(text="✏️ Скорректировать", callback_data=EveningCB(action="adjust").pack()),
        ],
    ])


def diagnostic_keyboard(diag_id: str) -> InlineKeyboardMarkup:
    """Action keyboard for CTO API diagnostic reports."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Перепроверить", callback_data=ApiCB(action="recheck", id=diag_id).pack()),
            InlineKeyboardButton(text="📋 Подробнее", callback_data=ApiCB(action="detail", id=diag_id).pack()),
        ],
        [
            InlineKeyboardButton(text="🔇 Принято", callback_data=ApiCB(action="ack", id=diag_id).pack()),
        ],
    ])


def proposal_keyboard(proposal_id: str) -> InlineKeyboardMarkup:
    """Approval keyboard for CTO improvement proposals."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=CtoCB(action="approve", id=proposal_id).pack()),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=CtoCB(action="reject", id=proposal_id).pack()),
        ],
        [
            InlineKeyboardButton(text="📝 Условия", callback_data=CtoCB(action="conditions", id=proposal_id).pack()),
            InlineKeyboardButton(text="📋 Подробнее", callback_data=CtoCB(action="detail", id=proposal_id).pack()),
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

    if image_id:
        rows.append([
            InlineKeyboardButton(text="✅ Одобрить", callback_data=GalleryCB(action="ok", id=image_id).pack()),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=GalleryCB(action="no", id=image_id).pack()),
            InlineKeyboardButton(text="📱 → Юки", callback_data=GalleryCB(action="fwd", id=image_id).pack()),
        ])

    if pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️", callback_data=GalleryCB(action="page", id=str(page - 1)).pack()))
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data=GalleryCB(action="noop").pack()))
        if page < pages - 1:
            nav.append(InlineKeyboardButton(text="▶️", callback_data=GalleryCB(action="page", id=str(page + 1)).pack()))
        rows.append(nav)

    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else InlineKeyboardMarkup(inline_keyboard=[])


# ── Voice Brain Dump keyboards ──────────────────────────────────────────────

def voice_brain_confirm_keyboard() -> InlineKeyboardMarkup:
    """Confirmation keyboard for voice brain dump: [Yes] [Correct] [Cancel]."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, верно", callback_data=VoiceBrainCB(action="confirm").pack()),
            InlineKeyboardButton(text="❌ Уточнить", callback_data=VoiceBrainCB(action="correct").pack()),
            InlineKeyboardButton(text="🚫 Отмена", callback_data=VoiceBrainCB(action="cancel").pack()),
        ],
    ])


# ── ReplyKeyboard (persistent menu) ─────────────────────────────────────────

def main_reply_keyboard() -> ReplyKeyboardMarkup:
    """Persistent 3x2 reply keyboard for CEO bot."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📋 Задачи"),
                KeyboardButton(text="📊 Статус"),
                KeyboardButton(text="📈 Аналитика"),
            ],
            [
                KeyboardButton(text="✍️ Контент"),
                KeyboardButton(text="🖼 Галерея"),
                KeyboardButton(text="❓ Помощь"),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


# ── Sub-menu keyboards ──────────────────────────────────────────────────────

def content_submenu_keyboard() -> InlineKeyboardMarkup:
    """Content sub-menu: post / calendar / linkedin."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📝 Пост", callback_data=SubMenuCB(menu="content", action="post").pack()),
            InlineKeyboardButton(text="📅 Календарь", callback_data=SubMenuCB(menu="content", action="calendar").pack()),
            InlineKeyboardButton(text="📱 LinkedIn", callback_data=SubMenuCB(menu="content", action="linkedin").pack()),
        ],
    ])


def status_submenu_keyboard() -> InlineKeyboardMarkup:
    """Status sub-menu: agents / tasks / revenue."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Агенты", callback_data=SubMenuCB(menu="status", action="agents").pack()),
            InlineKeyboardButton(text="📋 Tasks", callback_data=SubMenuCB(menu="status", action="tasks").pack()),
            InlineKeyboardButton(text="💰 Revenue", callback_data=SubMenuCB(menu="status", action="revenue").pack()),
        ],
    ])
