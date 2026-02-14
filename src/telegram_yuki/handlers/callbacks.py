"""Callback query handler — inline button presses for Yuki SMM bot.

Flow: approve → platform selection → time selection → publish/schedule.
"""

import asyncio
import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery

from ...telegram.bridge import AgentBridge
from ...telegram.formatters import format_for_telegram
from ..keyboards import (
    approval_keyboard, reject_reasons_keyboard, platform_keyboard,
    time_keyboard, author_keyboard, feedback_keyboard,
    approval_with_image_keyboard, post_ready_keyboard,
    preselect_keyboard, preselect_confirm_keyboard,
    calendar_entry_keyboard, plan_source_keyboard, calendar_pick_keyboard,
    start_menu_keyboard, author_submenu_keyboard,
    multiplatform_post_keyboard, publish_all_keyboard, published_lock_keyboard,
    rating_keyboard, image_offer_keyboard, image_review_keyboard,
    PLAT_SHORT, PLAT_LONG, PLAT_EMOJI,
)
from ..drafts import DraftManager
from ..image_gen import generate_image, generate_image_with_refinement
from ..image_pipeline import generate_image_via_pipeline
from ..publishers import get_publisher, get_all_publishers, AUTHORS
from ..scheduler import PostScheduler, get_schedule_time
from ..safety import circuit_breaker

logger = logging.getLogger(__name__)
router = Router()

# Pre-selection state: user_id → {"topic": str, "author": str, "brand": str, "platform": str, "calendar_entry_id": str?}
_preselect_state: dict[int, dict] = {}

# Calendar / plan state
_calendar_edit_state: dict[int, str] = {}  # user_id → entry_id being edited
_plan_custom_state: set[int] = set()       # user_ids in custom topic input mode

# Menu state
_menu_state: dict[int, dict] = {}  # user_id → {"author": str, "market_topics": list}


# ── Pre-selection flow ─────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("pre_author:"))
async def on_pre_author(callback: CallbackQuery):
    """User selected author in pre-select keyboard."""
    user_id = callback.from_user.id
    author = callback.data.split(":")[1]
    state = _preselect_state.get(user_id)
    if not state:
        await callback.answer("Сессия истекла. Отправь запрос заново.")
        return

    state["author"] = author
    # Update brand: personal only for tim
    if author == "tim" and state.get("brand") == "sborka":
        pass  # Keep sborka as default for tim
    elif author == "kristina":
        state["brand"] = "sborka"

    # If both author and platform selected → show confirm
    if "platform" in state:
        await _show_preselect_summary(callback, state)
    else:
        from ..keyboards import preselect_keyboard
        await callback.message.edit_text(
            f"📝 Пост: {state.get('topic', '?')}\n\n"
            f"Выберите автора и платформу:",
            reply_markup=preselect_keyboard(
                current_author=author,
                current_platform=state.get("platform", ""),
            ),
        )
        await callback.answer(f"Автор: {author}")


@router.callback_query(F.data.startswith("pre_platform:"))
async def on_pre_platform(callback: CallbackQuery):
    """User selected platform in pre-select keyboard."""
    user_id = callback.from_user.id
    platform = callback.data.split(":")[1]
    state = _preselect_state.get(user_id)
    if not state:
        await callback.answer("Сессия истекла. Отправь запрос заново.")
        return

    state["platform"] = platform

    # If author already set (always is from parser default) → show confirm
    await _show_preselect_summary(callback, state)


@router.callback_query(F.data == "pre_go")
async def on_pre_go(callback: CallbackQuery):
    """User confirmed pre-selection. Start generation."""
    user_id = callback.from_user.id
    state = _preselect_state.pop(user_id, None)
    if not state:
        await callback.answer("Сессия истекла. Отправь запрос заново.")
        return

    topic = state.get("topic", "")
    author = state.get("author", "kristina")
    brand = state.get("brand", "sborka")
    platform = state.get("platform", "linkedin")
    calendar_entry_id = state.get("calendar_entry_id", "")

    await callback.answer("Генерирую...")
    await callback.message.edit_text(
        f"📱 Генерирую пост: {topic[:40]}...\n"
        f"Автор: {author} | Платформа: {platform}"
    )

    # Run generation with platform
    from .messages import _generate_post_flow
    await _generate_post_flow(
        callback.message, topic, author, brand, platform=platform,
        calendar_entry_id=calendar_entry_id,
    )


@router.callback_query(F.data == "pre_change")
async def on_pre_change(callback: CallbackQuery):
    """Reset pre-selection — show keyboard again."""
    user_id = callback.from_user.id
    state = _preselect_state.get(user_id, {})
    # Clear platform to reset selection
    state.pop("platform", None)
    topic = state.get("topic", "")

    from ..keyboards import preselect_keyboard
    await callback.message.edit_text(
        f"📝 Пост: {topic}\n\nВыберите автора и платформу:",
        reply_markup=preselect_keyboard(
            current_author=state.get("author", ""),
        ),
    )
    await callback.answer()


