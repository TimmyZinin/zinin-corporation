"""Yuki SMM Telegram command handlers."""

import asyncio
import logging
import os
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
from ..safety import circuit_breaker, autonomy
from ..publishers import AUTHORS, get_configured_publishers

logger = logging.getLogger(__name__)
router = Router()

# Author parsing from command text
_AUTHOR_RE = re.compile(
    r"\bот\s+(тима|кристины|kristina|tim)\b", re.IGNORECASE
)
_BRAND_RE = re.compile(
    r"\b(для личного бренда|личный бренд|personal)\b", re.IGNORECASE
)


def _parse_author_topic(text: str) -> tuple[str, str, str]:
    """Parse author, brand, and topic from command text.

    Returns (author, brand, topic).
    """
    author = "kristina"
    brand = "sborka"

    # Check for brand override first
    if _BRAND_RE.search(text):
        brand = "personal"
        author = "tim"
        text = _BRAND_RE.sub("", text)

    # Check for author override
    m = _AUTHOR_RE.search(text)
    if m:
        name = m.group(1).lower()
        if name in ("тима", "tim"):
            author = "tim"
        elif name in ("кристины", "kristina"):
            author = "kristina"
        text = _AUTHOR_RE.sub("", text)

    # Personal brand can only be Tim
    if brand == "personal":
        author = "tim"

    topic = text.strip()
    # Remove leading command
    if topic.startswith("/"):
        parts = topic.split(maxsplit=1)
        topic = parts[1] if len(parts) > 1 else ""

    return author, brand, topic.strip()


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Юки Пак — Head of SMM, Zinin Corp\n\n"
        "Привет, Тим! Я Юки, отвечаю за контент и SMM.\n\n"
        "Команды:\n"
        "/пост <тема> — Создать пост\n"
        "/пост от Тима <тема> — Пост от Тима\n"
        "/пост для личного бренда <тема> — Личный бренд\n"
        "/подкаст <тема> — Сгенерировать подкаст\n"
        "/status — Статус системы\n"
        "/health — Диагностика\n"
        "/linkedin — Статус LinkedIn\n"
        "/level — Уровень автономности\n"
        "/reflexion — Анализ фидбека\n"
        "/schedule — Запланированные посты\n"
        "/help — Справка\n\n"
        "Можешь просто написать тему — я пойму."
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Юки Пак — Head of SMM\n\n"
        "Генерация контента:\n"
        "/пост <тема> — Пост от Кристины (СБОРКА)\n"
        "/пост от Тима <тема> — Пост от Тима (СБОРКА)\n"
        "/пост для личного бренда <тема> — Тим (личный)\n"
        "/post <тема> — Алиас для /пост\n\n"
        "Подкасты:\n"
        "/подкаст <тема> — Сгенерировать выпуск подкаста\n"
        "/podcast <тема> — Алиас для /подкаст\n\n"
        "Авторы: Кристина и Тим → СБОРКА, только Тим → личный бренд\n\n"
        "Платформы при публикации:\n"
        "💼 LinkedIn, 📱 Telegram канал, 🧵 Threads\n"
        "📢 Все платформы — одновременно\n\n"
        "Расписание:\n"
        "После одобрения выбираешь когда публиковать:\n"
        "⚡ Сейчас, 🕐 Через 1ч, 🕒 Через 3ч, 🌅 Завтра\n"
        "/schedule — Посмотреть очередь\n\n"
        "Система:\n"
        "/status — Статус, /health — Диагностика\n"
        "/level — Автономность (manual/auto)\n"
        "/reflexion — Анализ фидбека\n\n"
        "Кнопки после генерации:\n"
        "✅ → выбор платформы → выбор времени → публикация\n"
        "❌ → причина → обучение\n"
        "🔄 → новая версия, ✏️ → правки текстом"
    )


@router.message(Command(commands=["пост", "post"]))
async def cmd_post(message: Message):
    """Generate a post: /пост от Тима AI-агенты в бизнесе."""
    text = message.text or ""
    author, brand, topic = _parse_author_topic(text)

    if not topic:
        await message.answer(
            "Формат: /пост <тема>\n\n"
            "Примеры:\n"
            "• /пост AI-агенты в бизнесе\n"
            "• /пост от Тима карьерный рост\n"
            "• /пост для личного бренда AI в 2026\n"
            "• /post future of remote work"
        )
        return

    # Circuit breaker check
    if circuit_breaker.is_open:
        await message.answer(
            f"Circuit breaker активен: {circuit_breaker.status}\n"
            "Слишком много ошибок. Подожди или напиши /health для диагностики."
        )
        return

    author_label = AUTHORS.get(author, {}).get("label", author)
    status_msg = await message.answer(
        f"📱 Юки готовит пост от {author_label}: {topic[:40]}... (30–60 сек)"
    )

    stop = asyncio.Event()
    from ...telegram.handlers.commands import keep_typing
    typing_task = asyncio.create_task(keep_typing(message, stop))

    try:
        post_text = await AgentBridge.run_generate_post(
            topic=topic, author=author
        )

        # Record success for circuit breaker
        circuit_breaker.record_success()

        # Generate image (non-blocking)
        image_path = ""
        try:
            image_path = await asyncio.to_thread(generate_image, topic, post_text)
        except Exception as e:
            logger.warning(f"Image generation failed: {e}")

        post_id = DraftManager.create_draft(
            topic=topic,
            text=post_text,
            author=author,
            brand=brand,
            image_path=image_path or "",
        )

        # Send post
        for chunk in format_for_telegram(post_text):
            await message.answer(chunk)

        if image_path:
            try:
                from aiogram.types import FSInputFile
                await message.answer_photo(
                    FSInputFile(image_path), caption="Картинка для поста"
                )
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
        await message.answer(f"Ошибка генерации: {type(e).__name__}: {str(e)[:200]}")
    finally:
        stop.set()
        await typing_task
        try:
            await status_msg.delete()
        except Exception:
            pass


