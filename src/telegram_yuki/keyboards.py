"""Inline keyboards for Yuki SMM bot — approval, platforms, scheduling, menu UX, ratings."""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from .publishers import get_all_publishers

# Platform short codes for compact callback_data (< 64 bytes)
PLAT_SHORT = {"linkedin": "li", "threads": "th", "telegram": "tg"}
PLAT_LONG = {v: k for k, v in PLAT_SHORT.items()}
PLAT_EMOJI = {"linkedin": "💼", "threads": "🧵", "telegram": "📱"}


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


def post_ready_keyboard(post_id: str) -> InlineKeyboardMarkup:
    """Post ready keyboard — choose image or publish without. CS-001 + CS-002."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🖼 С картинкой", callback_data=f"gen_image:{post_id}"),
            InlineKeyboardButton(text="📝 Без картинки", callback_data=f"approve:{post_id}"),
        ],
        [
            InlineKeyboardButton(text="🔄 Переделать", callback_data=f"regen:{post_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject:{post_id}"),
        ],
        [
            InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit:{post_id}"),
        ],
    ])


def approval_with_image_keyboard(post_id: str) -> InlineKeyboardMarkup:
    """Approval keyboard when image is attached. CS-003."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"approve:{post_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject:{post_id}"),
        ],
        [
            InlineKeyboardButton(text="🎨 Другая картинка", callback_data=f"regen_image:{post_id}"),
            InlineKeyboardButton(text="🔄 Переделать текст", callback_data=f"regen:{post_id}"),
        ],
        [
            InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit:{post_id}"),
        ],
    ])


def final_choice_keyboard(post_id: str) -> InlineKeyboardMarkup:
    """Final choice keyboard after max iterations. CS-004."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Опубликовать как есть", callback_data=f"approve:{post_id}"),
            InlineKeyboardButton(text="🗑 Отклонить окончательно", callback_data=f"reject:{post_id}"),
        ],
    ])


def feedback_keyboard(post_id: str) -> InlineKeyboardMarkup:
    """Post-publish feedback keyboard: feedback on this post or for future posts."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✏️ Правки к этому посту",
                callback_data=f"fb_post:{post_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="📝 Фидбек на будущее",
                callback_data=f"fb_future:{post_id}",
            ),
        ],
    ])


def preselect_keyboard(
    current_author: str = "", current_platform: str = "",
) -> InlineKeyboardMarkup:
    """Account + platform pre-selection before post generation.

    Highlights current author/platform with checkmarks.
    """
    def _mark(label: str, key: str, current: str) -> str:
        return f"✓ {label}" if key == current else label

    buttons = [
        # Author row
        [
            InlineKeyboardButton(
                text=_mark("👩 Кристина", "kristina", current_author),
                callback_data="pre_author:kristina",
            ),
            InlineKeyboardButton(
                text=_mark("👤 Тим", "tim", current_author),
                callback_data="pre_author:tim",
            ),
        ],
        # Platform row
        [
            InlineKeyboardButton(
                text=_mark("💼 LinkedIn", "linkedin", current_platform),
                callback_data="pre_platform:linkedin",
            ),
            InlineKeyboardButton(
                text=_mark("🧵 Threads", "threads", current_platform),
                callback_data="pre_platform:threads",
            ),
            InlineKeyboardButton(
                text=_mark("📱 Telegram", "telegram", current_platform),
                callback_data="pre_platform:telegram",
            ),
        ],
        # All platforms
        [
            InlineKeyboardButton(
                text=_mark("📢 Все платформы", "all", current_platform),
                callback_data="pre_platform:all",
            ),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── Calendar & Planning keyboards ────────────────────────────────────────


def calendar_entry_keyboard(entry_id: str) -> InlineKeyboardMarkup:
    """Inline buttons for a single calendar entry: generate, skip, edit topic."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🚀 Сгенерировать пост",
                callback_data=f"cal_gen:{entry_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="⏭ Пропустить",
                callback_data=f"cal_skip:{entry_id}",
            ),
            InlineKeyboardButton(
                text="✏️ Изменить тему",
                callback_data=f"cal_edit:{entry_id}",
            ),
        ],
    ])


def plan_source_keyboard(has_entries: bool = True) -> InlineKeyboardMarkup:
    """Choose source for new post: from calendar or custom topic."""
    rows = []
    if has_entries:
        rows.append([
            InlineKeyboardButton(
                text="📅 Из календаря",
                callback_data="plan_cal",
            ),
        ])
    rows.append([
        InlineKeyboardButton(
            text="✍️ Своя тема",
            callback_data="plan_new",
        ),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def calendar_pick_keyboard(entries: list[dict]) -> InlineKeyboardMarkup:
    """List of calendar entries as pick-buttons (max 5)."""
    rows = []
    for e in entries[:5]:
        label = e.get("topic", "?")
        if len(label) > 40:
            label = label[:37] + "..."
        author = e.get("author", "?")
        rows.append([
            InlineKeyboardButton(
                text=f"📝 {label} ({author})",
                callback_data=f"plan_pick:{e['id']}",
            ),
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def preselect_confirm_keyboard() -> InlineKeyboardMarkup:
    """Confirm pre-selection and start generation."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Генерировать",
                callback_data="pre_go",
            ),
            InlineKeyboardButton(
                text="🔄 Изменить",
                callback_data="pre_change",
            ),
        ],
    ])


