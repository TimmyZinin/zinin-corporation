"""Inline keyboards for CEO Telegram bot — CTO improvement proposals."""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


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