@router.message(Command(commands=["подкаст", "podcast"]))
async def cmd_podcast(message: Message):
    """Generate a podcast episode: /подкаст AI-агенты в бизнесе."""
    text = (message.text or "").strip()
    # Remove command prefix
    parts = text.split(maxsplit=1)
    topic = parts[1].strip() if len(parts) > 1 else ""

    if not topic:
        await message.answer(
            "Формат: /подкаст <тема>\n\n"
            "Примеры:\n"
            "- /подкаст AI-агенты в бизнесе\n"
            "- /подкаст Будущее удалёнки\n"
            "- /podcast Тренды 2026"
        )
        return

    await _generate_podcast_flow(message, topic)


async def _generate_podcast_flow(message: Message, topic: str):
    """Core podcast generation flow — used by /подкаст command and natural language triggers."""
    if circuit_breaker.is_open:
        await message.answer(
            f"Circuit breaker активен: {circuit_breaker.status}\n"
            "Подожди или /health для диагностики."
        )
        return

    status_msg = await message.answer(
        f"🎙 Этап 1/3: Генерация сценария — {topic[:40]}... (30–90 сек)"
    )

    stop = asyncio.Event()
    from ...telegram.handlers.commands import keep_typing
    typing_task = asyncio.create_task(keep_typing(message, stop))

    try:
        # Step 1: Generate script
        script_raw = await AgentBridge.run_generate_podcast(topic=topic)
        circuit_breaker.record_success()

        # Extract clean script (after ---)
        if "---" in script_raw:
            script = script_raw.split("---", 1)[1].strip()
        else:
            script = script_raw.strip()

        # Send script preview
        preview = script[:1500] + ("..." if len(script) > 1500 else "")
        await message.answer(f"📝 Сценарий ({len(script)} символов):\n\n{preview}")

        # Step 2: TTS
        try:
            await status_msg.edit_text("🎙 Этап 2/3: Озвучка ElevenLabs...")
        except Exception:
            pass

        from ..podcast_gen import generate_podcast_audio
        filepath, metadata = await asyncio.to_thread(
            generate_podcast_audio, script, topic
        )

        # Step 3: RSS
        try:
            await status_msg.edit_text("🎙 Этап 3/3: Обновление RSS...")
        except Exception:
            pass

        from ..rss_feed import PodcastRSSManager
        rss = PodcastRSSManager()
        episode = rss.add_episode(
            title=topic,
            description=f"Выпуск подкаста AI Corporation на тему: {topic}",
            audio_filename=metadata["filename"],
            duration_sec=metadata["duration_sec"],
        )

        # Send audio file
        from aiogram.types import FSInputFile
        await message.answer_audio(
            FSInputFile(filepath),
            title=topic,
            performer="AI Corporation Podcast",
            caption=(
                f"🎙 Выпуск #{episode['episode_number']}: {topic}\n"
                f"⏱ {metadata['duration_sec'] // 60}:{metadata['duration_sec'] % 60:02d} | "
                f"📊 {metadata['file_size_bytes'] // 1024} KB | "
                f"🧩 {metadata['chunks_count']} чанков"
            ),
        )

        # Save as draft for potential re-publishing
        post_id = DraftManager.create_draft(
            topic=f"[PODCAST] {topic}",
            text=script,
            author="yuki",
            brand="ai_corp",
        )

        await message.answer(
            f"Подкаст готов! (ID: {post_id})\n"
            f"Выпуск #{episode['episode_number']} | "
            f"{metadata['duration_sec'] // 60} мин {metadata['duration_sec'] % 60} сек\n\n"
            f"RSS обновлён ({rss.get_episode_count()} выпусков)"
        )

    except Exception as e:
        circuit_breaker.record_failure()
        logger.error(f"Podcast generation error: {e}", exc_info=True)
        await message.answer(f"Ошибка генерации подкаста: {type(e).__name__}: {str(e)[:200]}")
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
    from ..scheduler import PostScheduler

    statuses = get_all_statuses()
    smm_status = statuses.get("smm", {})
    tasks_24h = get_agent_task_count("smm", hours=24)

    status_emoji = {"working": "🟢", "idle": "⚪", "queued": "🟡"}.get(
        smm_status.get("status", "idle"), "⚪"
    )

    scheduled = PostScheduler.get_scheduled()

    # Podcast episode count
    try:
        from ..rss_feed import PodcastRSSManager
        podcast_count = PodcastRSSManager().get_episode_count()
    except Exception:
        podcast_count = 0

    await message.answer(
        f"Юки Пак — SMM статус\n\n"
        f"{status_emoji} Статус: {smm_status.get('status', 'idle')}\n"
        f"📝 Задач за 24ч: {tasks_24h}\n"
        f"📋 Черновиков: {DraftManager.active_count()}\n"
        f"📅 В очереди: {len(scheduled)}\n"
        f"🎙 Подкастов: {podcast_count}\n"
        f"🔒 Автономность: {autonomy.status}\n"
        f"🔌 Circuit breaker: {circuit_breaker.status}\n"
    )