async def _show_preselect_summary(callback: CallbackQuery, state: dict):
    """Show summary of pre-selection and confirm button."""
    topic = state.get("topic", "?")
    author = state.get("author", "kristina")
    platform = state.get("platform", "linkedin")

    author_labels = {"kristina": "👩 Кристина", "tim": "👤 Тим"}
    platform_labels = {
        "linkedin": "💼 LinkedIn", "threads": "🧵 Threads",
        "telegram": "📱 Telegram", "all": "📢 Все платформы",
    }

    from ..keyboards import preselect_confirm_keyboard
    await callback.message.edit_text(
        f"📝 Пост: {topic}\n\n"
        f"Автор: {author_labels.get(author, author)}\n"
        f"Платформа: {platform_labels.get(platform, platform)}\n\n"
        f"Всё верно?",
        reply_markup=preselect_confirm_keyboard(),
    )
    await callback.answer()


# ── Approval → Platform selection ───────────────────────────────────────────

@router.callback_query(F.data.startswith("approve:"))
async def on_approve(callback: CallbackQuery):
    """Approve post → show platform selection (or skip if pre-selected)."""
    post_id = callback.data.split(":")[1]
    draft = DraftManager.get_draft(post_id)
    if not draft:
        await callback.answer("Черновик не найден", show_alert=True)
        return

    DraftManager.update_draft(post_id, status="approved")

    # If platforms were pre-selected → skip platform keyboard, go to time
    platforms = draft.get("platforms", [])
    if platforms and platforms != ["linkedin"]:
        platform_labels = []
        for p in platforms:
            pub = get_publisher(p)
            platform_labels.append(f"{pub.emoji} {pub.label}" if pub else p)
        await callback.message.edit_text(
            f"Пост одобрен (ID: {post_id})\n"
            f"Платформы: {', '.join(platform_labels)}\n"
            f"Когда публикуем?",
            reply_markup=time_keyboard(post_id),
        )
    else:
        await callback.message.edit_text(
            f"Пост одобрен (ID: {post_id})\nГде публикуем?",
            reply_markup=platform_keyboard(post_id),
        )
    await callback.answer()


# ── Platform selection → Time selection ─────────────────────────────────────

@router.callback_query(F.data.startswith("pub_platform:"))
async def on_platform_select(callback: CallbackQuery):
    """Platform selected → show time selection."""
    parts = callback.data.split(":")
    platform = parts[1]
    post_id = parts[2]

    draft = DraftManager.get_draft(post_id)
    if not draft:
        await callback.answer("Черновик не найден", show_alert=True)
        return

    # Store selected platforms
    if platform == "all":
        platforms = list(get_all_publishers().keys())
    else:
        platforms = [platform]

    DraftManager.update_draft(post_id, platforms=platforms)

    platform_labels = []
    for p in platforms:
        pub = get_publisher(p)
        platform_labels.append(f"{pub.emoji} {pub.label}" if pub else p)

    await callback.message.edit_text(
        f"Платформы: {', '.join(platform_labels)}\n"
        f"Когда публикуем?",
        reply_markup=time_keyboard(post_id),
    )
    await callback.answer()


# ── Time selection → Publish or Schedule ────────────────────────────────────

@router.callback_query(F.data.startswith("pub_time:"))
async def on_time_select(callback: CallbackQuery):
    """Time selected → publish now or schedule."""
    parts = callback.data.split(":")
    time_key = parts[1]
    post_id = parts[2]

    draft = DraftManager.get_draft(post_id)
    if not draft:
        await callback.answer("Черновик не найден", show_alert=True)
        return

    platforms = draft.get("platforms", ["linkedin"])
    publish_at = get_schedule_time(time_key)

    if time_key == "now":
        # Publish immediately
        await callback.answer("Публикую...")
        await callback.message.edit_text("⏳ Публикую...")
        await _do_publish(callback, post_id, draft, platforms)
    else:
        # Schedule for later
        PostScheduler.schedule(post_id, platforms, publish_at)
        DraftManager.update_draft(
            post_id, status="scheduled", scheduled_at=publish_at.isoformat()
        )

        platform_labels = []
        for p in platforms:
            pub = get_publisher(p)
            platform_labels.append(f"{pub.emoji} {pub.label}" if pub else p)

        await callback.message.edit_text(
            f"📅 Запланировано!\n\n"
            f"Платформы: {', '.join(platform_labels)}\n"
            f"Время: {publish_at.strftime('%H:%M %d.%m.%Y')} UTC\n"
            f"Тема: {draft.get('topic', '?')[:40]}\n\n"
            f"Посмотреть очередь: /schedule"
        )
        await callback.answer("Запланировано!")


