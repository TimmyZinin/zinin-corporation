"""Text message handler — forwards to Алексей (CEO) via AgentBridge."""

import asyncio
import logging

from aiogram import Router, F
from aiogram.types import Message

from ...telegram.bridge import AgentBridge
from ...telegram.formatters import format_for_telegram
from ...telegram.handlers.commands import keep_typing
from ...error_handler import format_error_for_user
from .callbacks import (
    is_in_conditions_mode, get_conditions_proposal_id,
    is_in_new_task_mode, _new_task_state,
    is_in_split_mode, _split_task_state,
    is_in_evening_adjust_mode, consume_evening_adjust_mode,
)

logger = logging.getLogger(__name__)
router = Router()

AGENT_TIMEOUT_SEC = 120

_chat_contexts: dict[int, list[dict]] = {}
MAX_CONTEXT = 20

_AGENT_LABELS = {
    "manager": "Алексей",
    "accountant": "Маттиас",
    "automator": "Мартин",
    "smm": "Юки",
    "designer": "Райан",
    "cpo": "Софи",
}

# Intent → command handler mapping
_INTENT_HANDLERS = {
    "/balance": "cmd_status",      # balance info via status
    "/tasks": "cmd_tasks",
    "/status": "cmd_status",
    "/review": "cmd_review",
    "/report": "cmd_report",
    "/analytics": "cmd_analytics",
    "/help": "cmd_help",
    "/content": "cmd_content",
    "/linkedin": "cmd_linkedin",
}


async def _execute_intent(message: Message, intent):
    """Execute a detected intent by calling the corresponding command handler."""
    from .commands import (
        cmd_status, cmd_tasks, cmd_review, cmd_report,
        cmd_help, cmd_content, cmd_linkedin, cmd_analytics,
    )
    handlers = {
        "/balance": cmd_status,
        "/tasks": cmd_tasks,
        "/status": cmd_status,
        "/review": cmd_review,
        "/report": cmd_report,
        "/analytics": cmd_analytics,
        "/help": cmd_help,
        "/content": cmd_content,
        "/linkedin": cmd_linkedin,
    }
    handler = handlers.get(intent.command)
    if handler:
        await handler(message)
    else:
        logger.warning(f"No handler for intent: {intent.command}")


async def _progress_updater(status_msg, agent_label: str, stop_event: asyncio.Event, interval: int = 30):
    """Update status message every `interval` seconds with elapsed time."""
    elapsed = 0
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(asyncio.shield(stop_event.wait()), timeout=interval)
            break  # stop_event was set
        except asyncio.TimeoutError:
            elapsed += interval
            try:
                await status_msg.edit_text(f"💬 {agent_label} работает... ({elapsed} сек)")
            except Exception:
                pass  # message already deleted or can't edit


def _get_context(user_id: int) -> list[dict]:
    """Get per-user chat context (isolated between users)."""
    if user_id not in _chat_contexts:
        _chat_contexts[user_id] = []
    return _chat_contexts[user_id]


