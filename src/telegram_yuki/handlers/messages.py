"""Text message handler — routes to Юки (SMM) via AgentBridge."""

import asyncio
import logging
import re

from aiogram import Router, F
from aiogram.types import Message

from ...telegram.bridge import AgentBridge
from ...telegram.formatters import format_for_telegram
from ...telegram.handlers.commands import keep_typing
from ..drafts import DraftManager
from ..keyboards import approval_keyboard
from ..image_gen import generate_image
from ..safety import circuit_breaker
from ..publishers import AUTHORS
from .commands import _parse_author_topic

logger = logging.getLogger(__name__)
router = Router()

_chat_context: list[dict] = []
MAX_CONTEXT = 20

# Patterns that trigger post generation
POST_TRIGGERS = re.compile(
    r"^(сделай|напиши|создай|генерируй|подготовь)\s+(пост|контент|статью)",
    re.IGNORECASE,
)


@router.message(F.text)
async def handle_text(message: Message):
    user_text = message.text.strip()
    if not user_text:
        return

    user_id = message.from_user.id

    # Check if user is in feedback mode (post-publish)
    fb = DraftManager.get_feedback(user_id)
    if fb:
        post_id, mode = fb
        DraftManager.clear_feedback(user_id)
        if mode == "future":
            await _handle_future_feedback(message, post_id, user_text)
        else:
            await _handle_post_feedback(message, post_id, user_text)
        return

    # Check if user is editing a draft
    editing_id = DraftManager.get_editing(user_id)
    if editing_id:
        await _handle_edit_feedback(message, editing_id, user_text)
        return

    # Check for natural language post triggers
    if POST_TRIGGERS.search(user_text):
        author, brand, topic = _parse_author_topic(user_text)
        if not topic:
            topic = POST_TRIGGERS.sub("", user_text).strip()
        if not topic:
            topic = user_text
        await _generate_post_flow(message, topic, author, brand)
        return

    # Default: send to Yuki agent as free conversation
    _chat_context.append({"role": "user", "text": user_text})

    status = await message.answer("📱 Юки думает...")
    stop = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(message, stop))

    context_str = _format_context(_chat_context[-MAX_CONTEXT:])

    try:
        response = await AgentBridge.send_to_agent(
            message=user_text,
            agent_name="smm",
            chat_context=context_str,
            bot=message.bot,
            chat_id=message.chat.id,
        )
        _chat_context.append({"role": "assistant", "text": response})

        for chunk in format_for_telegram(response):
            await message.answer(chunk)

    except Exception as e:
        logger.error(f"Yuki message handler error: {e}", exc_info=True)
        await message.answer(f"Ошибка: {type(e).__name__}: {str(e)[:200]}")
    finally:
        stop.set()
        await typing_task
        try:
            await status.delete()
        except Exception:
            pass


async def _handle_post_feedback(message: Message, post_id: str, feedback: str):
    """Handle feedback on a specific published post — Yuki revises it."""
    draft = DraftManager.get_draft(post_id)
    if not draft:
        await message.answer("Пост не найден.")
        return

    status = await message.answer("✏️ Юки переделывает пост с учётом правок...")
    stop = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(message, stop))

    try:
        new_text = await AgentBridge.send_to_agent(
            message=(
                f"Переделай этот ОПУБЛИКОВАННЫЙ пост с учётом обратной связи.\n\n"
                f"Пост:\n{draft['text'][:1500]}\n\n"
                f"Обратная связь от Тима: {feedback}\n\n"
                f"Тема: {draft['topic']}\n"
                f"Верни ТОЛЬКО исправленный текст поста, без комментариев."
            ),
            agent_name="smm",
        )

        DraftManager.update_draft(post_id, text=new_text, feedback=feedback)

        for chunk in format_for_telegram(new_text):
            await message.answer(chunk)

        await message.answer(
            f"Пост переделан (ID: {post_id}). Что делаем?",
            reply_markup=approval_keyboard(post_id),
        )

    except Exception as e:
        logger.error(f"Post feedback error: {e}", exc_info=True)
        await message.answer(f"Ошибка: {str(e)[:200]}")
    finally:
        stop.set()
        await typing_task
        try:
            await status.delete()
        except Exception:
            pass


