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
    time_keyboard, author_keyboard,
)
from ..drafts import DraftManager
from ..image_gen import generate_image
from ..publishers import get_publisher, get_all_publishers, AUTHORS
from ..scheduler import PostScheduler, get_schedule_time
from ..safety import circuit_breaker

logger = logging.getLogger(__name__)
router = Router()


# ── Approval → Platform selection ───────────────────────────────────────────

@router.callback_query(F.data.startswith("approve:"))
async def on_approve(callback: CallbackQuery):
    """Approve post → show platform selection."""
    post_id = callback.data.split(":")[1]
    draft = DraftManager.get_draft(post_id)
    if not draft:
        await callback.answer("Черновик не найден", show_alert=True)
        return

    DraftManager.update_draft(post_id, status="approved")
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
    """Execute publishing to all selected platforms."""
    results = []
    text = draft["text"]
    image_path = draft.get("image_path", "")

    for platform_name in platforms:
        pub = get_publisher(platform_name)
        if not pub:
            results.append(f"❌ {platform_name}: неизвестная платформа")
            continue

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

    await callback.message.edit_text(
        "Результаты публикации:\n\n" + "\n".join(results)
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
            image_path = await asyncio.to_thread(
                generate_image, draft["topic"], new_text
            )
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
