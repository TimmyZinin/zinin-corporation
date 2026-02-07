"""Text message handler — forwards to Алексей (CEO) via AgentBridge."""

import asyncio
import logging

from aiogram import Router, F
from aiogram.types import Message

from ...telegram.bridge import AgentBridge
from ...telegram.formatters import format_for_telegram
from ...telegram.handlers.commands import keep_typing

logger = logging.getLogger(__name__)
router = Router()

_chat_context: list[dict] = []
MAX_CONTEXT = 20


@router.message(F.text)
async def handle_text(message: Message):
    user_text = message.text.strip()
    if not user_text:
        return

    _chat_context.append({"role": "user", "text": user_text})

    status = await message.answer("💬 Алексей думает...")

    stop = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(message, stop))

    context_str = _format_context(_chat_context[-MAX_CONTEXT:])

    try:
        response = await AgentBridge.send_to_agent(
            message=user_text,
            agent_name="manager",
            chat_context=context_str,
        )
        _chat_context.append({"role": "assistant", "text": response})

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
