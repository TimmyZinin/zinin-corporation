"""Inline keyboards for CEO Telegram bot — CTO proposals & API diagnostics."""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


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