async def _do_publish(callback: CallbackQuery, post_id: str, draft: dict, platforms: list[str]):
    """Execute publishing to all selected platforms with content adaptation."""
    results = []
    base_text = draft["text"]
    image_path = draft.get("image_path", "")

    # Adapt content for each platform (non-blocking)
    adapted = {}
    if len(platforms) > 1:
        try:
            import asyncio
            from ...tools.content_adapter import adapt_for_all_platforms
            adapted = await asyncio.to_thread(adapt_for_all_platforms, base_text)
        except Exception as e:
            logger.warning(f"Content adaptation failed, using original: {e}")

    for platform_name in platforms:
        pub = get_publisher(platform_name)
        if not pub:
            results.append(f"❌ {platform_name}: неизвестная платформа")
            continue

        # Use adapted text if available, otherwise original
        text = adapted.get(platform_name, base_text)

        try:
            if platform_name == "telegram" and hasattr(pub, 'publish'):
                # Telegram publisher needs bot instance
                result = await pub.publish(text, image_path, bot=callback.bot)
            else:
                result = await pub.publish(text, image_path)
            results.append(f"✅ {pub.emoji} {pub.label}: {result[:100]}")
            circuit_breaker.record_success()
        except Exception as e:
            results.append(f"❌ {pub.emoji} {pub.label}: {str(e)[:100]}")
            circuit_breaker.record_failure()
            logger.error(f"Publish to {platform_name} failed: {e}", exc_info=True)

    DraftManager.update_draft(post_id, status="published")

    # Auto mark_done in content calendar
    if draft.get("calendar_entry_id"):
        try:
            from ...content_calendar import mark_done
            mark_done(draft["calendar_entry_id"], post_id=post_id)
        except Exception as e:
            logger.warning(f"Failed to mark calendar entry done: {e}")

    await callback.message.edit_text(
        "Результаты публикации:\n\n" + "\n".join(results)
    )

    # Show feedback buttons after publish
    await callback.message.answer(
        "Хочешь дать обратную связь?",
        reply_markup=feedback_keyboard(post_id),
    )


# ── Rejection flow ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("reject:"))
async def on_reject(callback: CallbackQuery):
    post_id = callback.data.split(":")[1]
    draft = DraftManager.get_draft(post_id)
    if not draft:
        await callback.answer("Черновик не найден", show_alert=True)
        return

    await callback.message.edit_reply_markup(
        reply_markup=reject_reasons_keyboard(post_id)
    )
    await callback.answer("Выберите причину")


@router.callback_query(F.data.startswith("reject_reason:"))
async def on_reject_reason(callback: CallbackQuery):
    parts = callback.data.split(":")
    reason = parts[1]
    post_id = parts[2]

    reason_labels = {
        "off_topic": "не по теме",
        "bad_text": "плохой текст",
        "wrong_tone": "не тот тон",
        "wrong_length": "неправильная длина",
        "other": "другое",
    }

    DraftManager.update_draft(post_id, status="rejected", reject_reason=reason)

    if reason == "other":
        DraftManager.set_editing(callback.from_user.id, post_id)
        await callback.message.edit_text(
            "Напиши, что именно не так — я учту в следующий раз."
        )
    else:
        await callback.message.edit_text(
            f"❌ Отклонено: {reason_labels.get(reason, reason)}\n"
            f"Я учту это для будущих постов."
        )

    await callback.answer()


# ── Regenerate ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("regen:"))
async def on_regenerate(callback: CallbackQuery):
    post_id = callback.data.split(":")[1]
    draft = DraftManager.get_draft(post_id)
    if not draft:
        await callback.answer("Черновик не найден", show_alert=True)
        return

    if circuit_breaker.is_open:
        await callback.answer("Circuit breaker активен", show_alert=True)
        return

    await callback.answer("Переделываю...")
    await callback.message.edit_text(f"🔄 Переделываю пост: {draft['topic'][:40]}...")

    try:
        new_text = await AgentBridge.run_generate_post(
            topic=draft["topic"], author=draft.get("author", "kristina")
        )
        circuit_breaker.record_success()

        image_path = ""
        try:
            image_path = await generate_image_via_pipeline(draft["topic"], new_text)
        except Exception as e:
            logger.warning(f"Image regen failed: {e}")

        DraftManager.update_draft(
            post_id, text=new_text, image_path=image_path or "", status="pending"
        )

        for chunk in format_for_telegram(new_text):
            await callback.message.answer(chunk)

        if image_path:
            try:
                from aiogram.types import FSInputFile
                await callback.message.answer_photo(
                    FSInputFile(image_path), caption="Картинка для поста"
                )
            except Exception as e:
                logger.warning(f"Failed to send regen image: {e}")

        author_label = AUTHORS.get(draft.get("author", "kristina"), {}).get("label", "?")
        await callback.message.answer(
            f"Пост переделан (ID: {post_id})\n"
            f"Автор: {author_label} | Бренд: {draft.get('brand', 'sborka')}\n"
            f"Что делаем?",
            reply_markup=approval_keyboard(post_id),
        )

    except Exception as e:
        circuit_breaker.record_failure()
        logger.error(f"Regeneration error: {e}", exc_info=True)
        await callback.message.edit_text(
            f"Ошибка: {str(e)[:200]}",
            reply_markup=approval_keyboard(post_id),
        )


# ── Edit mode ───────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("edit:"))
async def on_edit(callback: CallbackQuery):
    post_id = callback.data.split(":")[1]
    draft = DraftManager.get_draft(post_id)
    if not draft:
        await callback.answer("Черновик не найден", show_alert=True)
        return

    DraftManager.set_editing(callback.from_user.id, post_id)
    await callback.message.edit_text(
        f"✏️ Режим редактирования (пост {post_id})\n\n"
        "Напиши правки текстом — я переделаю пост с их учётом.\n"
        "Примеры:\n"
        "• «Сделай короче»\n"
        "• «Добавь больше конкретики»\n"
        "• «Смени тон на более формальный»"
    )
    await callback.answer()


