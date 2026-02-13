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
from ..keyboards import approval_keyboard, post_ready_keyboard, approval_with_image_keyboard, final_choice_keyboard
from ..image_gen import generate_image, generate_image_with_refinement
from ..safety import circuit_breaker
from ..publishers import AUTHORS
from .commands import _parse_author_topic

logger = logging.getLogger(__name__)
router = Router()

_chat_contexts: dict[int, list[dict]] = {}
MAX_CONTEXT = 20


def _get_context(user_id: int) -> list[dict]:
    """Get per-user chat context (isolated between users)."""
    if user_id not in _chat_contexts:
        _chat_contexts[user_id] = []
    return _chat_contexts[user_id]

# Patterns that trigger post generation
POST_TRIGGERS = re.compile(
    r"^(сделай|напиши|создай|генерируй|подготовь)\s+(пост|контент|статью)",
    re.IGNORECASE,
)

# Patterns that trigger podcast generation
PODCAST_TRIGGERS = re.compile(
    r"^(сделай|запиши|создай|генерируй|подготовь)\s+(подкаст|выпуск|эпизод)",
    re.IGNORECASE,
)


@router.message(F.text)
async def handle_text(message: Message):
    user_text = message.text.strip()
    if not user_text:
        return

    user_id = message.from_user.id

    # CS-003: Check if user is in image regeneration mode
    from .callbacks import is_in_image_regen_mode, consume_image_regen_mode
    if is_in_image_regen_mode(user_id):
        post_id = consume_image_regen_mode(user_id)
        if post_id:
            await _handle_image_refinement(message, post_id, user_text)
            return

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

    # Check for natural language podcast triggers
    if PODCAST_TRIGGERS.search(user_text):
        topic = PODCAST_TRIGGERS.sub("", user_text).strip()
        if not topic:
            topic = user_text
        from .commands import _generate_podcast_flow
        await _generate_podcast_flow(message, topic)
        return

    # Check for natural language post triggers
    if POST_TRIGGERS.search(user_text):
        author, brand, topic, platform = _parse_author_topic(user_text)
        if not topic:
            topic = POST_TRIGGERS.sub("", user_text).strip()
        if not topic:
            topic = user_text

        if platform:
            # Platform detected from text → generate directly
            await _generate_post_flow(message, topic, author, brand, platform=platform)
        else:
            # No platform detected → show pre-select keyboard
            from .callbacks import _preselect_state
            from ..keyboards import preselect_keyboard
            _preselect_state[message.from_user.id] = {
                "topic": topic, "author": author, "brand": brand,
            }
            await message.answer(
                f"📝 Пост: {topic}\n\nВыберите автора и платформу:",
                reply_markup=preselect_keyboard(author, brand),
            )
        return

    # Default: send to Yuki agent as free conversation
    user_ctx = _get_context(user_id)
    user_ctx.append({"role": "user", "text": user_text})

    status = await message.answer("📱 Юки думает...")
    stop = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(message, stop))

    context_str = _format_context(user_ctx[-MAX_CONTEXT:])

    try:
        response = await AgentBridge.send_to_agent(
            message=user_text,
            agent_name="smm",
            chat_context=context_str,
            bot=message.bot,
            chat_id=message.chat.id,
        )
        user_ctx.append({"role": "assistant", "text": response})

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
    """Handle text input when user is editing a draft. CS-004: iteration tracking."""
    draft = DraftManager.get_draft(post_id)
    if not draft:
        DraftManager.clear_editing(message.from_user.id)
        await message.answer("Черновик не найден. Режим редактирования сброшен.")
        return

    DraftManager.clear_editing(message.from_user.id)

    # CS-004: Check iteration limits
    iteration = draft.get("iteration", 1)
    max_iterations = draft.get("max_iterations", 3)

    if iteration >= max_iterations:
        await message.answer(
            f"⚠️ Достигнут лимит правок ({max_iterations} итераций).\n"
            f"Выбери финальное действие:",
            reply_markup=final_choice_keyboard(post_id),
        )
        return

    # CS-004: Track feedback history
    feedback_history = draft.get("feedback_history", [])
    feedback_history.append(feedback)

    status = await message.answer(f"✏️ Переделываю пост с учётом правок (итерация {iteration + 1}/{max_iterations})...")
    stop = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(message, stop))

    try:
        # Include feedback history as context for better iterations
        history_context = ""
        if len(feedback_history) > 1:
            prev = "\n".join(f"- {fb}" for fb in feedback_history[:-1])
            history_context = f"\nПредыдущие правки (уже учтены):\n{prev}\n"

        new_text = await AgentBridge.send_to_agent(
            message=(
                f"Переделай этот пост с учётом правок.\n\n"
                f"Текущий пост:\n{draft['text'][:1500]}\n\n"
                f"Правки от Тима: {feedback}\n"
                f"{history_context}"
                f"Тема: {draft['topic']}\n"
                f"Верни ТОЛЬКО текст поста, без комментариев."
            ),
            agent_name="smm",
        )

        DraftManager.update_draft(
            post_id,
            text=new_text,
            feedback=feedback,
            iteration=iteration + 1,
            feedback_history=feedback_history,
        )

        for chunk in format_for_telegram(new_text):
            await message.answer(chunk)

        # CS-004: At max iterations, show final choice keyboard
        if iteration + 1 >= max_iterations:
            await message.answer(
                f"Пост обновлён (ID: {post_id}). Лимит правок ({max_iterations}) достигнут.\n"
                f"Финальное решение:",
                reply_markup=final_choice_keyboard(post_id),
            )
        else:
            await message.answer(
                f"Пост обновлён (ID: {post_id}, итерация {iteration + 1}/{max_iterations}). Что делаем?",
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


async def _generate_post_flow(
    message: Message,
    topic: str,
    author: str = "kristina",
    brand: str = "sborka",
    platform: str = "linkedin",
):
    """Generate a post from natural language trigger. CS-001: text first, image deferred."""
    if circuit_breaker.is_open:
        await message.answer("Circuit breaker активен. Подожди или /health.")
        return

    platform_labels = {
        "linkedin": "💼 LinkedIn", "threads": "🧵 Threads",
        "telegram": "📱 Telegram", "all": "📢 Все",
    }
    author_label = AUTHORS.get(author, {}).get("label", author)
    plat_label = platform_labels.get(platform, platform)
    status_msg = await message.answer(
        f"📱 Готовлю пост от {author_label} для {plat_label}: {topic[:40]}..."
    )
    stop = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(message, stop))

    try:
        post_text = await AgentBridge.run_generate_post(topic=topic, author=author)
        circuit_breaker.record_success()

        # Set platforms from pre-selection
        if platform == "all":
            platforms = ["linkedin", "threads", "telegram"]
        else:
            platforms = [platform]

        # CS-001: Text first, image deferred (no auto-generation)
        post_id = DraftManager.create_draft(
            topic=topic, text=post_text, author=author, brand=brand,
            platforms=platforms,
            image_path="",
        )

        for chunk in format_for_telegram(post_text):
            await message.answer(chunk)

        # CS-002: Use post_ready_keyboard with image choice
        await message.answer(
            f"Пост готов (ID: {post_id})\n"
            f"Автор: {author_label} | Платформа: {plat_label}\n"
            f"Что делаем?",
            reply_markup=post_ready_keyboard(post_id),
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


async def _handle_image_refinement(message: Message, post_id: str, refinement: str):
    """CS-003: Handle image refinement text input."""
    draft = DraftManager.get_draft(post_id)
    if not draft:
        await message.answer("Черновик не найден.")
        return

    status = await message.answer("🎨 Генерирую новую картинку с учётом пожеланий...")
    stop = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(message, stop))

    try:
        image_path = await asyncio.to_thread(
            generate_image_with_refinement, draft["topic"], draft["text"], refinement
        )

        if not image_path:
            await message.answer(
                "Не удалось сгенерировать картинку.",
                reply_markup=approval_with_image_keyboard(post_id),
            )
            return

        DraftManager.update_draft(post_id, image_path=image_path)

        from aiogram.types import FSInputFile
        await message.answer_photo(
            FSInputFile(image_path), caption="Обновлённая картинка"
        )
        await message.answer(
            f"Картинка обновлена (ID: {post_id}). Что делаем?",
            reply_markup=approval_with_image_keyboard(post_id),
        )

    except Exception as e:
        logger.error(f"Image refinement error: {e}", exc_info=True)
        await message.answer(f"Ошибка: {str(e)[:200]}")
    finally:
        stop.set()
        await typing_task
        try:
            await status.delete()
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