@router.message(F.text)
async def handle_text(message: Message):
    user_text = message.text.strip()
    if not user_text:
        return

    # Evening adjust mode — user typed plan corrections
    if is_in_evening_adjust_mode(message.from_user.id):
        consume_evening_adjust_mode(message.from_user.id)
        await message.answer(
            f"📝 Корректировки приняты: «{user_text[:200]}»\n"
            f"Учту в завтрашнем плане."
        )
        logger.info(f"Evening adjustment received: {user_text[:100]}")
        return

    # Task Pool "split task" mode — intercept text as subtask titles
    if is_in_split_mode(message.from_user.id):
        parent_id = _split_task_state.pop(message.from_user.id)
        from ...task_pool import get_task, create_task, format_task_summary, delete_task
        from ..keyboards import task_menu_keyboard
        parent = get_task(parent_id)
        lines = [l.strip() for l in user_text.split("\n") if l.strip()]
        created = []
        for line in lines:
            # Strip list markers
            clean = line.lstrip("0123456789.-) •").strip()
            if len(clean) >= 5:
                t = create_task(clean, source="split", assigned_by="tim")
                created.append(t)
        if created:
            if parent:
                delete_task(parent_id)
            parts = [f"✂️ Разделено на {len(created)} подзадач:\n"]
            for t in created:
                parts.append(format_task_summary(t))
            await message.answer(
                "\n\n".join(parts),
                reply_markup=task_menu_keyboard(),
                parse_mode="HTML",
            )
        else:
            await message.answer("Не удалось создать подзадачи. Попробуйте ещё раз.")
        return

    # Task Pool "new task" mode — intercept text input as task title
    if is_in_new_task_mode(message.from_user.id):
        _new_task_state.discard(message.from_user.id)
        from ...task_pool import create_task, suggest_assignee, format_task_summary, ESCALATION_THRESHOLD
        from ..keyboards import task_detail_keyboard, escalation_keyboard
        task = create_task(user_text, source="telegram", assigned_by="tim")
        suggestion = suggest_assignee(task.tags)
        text_parts = [format_task_summary(task)]

        # Escalation: if no good match, show escalation keyboard
        if not suggestion or suggestion[0][1] < ESCALATION_THRESHOLD:
            max_conf = suggestion[0][1] if suggestion else 0
            text_parts.append(
                f"\n⚠️ Нет подходящего агента (max confidence: {max_conf:.0%})"
            )
            await message.answer(
                "\n".join(text_parts),
                reply_markup=escalation_keyboard(task.id),
                parse_mode="HTML",
            )
        else:
            best_agent, confidence = suggestion[0]
            text_parts.append(f"\n💡 Рекомендация: <b>{best_agent}</b> ({confidence:.0%})")
            await message.answer(
                "\n".join(text_parts),
                reply_markup=task_detail_keyboard(task.id, task.status.value),
                parse_mode="HTML",
            )
        return

    # CTO proposal conditions mode — intercept text input
    if is_in_conditions_mode(message.from_user.id):
        proposal_id = get_conditions_proposal_id(message.from_user.id)
        if proposal_id:
            from .callbacks import _find_and_update_proposal
            proposal = _find_and_update_proposal(
                proposal_id, {"status": "conditions", "conditions": user_text}
            )
            if proposal:
                await message.answer(
                    f"📝 Условия сохранены для предложения:\n"
                    f"📋 {proposal.get('title', '?')}\n\n"
                    f"Мартин учтёт ваши условия при доработке."
                )
            else:
                await message.answer("Предложение не найдено.")
            return

    # Fast Router: intent → agent → fallback (0 LLM for routing)
    from ..fast_router import route_message
    route = route_message(user_text)

    # Intent route → redirect to command handler
    if route.route_type == "intent":
        from ..nlu import detect_intent
        intent = detect_intent(user_text)
        if intent:
            await _execute_intent(message, intent)
            return

    # Brain dump detection — long structured messages → Task Pool
    from ...brain_dump import is_brain_dump, parse_brain_dump, format_brain_dump_result
    if is_brain_dump(user_text):
        tasks = parse_brain_dump(user_text, source="brain_dump")
        if tasks:
            from ..keyboards import task_menu_keyboard
            result_text = format_brain_dump_result(tasks)
            if len(result_text) > 4000:
                result_text = result_text[:4000] + "..."
            await message.answer(result_text, reply_markup=task_menu_keyboard(), parse_mode="HTML")
            return

    # Agent route from fast_router (agent detection or fallback)
    agent_name = route.agent_name or "manager"

    user_ctx = _get_context(message.from_user.id)
    user_ctx.append({"role": "user", "text": user_text})

    agent_label = _AGENT_LABELS.get(agent_name, "Алексей")
    status = await message.answer(f"💬 {agent_label} думает...")

    stop = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(message, stop))
    progress_task = asyncio.create_task(_progress_updater(status, agent_label, stop))

    context_str = _format_context(user_ctx[-MAX_CONTEXT:])

    try:
        print(f"[CEO] msg from {message.from_user.id}: {user_text[:80]}", flush=True)
        print(f"[CEO] Calling AgentBridge.send_to_agent({agent_name})...", flush=True)
        response = await asyncio.wait_for(
            AgentBridge.send_to_agent(
                message=user_text,
                agent_name=agent_name,
                chat_context=context_str,
                bot=message.bot,
                chat_id=message.chat.id,
            ),
            timeout=AGENT_TIMEOUT_SEC,
        )
        print(f"[CEO] AgentBridge returned {len(response)} chars", flush=True)
        user_ctx.append({"role": "assistant", "text": response})

        # Send any images found in agent response
        from ..image_sender import send_images_from_response
        response = await send_images_from_response(message.bot, message.chat.id, response)

        for chunk in format_for_telegram(response):
            await message.answer(chunk)

    except asyncio.TimeoutError:
        logger.warning(f"Agent {agent_name} timed out after {AGENT_TIMEOUT_SEC}s")
        await message.answer(
            f"⏱ {agent_label} не ответил за {AGENT_TIMEOUT_SEC} сек.\n"
            f"Попробуйте /route {agent_name} <задача> для прямого вызова."
        )
    except Exception as e:
        logger.error(f"CEO message handler error: {e}", exc_info=True)
        await message.answer(f"Ошибка: {format_error_for_user(e)}")
    finally:
        stop.set()
        await typing_task
        await progress_task
        try:
            await status.delete()
        except Exception:
            pass