# ── Author change ───────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("set_author:"))
async def on_set_author(callback: CallbackQuery):
    parts = callback.data.split(":")
    author_key = parts[1]
    post_id = parts[2]

    if author_key == "tim_personal":
        DraftManager.update_draft(post_id, author="tim", brand="personal")
        label = "Тим (личный бренд)"
    else:
        DraftManager.update_draft(post_id, author=author_key, brand="sborka")
        label = AUTHORS.get(author_key, {}).get("label", author_key)

    await callback.message.edit_text(
        f"Автор изменён: {label}\nЧто делаем?",
        reply_markup=approval_keyboard(post_id),
    )
    await callback.answer(f"Автор: {label}")


# ── Back ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("back:"))
async def on_back(callback: CallbackQuery):
    post_id = callback.data.split(":")[1]
    DraftManager.clear_editing(callback.from_user.id)
    await callback.message.edit_reply_markup(
        reply_markup=approval_keyboard(post_id)
    )
    await callback.answer()


# ── Post-publish feedback ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("fb_post:"))
async def on_feedback_post(callback: CallbackQuery):
    """Feedback on THIS specific published post."""
    post_id = callback.data.split(":")[1]
    draft = DraftManager.get_draft(post_id)
    if not draft:
        await callback.answer("Пост не найден", show_alert=True)
        return

    DraftManager.set_feedback(callback.from_user.id, post_id, "post")
    await callback.message.edit_text(
        f"✏️ Правки к посту (ID: {post_id})\n\n"
        "Напиши, что не так с этим постом — Юки переделает его с учётом правок.\n"
        "Примеры:\n"
        "• «Слишком длинно, сократи»\n"
        "• «Тон слишком менторский»\n"
        "• «Добавь конкретный кейс»"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("fb_future:"))
async def on_feedback_future(callback: CallbackQuery):
    """General feedback for future posts."""
    post_id = callback.data.split(":")[1]

    DraftManager.set_feedback(callback.from_user.id, post_id, "future")
    await callback.message.edit_text(
        "📝 Фидбек на будущее\n\n"
        "Напиши общие пожелания по стилю, тону, структуре — "
        "Юки запомнит и будет учитывать в следующих постах.\n"
        "Примеры:\n"
        "• «Меньше советов, больше историй»\n"
        "• «Не поучай читателя»\n"
        "• «Всегда заканчивай вопросом»"
    )
    await callback.answer()


# ── CS-001: On-demand image generation ─────────────────────────────────────

@router.callback_query(F.data.startswith("gen_image:"))
async def on_gen_image(callback: CallbackQuery):
    """Generate image on demand when user presses [С картинкой]."""
    post_id = callback.data.split(":")[1]
    draft = DraftManager.get_draft(post_id)
    if not draft:
        await callback.answer("Черновик не найден", show_alert=True)
        return

    await callback.answer("Генерирую картинку...")
    await callback.message.edit_text(f"🎨 Генерирую картинку для: {draft['topic'][:40]}...")

    try:
        image_path = await generate_image_via_pipeline(draft["topic"], draft["text"])

        if not image_path:
            await callback.message.edit_text(
                "Не удалось сгенерировать картинку.",
                reply_markup=post_ready_keyboard(post_id),
            )
            return

        DraftManager.update_draft(post_id, image_path=image_path)

        from aiogram.types import FSInputFile
        await callback.message.answer_photo(
            FSInputFile(image_path), caption="Картинка для поста"
        )
        await callback.message.answer(
            f"Пост с картинкой (ID: {post_id})\nЧто делаем?",
            reply_markup=approval_with_image_keyboard(post_id),
        )

    except Exception as e:
        logger.error(f"On-demand image generation error: {e}", exc_info=True)
        await callback.message.edit_text(
            f"Ошибка генерации: {str(e)[:200]}",
            reply_markup=post_ready_keyboard(post_id),
        )


# ── CS-003: Image regeneration with refinement ────────────────────────────

_image_regen_state: dict[int, str] = {}  # user_id → post_id


def is_in_image_regen_mode(user_id: int) -> bool:
    return user_id in _image_regen_state


def get_image_regen_post_id(user_id: int) -> str | None:
    return _image_regen_state.get(user_id)


def consume_image_regen_mode(user_id: int) -> str | None:
    return _image_regen_state.pop(user_id, None)


@router.callback_query(F.data.startswith("regen_image:"))
async def on_regen_image(callback: CallbackQuery):
    """Start image regeneration — ask user what to change."""
    post_id = callback.data.split(":")[1]
    draft = DraftManager.get_draft(post_id)
    if not draft:
        await callback.answer("Черновик не найден", show_alert=True)
        return

    _image_regen_state[callback.from_user.id] = post_id
    await callback.message.edit_text(
        f"🎨 Что изменить в картинке? (пост {post_id})\n\n"
        "Напиши текстом, например:\n"
        "• «Сделай ярче»\n"
        "• «Добавь стрелку вверх»\n"
        "• «Используй сцену с лестницей»"
    )
    await callback.answer()


# ── Calendar & Plan callbacks ──────────────────────────────────────────────