async def _handle_future_feedback(message: Message, post_id: str, feedback: str):
    """Handle general feedback for future posts — save to Yuki memory."""
    draft = DraftManager.get_draft(post_id)
    topic = draft.get("topic", "?") if draft else "?"

    try:
        import json
        from ...tools.smm_tools import YukiMemory

        memory_tool = YukiMemory()
        record = json.dumps({
            "type": "future_feedback",
            "feedback": feedback,
            "post_id": post_id,
            "topic": topic,
            "source": "telegram_inline",
        })
        memory_tool._run(action="record_feedback", data=record)

        await message.answer(
            f"📝 Записано! Юки учтёт в будущих постах:\n\n"
            f"«{feedback[:300]}»"
        )
    except Exception as e:
        logger.error(f"Future feedback save error: {e}", exc_info=True)
        await message.answer(f"Ошибка сохранения: {str(e)[:200]}")


async def _handle_edit_feedback(message: Message, post_id: str, feedback: str):
    """Handle text input when user is editing a draft."""
    draft = DraftManager.get_draft(post_id)
    if not draft:
        DraftManager.clear_editing(message.from_user.id)
        await message.answer("Черновик не найден. Режим редактирования сброшен.")
        return

    DraftManager.clear_editing(message.from_user.id)

    status = await message.answer(f"✏️ Переделываю пост с учётом правок...")
    stop = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(message, stop))

    try:
        new_text = await AgentBridge.send_to_agent(
            message=(
                f"Переделай этот пост с учётом правок.\n\n"
                f"Текущий пост:\n{draft['text'][:1500]}\n\n"
                f"Правки от Тима: {feedback}\n\n"
                f"Тема: {draft['topic']}\n"
                f"Верни ТОЛЬКО текст поста, без комментариев."
            ),
            agent_name="smm",
        )

        DraftManager.update_draft(post_id, text=new_text, feedback=feedback)

        for chunk in format_for_telegram(new_text):
            await message.answer(chunk)

        await message.answer(
            f"Пост обновлён (ID: {post_id}). Что делаем?",
            reply_markup=approval_keyboard(post_id),
        )

    except Exception as e:
        logger.error(f"Edit feedback error: {e}", exc_info=True)
        await message.answer(f"Ошибка: {str(e)[:200]}")
    finally:
        stop.set()
        await typing_task
        try:
            await status.delete()
        except Exception:
            pass


async def _generate_post_flow(message: Message, topic: str, author: str = "kristina", brand: str = "sborka"):
    """Generate a post from natural language trigger."""
    if circuit_breaker.is_open:
        await message.answer("Circuit breaker активен. Подожди или /health.")
        return

    author_label = AUTHORS.get(author, {}).get("label", author)
    status_msg = await message.answer(f"📱 Готовлю пост от {author_label}: {topic[:40]}...")
    stop = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(message, stop))

    try:
        post_text = await AgentBridge.run_generate_post(topic=topic, author=author)
        circuit_breaker.record_success()

        image_path = ""
        try:
            image_path = await asyncio.to_thread(generate_image, topic, post_text)
        except Exception as e:
            logger.warning(f"Image generation failed: {e}")

        post_id = DraftManager.create_draft(
            topic=topic, text=post_text, author=author, brand=brand,
            image_path=image_path or "",
        )

        for chunk in format_for_telegram(post_text):
            await message.answer(chunk)

        if image_path:
            try:
                from aiogram.types import FSInputFile
                await message.answer_photo(FSInputFile(image_path), caption="Картинка для поста")
            except Exception as e:
                logger.warning(f"Failed to send image: {e}")

        await message.answer(
            f"Пост готов (ID: {post_id})\n"
            f"Автор: {author_label} | Бренд: {brand}\n"
            f"Что делаем?",
            reply_markup=approval_keyboard(post_id),
        )

    except Exception as e:
        circuit_breaker.record_failure()
        logger.error(f"Post generation error: {e}", exc_info=True)
        await message.answer(f"Ошибка: {str(e)[:200]}")
    finally:
        stop.set()
        await typing_task
        try:
            await status_msg.delete()
        except Exception:
            pass


def _format_context(messages: list[dict]) -> str:
    lines = []
    for msg in messages:
        if msg["role"] == "user":
            lines.append(f"Тим: {msg['text']}")
        else:
            lines.append(f"Юки: {msg['text'][:800]}")
    return "\n".join(lines)
