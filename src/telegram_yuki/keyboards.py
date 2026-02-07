"""Inline keyboards for Yuki SMM bot — approval, rejection, editing."""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def approval_keyboard(post_id: str) -> InlineKeyboardMarkup:
    """Main approval keyboard: approve, reject, regenerate, edit."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"approve:{post_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject:{post_id}"),
        ],
        [
            InlineKeyboardButton(text="🔄 Переделать", callback_data=f"regen:{post_id}"),
            InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit:{post_id}"),
        ],
    ])


def reject_reasons_keyboard(post_id: str) -> InlineKeyboardMarkup:
    """Rejection reason selection keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📝 Не по теме", callback_data=f"reject_reason:off_topic:{post_id}"),
            InlineKeyboardButton(text="✍️ Плохой текст", callback_data=f"reject_reason:bad_text:{post_id}"),
        ],
        [
            InlineKeyboardButton(text="🎯 Не тот тон", callback_data=f"reject_reason:wrong_tone:{post_id}"),
            InlineKeyboardButton(text="📏 Неправильная длина", callback_data=f"reject_reason:wrong_length:{post_id}"),
        ],
        [
            InlineKeyboardButton(text="💬 Другое (напишите)", callback_data=f"reject_reason:other:{post_id}"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"back:{post_id}"),
        ],
    ])


def confirm_publish_keyboard(post_id: str) -> InlineKeyboardMarkup:
    """Confirm publication keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, опубликовать", callback_data=f"confirm_pub:{post_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"back:{post_id}"),
        ],
    ])


def platform_keyboard(post_id: str) -> InlineKeyboardMarkup:
    """Platform selection keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💼 LinkedIn", callback_data=f"platform:linkedin:{post_id}"),
            InlineKeyboardButton(text="🧵 Threads", callback_data=f"platform:threads:{post_id}"),
        ],
        [
            InlineKeyboardButton(text="📋 Только текст", callback_data=f"platform:text:{post_id}"),
        ],
    ])