@router.callback_query(F.data.startswith("cal_gen:"))
async def on_cal_gen(callback: CallbackQuery):
    """Generate post from a calendar entry — populate preselect state and go."""
    entry_id = callback.data.split(":")[1]
    from ...content_calendar import get_entry_by_id
    entry = get_entry_by_id(entry_id)
    if not entry:
        await callback.answer("Запись не найдена", show_alert=True)
        return

    user_id = callback.from_user.id
    author = entry.get("author", "kristina")
    if author == "both":
        author = "kristina"  # Default to Kristina for "both"

    # Parse platform: "linkedin+threads" → first one for preselect
    raw_platform = entry.get("platform", "linkedin")
    platform = raw_platform.split("+")[0] if "+" in raw_platform else raw_platform
    if "+" in raw_platform:
        platform = "all"  # Multiple platforms → use all

    _preselect_state[user_id] = {
        "topic": entry.get("topic", ""),
        "author": author,
        "brand": entry.get("brand", "sborka"),
        "platform": platform,
        "calendar_entry_id": entry_id,
    }

    await _show_preselect_summary(callback, _preselect_state[user_id])


@router.callback_query(F.data.startswith("cal_skip:"))
async def on_cal_skip(callback: CallbackQuery):
    """Skip a calendar entry."""
    entry_id = callback.data.split(":")[1]
    from ...content_calendar import mark_skipped, get_entry_by_id
    entry = get_entry_by_id(entry_id)
    topic = entry.get("topic", "?")[:30] if entry else "?"

    mark_skipped(entry_id)
    await callback.message.edit_text(f"⏭ Пропущено: {topic}")
    await callback.answer("Пропущено")


@router.callback_query(F.data.startswith("cal_edit:"))
async def on_cal_edit(callback: CallbackQuery):
    """Enter calendar entry edit mode — next text message updates the topic."""
    entry_id = callback.data.split(":")[1]
    from ...content_calendar import get_entry_by_id
    entry = get_entry_by_id(entry_id)
    if not entry:
        await callback.answer("Запись не найдена", show_alert=True)
        return

    _calendar_edit_state[callback.from_user.id] = entry_id
    await callback.message.edit_text(
        f"✏️ Редактирование записи\n\n"
        f"Текущая тема: {entry.get('topic', '?')}\n\n"
        "Напиши новую тему:"
    )
    await callback.answer()


@router.callback_query(F.data == "plan_cal")
async def on_plan_cal(callback: CallbackQuery):
    """Show undone calendar entries for picking."""
    from ...content_calendar import get_today, get_overdue
    today = get_today()
    overdue = get_overdue()
    undone = [
        e for e in overdue + today
        if e.get("status") not in ("done", "skipped")
    ]

    if not undone:
        await callback.message.edit_text("📅 Нет активных записей в календаре.")
        await callback.answer()
        return

    await callback.message.edit_text(
        "📅 Выбери тему из календаря:",
        reply_markup=calendar_pick_keyboard(undone),
    )
    await callback.answer()


@router.callback_query(F.data == "plan_new")
async def on_plan_new(callback: CallbackQuery):
    """Start custom topic input mode."""
    _plan_custom_state.add(callback.from_user.id)
    await callback.message.edit_text(
        "✍️ Напиши тему для нового поста:"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("plan_pick:"))
async def on_plan_pick(callback: CallbackQuery):
    """User picked a calendar entry — populate preselect and show summary."""
    entry_id = callback.data.split(":")[1]
    from ...content_calendar import get_entry_by_id
    entry = get_entry_by_id(entry_id)
    if not entry:
        await callback.answer("Запись не найдена", show_alert=True)
        return

    user_id = callback.from_user.id
    author = entry.get("author", "kristina")
    if author == "both":
        author = "kristina"

    raw_platform = entry.get("platform", "linkedin")
    platform = "all" if "+" in raw_platform else raw_platform

    _preselect_state[user_id] = {
        "topic": entry.get("topic", ""),
        "author": author,
        "brand": entry.get("brand", "sborka"),
        "platform": platform,
        "calendar_entry_id": entry_id,
    }

    await _show_preselect_summary(callback, _preselect_state[user_id])


# ── Menu-first UX callbacks ─────────────────────────────────────────────


@router.callback_query(F.data.startswith("m_au:"))
async def on_menu_author(callback: CallbackQuery):
    """Author selected → show submenu + market suggests."""
    author = callback.data.split(":")[1]
    user_id = callback.from_user.id
    _menu_state[user_id] = {"author": author}

    # Load market topics (non-blocking, graceful fallback)
    topics = []
    try:
        from ...market_listener import get_today_topics
        topics = get_today_topics()[:3]
    except Exception:
        pass
    _menu_state[user_id]["market_topics"] = topics

    label = "👤 Тим" if author == "tim" else "👩 Кристина"
    text = f"{label} → СБОРКА\n\n"
    if topics:
        text += "💡 Горячие темы сегодня:\n"
        for i, t in enumerate(topics, 1):
            text += f"  {i}. {t[:60]}\n"
        text += "\nОтправь номер темы или выбери источник:"
    else:
        text += "Выбери источник темы:"

    await callback.message.edit_text(text, reply_markup=author_submenu_keyboard(author))
    await callback.answer()


@router.callback_query(F.data == "m_back")
async def on_menu_back(callback: CallbackQuery):
    """Back to start menu."""
    _menu_state.pop(callback.from_user.id, None)
    await callback.message.edit_text(
        "Юки Пак — Head of SMM, Zinin Corp 🎯\n\n"
        "Выбери автора — я подготовлю посты для всех платформ.",
        reply_markup=start_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "m_cal")
