"""Callback query handler — inline button presses for Yuki SMM bot."""

import asyncio
import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery

from ...telegram.bridge import AgentBridge
from ...telegram.formatters import format_for_telegram
from ..keyboards import approval_keyboard, reject_reasons_keyboard, confirm_publish_keyboard
from ..drafts import DraftManager
from ..image_gen import generate_image

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data.startswith("approve:"))
async def on_approve(callback: CallbackQuery):
    """Approve post → confirm before publishing."""
    post_id = callback.data.split(":")[1]
    draft = DraftManager.get_draft(post_id)
    if not draft:
        await callback.answer("Черновик не найден", show_alert=True)
        return

    await callback.message.edit_reply_markup(
        reply_markup=confirm_publish_keyboard(post_id)
    )
    await callback.answer("Подтвердите публикацию")


@router.callback_query(F.data.startswith("confirm_pub:"))
async def on_confirm_publish(callback: CallbackQuery):
    """Confirmed publish → send to LinkedIn."""
    post_id = callback.data.split(":")[1]
    draft = DraftManager.get_draft(post_id)
    if not draft:
        await callback.answer("Черновик не найден", show_alert=True)
        return

    await callback.answer("Публикую...")
    await callback.message.edit_text("⏳ Публикую в LinkedIn...")

    try:
        result = await AgentBridge.run_linkedin_publish(
            text=draft["text"],
            image_path=draft.get("image_path", ""),
        )
        DraftManager.update_draft(post_id, status="published")
        await callback.message.edit_text(f"✅ ОПУБЛИКОВАНО\n\n{result[:500]}")
    except Exception as e:
        logger.error(f"Publish failed: {e}", exc_info=True)
        await callback.message.edit_text(
            f"❌ Ошибка публикации: {str(e)[:200]}",
            reply_markup=approval_keyboard(post_id),
        )


@router.callback_query(F.data.startswith("reject:"))
async def on_reject(callback: CallbackQuery):
    """Reject post → show reason selection."""
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
    """Record rejection with reason."""
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
        # Enter edit mode to get custom feedback
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


@router.callback_query(F.data.startswith("regen:"))
async def on_regenerate(callback: CallbackQuery):
    """Regenerate post with same topic."""
    post_id = callback.data.split(":")[1]
    draft = DraftManager.get_draft(post_id)
    if not draft:
        await callback.answer("Черновик не найден", show_alert=True)
        return

    await callback.answer("Переделываю...")
    await callback.message.edit_text(f"🔄 Переделываю пост: {draft['topic'][:40]}...")

    try:
        new_text = await AgentBridge.run_generate_post(
            topic=draft["topic"], author=draft.get("author", "kristina")
        )

        # Generate new image
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

        await callback.message.answer(
            f"Пост переделан (ID: {post_id}). Что делаем?",
            reply_markup=approval_keyboard(post_id),
        )

    except Exception as e:
        logger.error(f"Regeneration error: {e}", exc_info=True)
        await callback.message.edit_text(
            f"Ошибка: {str(e)[:200]}",
            reply_markup=approval_keyboard(post_id),
        )


@router.callback_query(F.data.startswith("edit:"))
async def on_edit(callback: CallbackQuery):
    """Enter edit mode — next text message will be treated as feedback."""
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


@router.callback_query(F.data.startswith("back:"))
async def on_back(callback: CallbackQuery):
    """Return to main approval keyboard."""
    post_id = callback.data.split(":")[1]
    DraftManager.clear_editing(callback.from_user.id)
    await callback.message.edit_reply_markup(
        reply_markup=approval_keyboard(post_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("platform:"))
async def on_platform_select(callback: CallbackQuery):
    """Platform selection."""
    parts = callback.data.split(":")
    platform = parts[1]
    post_id = parts[2]
    DraftManager.update_draft(post_id, platform=platform)
    await callback.message.edit_reply_markup(
        reply_markup=approval_keyboard(post_id)
    )
    await callback.answer(f"Платформа: {platform}")