# ── Menu-first UX keyboards ─────────────────────────────────────────────


def start_menu_keyboard() -> InlineKeyboardMarkup:
    """Main menu: author selection + calendar + status."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📝 Тим", callback_data="m_au:tim"),
            InlineKeyboardButton(text="📝 Кристина", callback_data="m_au:kristina"),
        ],
        [
            InlineKeyboardButton(text="📅 Календарь", callback_data="m_cal_view"),
            InlineKeyboardButton(text="📊 Статус", callback_data="m_status"),
        ],
    ])


def author_submenu_keyboard(author: str) -> InlineKeyboardMarkup:
    """Author submenu: from calendar, custom topic, or market topics."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔥 Из календаря", callback_data="m_cal"),
            InlineKeyboardButton(text="✍️ Своя тема", callback_data="m_topic"),
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="m_back"),
        ],
    ])


# ── Multi-platform post keyboards ───────────────────────────────────────


def multiplatform_post_keyboard(post_id: str, platform: str) -> InlineKeyboardMarkup:
    """Per-platform actions: publish, improve, schedule, remove."""
    ps = PLAT_SHORT.get(platform, platform[:2])
    emoji = PLAT_EMOJI.get(platform, "📝")
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"✅ Опубликовать {emoji}",
                callback_data=f"mp_pub:{ps}:{post_id}",
            ),
            InlineKeyboardButton(
                text="🔄 Улучшить",
                callback_data=f"mp_imp:{ps}:{post_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="📅 Запланировать",
                callback_data=f"mp_sch:{ps}:{post_id}",
            ),
            InlineKeyboardButton(
                text="❌ Убрать",
                callback_data=f"mp_rm:{ps}:{post_id}",
            ),
        ],
    ])


def publish_all_keyboard(post_id: str) -> InlineKeyboardMarkup:
    """Publish all pending platforms at once."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🚀 Опубликовать ВСЁ",
                callback_data=f"mp_all:{post_id}",
            ),
        ],
    ])


def published_lock_keyboard(platform: str) -> InlineKeyboardMarkup:
    """Disabled button showing published status."""
    emoji = PLAT_EMOJI.get(platform, "✅")
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"✅ Опубликовано {emoji} {platform}",
                callback_data="noop",
            ),
        ],
    ])


# ── Post-publish rating + image keyboards ────────────────────────────────


def rating_keyboard(prefix: str, post_id: str, label: str = "") -> InlineKeyboardMarkup:
    """Rating 1-5 stars. prefix: r_txt, r_img, r_ovr."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1⭐", callback_data=f"{prefix}:1:{post_id}"),
            InlineKeyboardButton(text="2⭐", callback_data=f"{prefix}:2:{post_id}"),
            InlineKeyboardButton(text="3⭐", callback_data=f"{prefix}:3:{post_id}"),
            InlineKeyboardButton(text="4⭐", callback_data=f"{prefix}:4:{post_id}"),
            InlineKeyboardButton(text="5⭐", callback_data=f"{prefix}:5:{post_id}"),
        ],
    ])


def image_offer_keyboard(post_id: str) -> InlineKeyboardMarkup:
    """Offer to generate image after publish."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🖼 Создать картинку", callback_data=f"pp_img:{post_id}"),
            InlineKeyboardButton(text="⏭ Пропустить", callback_data=f"pp_skip:{post_id}"),
        ],
    ])


def image_review_keyboard(post_id: str) -> InlineKeyboardMarkup:
    """Review generated image: accept, redo, refine with text, reject."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"pp_ok:{post_id}"),
            InlineKeyboardButton(text="🔄 Переделать", callback_data=f"pp_redo:{post_id}"),
        ],
        [
            InlineKeyboardButton(text="✏️ Уточнить", callback_data=f"pp_fb:{post_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"pp_no:{post_id}"),
        ],
    ])