async def on_menu_calendar(callback: CallbackQuery):
    """Show calendar entries filtered by author from menu."""
    user_id = callback.from_user.id
    menu = _menu_state.get(user_id, {})
    author = menu.get("author", "kristina")

    from ...content_calendar import get_today, get_overdue
    today = get_today()
    overdue = get_overdue()
    undone = [
        e for e in overdue + today
        if e.get("status") not in ("done", "skipped")
        and (e.get("author") == author or e.get("author") == "both")
    ]

    if not undone:
        await callback.message.edit_text(
            f"📅 Нет активных записей для {'Тима' if author == 'tim' else 'Кристины'}.\n"
            "Напиши тему или выбери из другого автора.",
            reply_markup=author_submenu_keyboard(author),
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "📅 Выбери тему из календаря:",
        reply_markup=calendar_pick_keyboard(undone),
    )
    await callback.answer()


@router.callback_query(F.data == "m_topic")
async def on_menu_topic(callback: CallbackQuery):
    """Custom topic input from menu."""
    user_id = callback.from_user.id
    menu = _menu_state.get(user_id, {})
    author = menu.get("author", "kristina")

    _plan_custom_state.add(user_id)
    # Pre-fill preselect state with author from menu
    _preselect_state[user_id] = {
        "topic": "",
        "author": author,
        "brand": "sborka",
    }
    await callback.message.edit_text("✍️ Напиши тему для нового поста:")
    await callback.answer()


@router.callback_query(F.data == "m_cal_view")
async def on_menu_cal_view(callback: CallbackQuery):
    """Delegate to /calendar logic."""
    from ...content_calendar import format_today_plan, format_week_plan
    today_text = format_today_plan()
    week_text = format_week_plan()
    await callback.message.edit_text(f"{today_text}\n\n{week_text}")
    await callback.answer()


@router.callback_query(F.data == "m_status")
async def on_menu_status(callback: CallbackQuery):
    """Quick status from menu."""
    from ...activity_tracker import get_all_statuses, get_agent_task_count

    statuses = get_all_statuses()
    smm_status = statuses.get("smm", {})
    tasks_24h = get_agent_task_count("smm", hours=24)
    status_emoji = {"working": "🟢", "idle": "⚪", "queued": "🟡"}.get(
        smm_status.get("status", "idle"), "⚪"
    )
    await callback.message.edit_text(
        f"Юки — статус\n\n"
        f"{status_emoji} {smm_status.get('status', 'idle')}\n"
        f"📝 Задач за 24ч: {tasks_24h}\n"
        f"📋 Черновиков: {DraftManager.active_count()}\n",
        reply_markup=start_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "noop")
async def on_noop(callback: CallbackQuery):
    """No-op for disabled buttons."""
    await callback.answer("Уже опубликовано")


# ── Multi-platform publish callbacks ─────────────────────────────────────


def _get_last_published_platform(draft: dict) -> str:
    """Get the most recently published platform from draft."""
    for plat, status in draft.get("platform_status", {}).items():
        if status == "published":
            return plat
    return draft.get("platforms", ["linkedin"])[0] if draft.get("platforms") else "linkedin"


@router.callback_query(F.data.startswith("mp_pub:"))
async def on_mp_publish(callback: CallbackQuery):
    """Publish to single platform."""
    parts = callback.data.split(":")
    plat_short, post_id = parts[1], parts[2]
    platform = PLAT_LONG.get(plat_short, plat_short)

    draft = DraftManager.get_draft(post_id)
    if not draft:
        await callback.answer("Черновик не найден", show_alert=True)
        return

    # Publish lock check
    if draft.get("platform_status", {}).get(platform) == "published":
        await callback.answer("Уже опубликовано")
        return

    await callback.answer("Публикую...")

    text = draft.get("platform_texts", {}).get(platform, draft["text"])
    image_path = draft.get("image_path", "")

    try:
        pub = get_publisher(platform)
        if not pub:
            await callback.message.answer(f"❌ Платформа {platform} не настроена")
            return

        if platform == "telegram" and hasattr(pub, 'publish'):
            result = await pub.publish(text, image_path, bot=callback.bot)
        else:
            result = await pub.publish(text, image_path)

        circuit_breaker.record_success()

        # Update platform status
        pstatus = dict(draft.get("platform_status", {}))
        pstatus[platform] = "published"
        DraftManager.update_draft(post_id, platform_status=pstatus, status="published")

        # Replace buttons → published lock
        await callback.message.edit_reply_markup(
            reply_markup=published_lock_keyboard(platform)
        )

        # Start post-publish rating flow: text rating
        DraftManager.update_draft(post_id, rating_step="text")
        emoji = PLAT_EMOJI.get(platform, "✅")
        await callback.message.answer(
            f"✅ Опубликовано в {emoji} {platform}!\n\n"
            f"✍️ Оцени качество текста:",
            reply_markup=rating_keyboard("r_txt", post_id),
        )

    except Exception as e:
        circuit_breaker.record_failure()
        logger.error(f"mp_pub error {platform}: {e}", exc_info=True)
        await callback.message.answer(f"❌ Ошибка публикации в {platform}: {str(e)[:200]}")