@router.message(F.voice)
async def handle_voice(message: Message):
    """Voice message handler — transcribe → brain dump or agent."""
    import os
    import tempfile

    from ...tools.voice_tools import transcribe_voice, convert_ogg_to_wav, is_voice_available, release_model

    if not is_voice_available():
        await message.answer(
            "🎙️ Voice отключён на сервере (экономия RAM).\n"
            "Отправьте текстом — я обработаю так же."
        )
        return

    status = await message.answer("🎙️ Распознаю голос...")

    ogg_path = None
    wav_path = None
    try:
        # Download voice file
        file = await message.bot.get_file(message.voice.file_id)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            ogg_path = tmp.name
        await message.bot.download_file(file.file_path, ogg_path)

        # Convert OGG → WAV
        wav_path = convert_ogg_to_wav(ogg_path)
        if not wav_path:
            await message.answer("Не удалось конвертировать аудио.")
            return

        # Transcribe
        text = transcribe_voice(wav_path)
        # Free whisper model immediately to save RAM for CrewAI agents
        release_model()
        if not text:
            await message.answer("Не удалось распознать речь.")
            return

        # Show transcription
        await message.answer(f"📝 Распознано:\n{text[:2000]}")

        # Check if it's a brain dump
        from ...brain_dump import is_brain_dump, parse_brain_dump, format_brain_dump_result
        if is_brain_dump(text):
            tasks = parse_brain_dump(text, source="voice_brain_dump")
            if tasks:
                from ..keyboards import task_menu_keyboard
                result_text = format_brain_dump_result(tasks)
                if len(result_text) > 4000:
                    result_text = result_text[:4000] + "..."
                await message.answer(
                    result_text, reply_markup=task_menu_keyboard(), parse_mode="HTML",
                )
                return

        # Otherwise treat as regular text — forward to agent
        # Create a synthetic text message behavior
        user_ctx = _get_context(message.from_user.id)
        user_ctx.append({"role": "user", "text": f"[голос] {text}"})

        stop = asyncio.Event()
        typing_task = asyncio.create_task(keep_typing(message, stop))
        context_str = _format_context(user_ctx[-MAX_CONTEXT:])

        try:
            response = await asyncio.wait_for(
                AgentBridge.send_to_agent(
                    message=text,
                    agent_name="manager",
                    chat_context=context_str,
                    bot=message.bot,
                    chat_id=message.chat.id,
                ),
                timeout=AGENT_TIMEOUT_SEC,
            )
            user_ctx.append({"role": "assistant", "text": response})
            from ..image_sender import send_images_from_response
            response = await send_images_from_response(message.bot, message.chat.id, response)
            for chunk in format_for_telegram(response):
                await message.answer(chunk)
        except asyncio.TimeoutError:
            logger.warning(f"Voice agent timed out after {AGENT_TIMEOUT_SEC}s")
            await message.answer(
                f"⏱ Агент не ответил за {AGENT_TIMEOUT_SEC} сек. Отправьте текстом ещё раз."
            )
        except Exception as e:
            logger.error(f"Voice → agent error: {e}", exc_info=True)
            await message.answer(f"Ошибка: {format_error_for_user(e)}")
        finally:
            stop.set()
            await typing_task

    except Exception as e:
        logger.error(f"Voice handler error: {e}", exc_info=True)
        await message.answer(f"Ошибка обработки голоса: {format_error_for_user(e)}")
    finally:
        # Cleanup temp files
        for path in [ogg_path, wav_path]:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except Exception:
                    pass
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
            lines.append(f"Алексей: {msg['text'][:800]}")
    return "\n".join(lines)
