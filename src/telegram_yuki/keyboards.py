"""Inline keyboards for Yuki SMM bot — approval, platforms, scheduling."""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from .publishers import get_all_publishers


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


def platform_keyboard(post_id: str) -> InlineKeyboardMarkup:
    """Platform selection keyboard — all registered publishers + all."""
    publishers = get_all_publishers()
    rows = []
    row = []
    for name, pub in publishers.items():
        btn = InlineKeyboardButton(
            text=f"{pub.emoji} {pub.label}",
            callback_data=f"pub_platform:{name}:{post_id}",
        )
        row.append(btn)
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    # "All platforms" and "back" buttons
    rows.append([
        InlineKeyboardButton(
            text="📢 Все платформы",
            callback_data=f"pub_platform:all:{post_id}",
        ),
    ])
    rows.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data=f"back:{post_id}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def time_keyboard(post_id: str) -> InlineKeyboardMarkup:
    """Time selection keyboard — when to publish."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚡ Сейчас", callback_data=f"pub_time:now:{post_id}"),
            InlineKeyboardButton(text="🕐 Через 1 час", callback_data=f"pub_time:1h:{post_id}"),
        ],
        [
            InlineKeyboardButton(text="🕒 Через 3 часа", callback_data=f"pub_time:3h:{post_id}"),
            InlineKeyboardButton(text="🌅 Завтра 10:00", callback_data=f"pub_time:tomorrow:{post_id}"),
        ],
        [
            InlineKeyboardButton(text="🌆 Сегодня вечером", callback_data=f"pub_time:evening:{post_id}"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад к платформам", callback_data=f"approve:{post_id}"),
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


def author_keyboard(post_id: str) -> InlineKeyboardMarkup:
    """Author selection keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👩 Кристина (СБОРКА)", callback_data=f"set_author:kristina:{post_id}"),
        ],
        [
            InlineKeyboardButton(text="👤 Тим (СБОРКА)", callback_data=f"set_author:tim:{post_id}"),
        ],
        [
            InlineKeyboardButton(text="👤 Тим (личный бренд)", callback_data=f"set_author:tim_personal:{post_id}"),
        ],
    ])
