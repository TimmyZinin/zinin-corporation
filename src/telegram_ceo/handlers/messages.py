"""Text message handler — forwards to Алексей (CEO) via AgentBridge."""

import asyncio
import logging

from aiogram import Router, F
from aiogram.types import Message

from ...telegram.bridge import AgentBridge
from ...telegram.formatters import format_for_telegram
from ...telegram.handlers.commands import keep_typing
from .callbacks import is_in_conditions_mode, get_conditions_proposal_id, is_in_new_task_mode, _new_task_state

logger = logging.getLogger(__name__)
router = Router()

_chat_contexts: dict[int, list[dict]] = {}
MAX_CONTEXT = 20


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

    # Task Pool "new task" mode — intercept text input as task title
    if is_in_new_task_mode(message.from_user.id):
        _new_task_state.discard(message.from_user.id)
        from ...task_pool import create_task, suggest_assignee, format_task_summary
        from ..keyboards import task_detail_keyboard
        task = create_task(user_text, source="telegram", assigned_by="tim")
        suggestion = suggest_assignee(task.tags)
        text_parts = [format_task_summary(task)]
        if suggestion:
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

    user_ctx = _get_context(message.from_user.id)
    user_ctx.append({"role": "user", "text": user_text})

    status = await message.answer("💬 Алексей думает...")

    stop = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(message, stop))

    context_str = _format_context(user_ctx[-MAX_CONTEXT:])

    try:
        print(f"[CEO] msg from {message.from_user.id}: {user_text[:80]}", flush=True)
        print("[CEO] Calling AgentBridge.send_to_agent(manager)...", flush=True)
        response = await AgentBridge.send_to_agent(
            message=user_text,
            agent_name="manager",
            chat_context=context_str,
            bot=message.bot,
            chat_id=message.chat.id,
        )
        print(f"[CEO] AgentBridge returned {len(response)} chars", flush=True)
        user_ctx.append({"role": "assistant", "text": response})

        for chunk in format_for_telegram(response):
            await message.answer(chunk)

    except Exception as e:
        logger.error(f"CEO message handler error: {e}", exc_info=True)
        await message.answer(f"Ошибка: {type(e).__name__}: {str(e)[:200]}")
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
            lines.append(f"Алексей: {msg['text'][:800]}")
    return "\n".join(lines)