@router.message(Command("health"))
async def cmd_health(message: Message):
    """Quick health check — no LLM call."""
    from ..scheduler import PostScheduler

    lines = ["Юки — диагностика\n"]

    # LLM check
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
    lines.append(f"{'✅' if openrouter_key else '❌'} OpenRouter API key: {'set' if openrouter_key else 'MISSING'}")

    # LinkedIn
    linkedin_token = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
    lines.append(f"{'✅' if linkedin_token else '⚠️'} LinkedIn token: {'set' if linkedin_token else 'not set'}")

    # Telegram channel
    channel_id = os.getenv("TELEGRAM_YUKI_CHANNEL_ID", "")
    lines.append(f"{'✅' if channel_id else '⚠️'} Telegram канал: {channel_id or 'не настроен'}")

    # Threads
    threads_token = os.getenv("THREADS_ACCESS_TOKEN", "")
    lines.append(f"{'✅' if threads_token else '⚠️'} Threads: {'настроен' if threads_token else 'не настроен'}")

    # ElevenLabs (podcast)
    el_key = os.getenv("ELEVENLABS_API_KEY", "")
    el_voice = os.getenv("ELEVENLABS_VOICE_ID", "")
    lines.append(f"{'✅' if el_key else '⚠️'} ElevenLabs API: {'set' if el_key else 'не настроен'}")
    lines.append(f"{'✅' if el_voice else '⚠️'} ElevenLabs Voice: {'set' if el_voice else 'не настроен'}")

    # Publishers
    configured = get_configured_publishers()
    lines.append(f"\n📡 Платформы: {', '.join(configured) if configured else 'ни одна не настроена'}")

    # Circuit breaker
    lines.append(f"🔌 Circuit breaker: {circuit_breaker.status}")

    # Autonomy
    lines.append(f"🔒 Автономность: {autonomy.status}")

    # Drafts
    lines.append(f"📋 Активных черновиков: {DraftManager.active_count()}")

    # Schedule
    scheduled = PostScheduler.get_scheduled()
    lines.append(f"📅 Запланировано: {len(scheduled)}")

    await message.answer("\n".join(lines))


@router.message(Command("level"))
async def cmd_level(message: Message):
    """Show/set autonomy level."""
    text = (message.text or "").strip()
    parts = text.split()

    if len(parts) > 1:
        try:
            new_level = int(parts[1])
            if new_level not in (1, 2):
                await message.answer("Доступные уровни: 1 (manual), 2 (auto)")
                return
            autonomy.level = new_level
            await message.answer(f"Автономность изменена: {autonomy.status}")
        except ValueError:
            await message.answer("Формат: /level 1 или /level 2")
    else:
        await message.answer(
            f"Текущий уровень: {autonomy.status}\n\n"
            "Уровни:\n"
            "1 — Manual: все посты через одобрение\n"
            "2 — Auto: авто-публикация при confidence ≥ 0.8\n\n"
            "Изменить: /level 1 или /level 2"
        )


@router.message(Command("schedule"))
async def cmd_schedule(message: Message):
    """Show scheduled posts."""
    from ..scheduler import PostScheduler
    from datetime import datetime, timezone

    scheduled = PostScheduler.get_scheduled()
    if not scheduled:
        await message.answer("📅 Нет запланированных постов.")
        return

    lines = ["📅 Запланированные посты:\n"]
    for entry in scheduled:
        draft = DraftManager.get_draft(entry["post_id"])
        topic = draft.get("topic", "?")[:30] if draft else "?"
        pub_at = datetime.fromisoformat(entry["publish_at"])
        platforms = ", ".join(entry.get("platforms", []))
        lines.append(f"• {topic} → {platforms} @ {pub_at.strftime('%H:%M %d.%m')}")

    await message.answer("\n".join(lines))


@router.message(Command("linkedin"))
async def cmd_linkedin(message: Message):
    await run_with_typing(
        message,
        AgentBridge.run_linkedin_status(),
        "📱 Проверяю статус LinkedIn... (20–40 сек)",
    )


@router.message(Command("reflexion"))
async def cmd_reflexion(message: Message):
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
