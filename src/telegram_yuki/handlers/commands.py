"""Yuki SMM Telegram command handlers."""

import asyncio
import logging
import re

from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from ...telegram.bridge import AgentBridge
from ...telegram.formatters import format_for_telegram
from ...telegram.handlers.commands import run_with_typing
from ..keyboards import approval_keyboard
from ..drafts import DraftManager
from ..image_gen import generate_image

logger = logging.getLogger(__name__)
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Юки Пак — Head of SMM, Zinin Corp\n\n"
        "Привет, Тим! Я Юки, отвечаю за контент и SMM.\n\n"
        "Команды:\n"
        "/пост <тема> — Создать пост для LinkedIn\n"
        "/post <тема> — Алиас для /пост\n"
        "/status — Статус системы\n"
        "/linkedin — Статус LinkedIn\n"
        "/reflexion — Анализ фидбека\n"
        "/help — Справка\n\n"
        "Можешь просто написать тему — я пойму."
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Юки Пак — Head of SMM\n\n"
        "Генерация контента:\n"
        "/пост <тема> — Создать пост (LinkedIn)\n"
        "/post <тема> — Алиас\n\n"
        "Просто напиши тему — я создам пост.\n"
        'Примеры: "AI-агенты в бизнесе", "карьерный рост в IT"\n\n'
        "Статус:\n"
        "/status — Мой статус\n"
        "/linkedin — Статус LinkedIn-интеграции\n\n"
        "Обучение:\n"
        "/reflexion — Анализ фидбека за последнее время\n\n"
        "После генерации поста используй кнопки:\n"
        "✅ Опубликовать → LinkedIn\n"
        "❌ Отклонить → с указанием причины\n"
        "🔄 Переделать → новая версия\n"
        "✏️ Редактировать → напиши правки текстом"
    )


@router.message(Command(commands=["пост", "post"]))
async def cmd_post(message: Message):
    """Generate a post: /пост AI-агенты в бизнесе."""
    text = message.text or ""
    parts = text.split(maxsplit=1)
    topic = parts[1] if len(parts) > 1 else ""

    if not topic:
        await message.answer(
            "Формат: /пост <тема>\n\n"
            "Примеры:\n"
            "• /пост AI-агенты в бизнесе\n"
            "• /пост карьерный рост в IT\n"
            "• /post future of remote work"
        )
        return

    status_msg = await message.answer(f"📱 Юки готовит пост: {topic[:50]}... (30–60 сек)")

    stop = asyncio.Event()
    from ...telegram.handlers.commands import keep_typing
    typing_task = asyncio.create_task(keep_typing(message, stop))

    try:
        # Generate post text via CrewAI Yuki agent
        post_text = await AgentBridge.run_generate_post(
            topic=topic, author="kristina"
        )

        # Generate image (non-blocking, best-effort)
        image_path = ""
        try:
            image_path = await asyncio.to_thread(
                generate_image, topic, post_text
            )
        except Exception as e:
            logger.warning(f"Image generation failed: {e}")

        # Save as draft
        post_id = DraftManager.create_draft(
            topic=topic,
            text=post_text,
            author="kristina",
            platform="linkedin",
            image_path=image_path or "",
        )

        # Send post with approval keyboard
        for chunk in format_for_telegram(post_text):
            await message.answer(chunk)

        # Send image if generated
        if image_path:
            try:
                from aiogram.types import FSInputFile
                photo = FSInputFile(image_path)
                await message.answer_photo(photo, caption="Картинка для поста")
            except Exception as e:
                logger.warning(f"Failed to send image: {e}")

        # Send approval buttons
        await message.answer(
            f"Пост готов (ID: {post_id}). Что делаем?",
            reply_markup=approval_keyboard(post_id),
        )

    except Exception as e:
        logger.error(f"Post generation error: {e}", exc_info=True)
        await message.answer(f"Ошибка генерации: {type(e).__name__}: {str(e)[:200]}")
    finally:
        stop.set()
        await typing_task
        try:
            await status_msg.delete()
        except Exception:
            pass


@router.message(Command("status"))
async def cmd_status(message: Message):
    """Quick status — no LLM call."""
    from ...activity_tracker import get_all_statuses, get_agent_task_count

    statuses = get_all_statuses()
    smm_status = statuses.get("smm", {})
    tasks_24h = get_agent_task_count("smm", hours=24)

    status_emoji = {"working": "🟢", "idle": "⚪", "queued": "🟡"}.get(
        smm_status.get("status", "idle"), "⚪"
    )

    drafts_count = len(DraftManager._drafts)

    await message.answer(
        f"Юки Пак — SMM статус\n\n"
        f"{status_emoji} Статус: {smm_status.get('status', 'idle')}\n"
        f"📝 Задач за 24ч: {tasks_24h}\n"
        f"📋 Черновиков: {drafts_count}\n"
    )


@router.message(Command("linkedin"))
async def cmd_linkedin(message: Message):
    """Check LinkedIn integration status."""
    await run_with_typing(
        message,
        AgentBridge.run_linkedin_status(),
        "📱 Проверяю статус LinkedIn... (20–40 сек)",
    )


@router.message(Command("reflexion"))
async def cmd_reflexion(message: Message):
    """Run reflexion analysis on recent feedback."""
    await run_with_typing(
        message,
        AgentBridge.send_to_agent(
            message="Проанализируй весь фидбек за последнюю неделю. "
            "Какие паттерны ты видишь? Что улучшить в контенте? "
            "Дай конкретные рекомендации.",
            agent_name="smm",
        ),
        "🔍 Анализирую фидбек... (30–60 сек)",
    )