@router.callback_query(F.data.startswith("mp_imp:"))
async def on_mp_improve(callback: CallbackQuery):
    """Improve text for a specific platform."""
    parts = callback.data.split(":")
    plat_short, post_id = parts[1], parts[2]
    platform = PLAT_LONG.get(plat_short, plat_short)

    DraftManager.set_editing(callback.from_user.id, post_id)
    await callback.message.edit_text(
        f"✏️ Улучшение текста для {PLAT_EMOJI.get(platform, '')} {platform}\n\n"
        "Напиши правки текстом:"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("mp_sch:"))
async def on_mp_schedule(callback: CallbackQuery):
    """Schedule for a specific platform."""
    parts = callback.data.split(":")
    plat_short, post_id = parts[1], parts[2]
    platform = PLAT_LONG.get(plat_short, plat_short)

    draft = DraftManager.get_draft(post_id)
    if not draft:
        await callback.answer("Черновик не найден", show_alert=True)
        return

    DraftManager.update_draft(post_id, platforms=[platform])
    await callback.message.edit_text(
        f"📅 Планирование для {PLAT_EMOJI.get(platform, '')} {platform}\nКогда?",
        reply_markup=time_keyboard(post_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("mp_rm:"))
async def on_mp_remove(callback: CallbackQuery):
    """Remove a platform variant."""
    parts = callback.data.split(":")
    plat_short, post_id = parts[1], parts[2]
    platform = PLAT_LONG.get(plat_short, plat_short)

    draft = DraftManager.get_draft(post_id)
    if not draft:
        await callback.answer("Черновик не найден", show_alert=True)
        return

    pstatus = dict(draft.get("platform_status", {}))
    pstatus[platform] = "removed"
    DraftManager.update_draft(post_id, platform_status=pstatus)

    await callback.message.edit_text(f"❌ {platform} убрана")
    await callback.answer("Убрано")


@router.callback_query(F.data.startswith("mp_all:"))
async def on_mp_publish_all(callback: CallbackQuery):
    """Publish ALL pending platforms at once."""
    post_id = callback.data.split(":")[1]
    draft = DraftManager.get_draft(post_id)
    if not draft:
        await callback.answer("Черновик не найден", show_alert=True)
        return

    await callback.answer("Публикую всё...")

    results = []
    pstatus = dict(draft.get("platform_status", {}))
    image_path = draft.get("image_path", "")

    for platform, status in list(pstatus.items()):
        if status != "pending":
            continue

        text = draft.get("platform_texts", {}).get(platform, draft["text"])
        try:
            pub = get_publisher(platform)
            if not pub:
                results.append(f"❌ {platform}: не настроена")
                continue

            if platform == "telegram" and hasattr(pub, 'publish'):
                result = await pub.publish(text, image_path, bot=callback.bot)
            else:
                result = await pub.publish(text, image_path)

            pstatus[platform] = "published"
            emoji = PLAT_EMOJI.get(platform, "✅")
            results.append(f"✅ {emoji} {platform}")
            circuit_breaker.record_success()
        except Exception as e:
            results.append(f"❌ {platform}: {str(e)[:80]}")
            circuit_breaker.record_failure()
            logger.error(f"mp_all publish {platform}: {e}", exc_info=True)

    DraftManager.update_draft(post_id, platform_status=pstatus, status="published", rating_step="text")

    await callback.message.edit_text(
        "Результаты:\n" + "\n".join(results)
    )

    # Start post-publish rating flow
    await callback.message.answer(
        "✍️ Оцени качество текста:",
        reply_markup=rating_keyboard("r_txt", post_id),
    )


# ── Post-publish rating flow ─────────────────────────────────────────────


@router.callback_query(F.data.startswith("r_txt:"))
async def on_rate_text(callback: CallbackQuery):
    """Rate text 1-5 → offer image."""
    parts = callback.data.split(":")
    score = int(parts[1])
    post_id = parts[2]

    draft = DraftManager.get_draft(post_id)
    if not draft:
        await callback.answer("Не найдено")
        return

    ratings = dict(draft.get("ratings", {}))
    ratings["text"] = score
    DraftManager.update_draft(post_id, ratings=ratings, rating_step="image_offer")

    platform = _get_last_published_platform(draft)
    # Offer image for linkedin and telegram (threads has no image API support)
    if platform in ("linkedin", "telegram"):
        await callback.message.edit_text(
            f"Оценка текста: {'⭐' * score} — записано!\n\n🖼 Добавить картинку к посту?",
            reply_markup=image_offer_keyboard(post_id),
        )
    else:
        # Skip image, go to overall
        DraftManager.update_draft(post_id, rating_step="overall")
        await callback.message.edit_text(
            f"Оценка текста: {'⭐' * score}\n\n📊 Оцени пост в целом:",
            reply_markup=rating_keyboard("r_ovr", post_id),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("pp_img:"))
async def on_pp_generate_image(callback: CallbackQuery):
    """Generate image for published post."""
    post_id = callback.data.split(":")[1]
    draft = DraftManager.get_draft(post_id)
    if not draft:
        await callback.answer("Не найдено")
        return

    DraftManager.update_draft(post_id, rating_step="image_gen")
    await callback.answer("Генерирую...")
    await callback.message.edit_text("🎨 Генерирую картинку...")

    try:
        image_path = await generate_image_via_pipeline(draft["topic"], draft["text"])
        if image_path:
            DraftManager.update_draft(post_id, image_path=image_path)
            from aiogram.types import FSInputFile
            await callback.message.answer_photo(FSInputFile(image_path), caption="🖼 Картинка для поста")
            await callback.message.answer(
                "Что делаем с картинкой?",
                reply_markup=image_review_keyboard(post_id),
            )
        else:
            DraftManager.update_draft(post_id, rating_step="overall")
            await callback.message.answer(
                "Не удалось сгенерировать. Оцени пост:",
                reply_markup=rating_keyboard("r_ovr", post_id),
            )
    except Exception as e:
        logger.error(f"pp_img error: {e}", exc_info=True)
        DraftManager.update_draft(post_id, rating_step="overall")
        await callback.message.answer(
            f"Ошибка: {str(e)[:150]}\n\nОцени пост:",
            reply_markup=rating_keyboard("r_ovr", post_id),
        )


@router.callback_query(F.data.startswith("pp_skip:"))
async def on_pp_skip_image(callback: CallbackQuery):
    """Skip image → go to overall rating."""
    post_id = callback.data.split(":")[1]
    DraftManager.update_draft(post_id, rating_step="overall")
    await callback.message.edit_text(
        "📊 Оцени пост в целом:",
        reply_markup=rating_keyboard("r_ovr", post_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pp_ok:"))
async def on_pp_accept_image(callback: CallbackQuery):
    """Accept image → rate image → overall."""
    post_id = callback.data.split(":")[1]
    DraftManager.update_draft(post_id, rating_step="image_rate")
    await callback.message.edit_text(
        "🖼 Оцени качество картинки:",
        reply_markup=rating_keyboard("r_img", post_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pp_redo:"))
async def on_pp_redo_image(callback: CallbackQuery):
    """Redo image → regenerate."""
    post_id = callback.data.split(":")[1]
    # Reuse pp_img logic — override callback data
    callback.data = f"pp_img:{post_id}"
    await on_pp_generate_image(callback)


@router.callback_query(F.data.startswith("pp_fb:"))
async def on_pp_image_feedback(callback: CallbackQuery):
    """User wants to refine image with text feedback."""
    post_id = callback.data.split(":")[1]
    DraftManager.set_image_feedback(callback.from_user.id, post_id)
    await callback.message.edit_text(
        "✏️ Напиши, что изменить в картинке:\n\n"
        "Примеры:\n"
        "• «Сделай ярче и проще»\n"
        "• «Используй сцену с лестницей»\n"
        "• «Больше контраста»"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pp_no:"))
async def on_pp_reject_image(callback: CallbackQuery):
    """Reject image → skip to overall (image_score=0)."""
    post_id = callback.data.split(":")[1]
    ratings = dict(DraftManager.get_draft(post_id).get("ratings", {})) if DraftManager.get_draft(post_id) else {}
    ratings["image"] = 0
    DraftManager.update_draft(post_id, ratings=ratings, rating_step="overall", image_path="")
    await callback.message.edit_text(
        "📊 Оцени пост в целом:",
        reply_markup=rating_keyboard("r_ovr", post_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("r_img:"))
async def on_rate_image(callback: CallbackQuery):
    """Rate image 1-5 → go to overall."""
    parts = callback.data.split(":")
    score = int(parts[1])
    post_id = parts[2]

    draft = DraftManager.get_draft(post_id)
    if not draft:
        await callback.answer("Не найдено")
        return

    ratings = dict(draft.get("ratings", {}))
    ratings["image"] = score
    DraftManager.update_draft(post_id, ratings=ratings, rating_step="overall")

    await callback.message.edit_text(
        f"Оценка картинки: {'⭐' * score}\n\n📊 Оцени пост в целом:",
        reply_markup=rating_keyboard("r_ovr", post_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("r_ovr:"))
async def on_rate_overall(callback: CallbackQuery):
    """Rate overall 1-5 → save ALL to RatingStore → show menu."""
    parts = callback.data.split(":")
    score = int(parts[1])
    post_id = parts[2]

    draft = DraftManager.get_draft(post_id)
    if not draft:
        await callback.answer("Не найдено")
        return

    ratings = dict(draft.get("ratings", {}))

    # Save to RatingStore
    try:
        from ..ratings import RatingStore
        RatingStore.record_rating(
            post_id=post_id,
            author=draft.get("author", "unknown"),
            brand=draft.get("brand", "sborka"),
            platform=_get_last_published_platform(draft),
            topic=draft.get("topic", ""),
            text_score=ratings.get("text", 0),
            image_score=ratings.get("image", 0),
            overall_score=score,
            image_feedback=draft.get("image_feedback_text", ""),
        )
    except Exception as e:
        logger.error(f"RatingStore error: {e}", exc_info=True)

    DraftManager.update_draft(post_id, rating_step="done")

    text_stars = "⭐" * ratings.get("text", 0) if ratings.get("text") else "—"
    img_stars = "⭐" * ratings.get("image", 0) if ratings.get("image") else "—"
    ovr_stars = "⭐" * score

    await callback.message.edit_text(
        f"📝 Оценки записаны!\n"
        f"Текст: {text_stars} | Картинка: {img_stars} | Общая: {ovr_stars}\n\n"
        f"Юки учтёт в будущих постах.",
        reply_markup=start_menu_keyboard(),
    )
    await callback.answer()
