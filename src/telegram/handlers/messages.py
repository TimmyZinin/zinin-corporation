"""Text message handler — forwards to Маттиас via AgentBridge."""

from aiogram import Router, F
from aiogram.types import Message

from ..bridge import AgentBridge
from ..formatters import format_for_telegram

router = Router()

# Simple in-memory context (last N messages)
_chat_context: list[dict] = []
MAX_CONTEXT = 20


@router.message(F.text)
async def handle_text(message: Message):
    user_text = message.text.strip()
    if not user_text:
        return

    _chat_context.append({"role": "user", "text": user_text})

    await message.answer_chat_action("typing")

    context_str = _format_context(_chat_context[-MAX_CONTEXT:])

    try:
        response = await AgentBridge.send_to_agent(
            message=user_text,
            agent_name="accountant",
            chat_context=context_str,
        )
        _chat_context.append({"role": "assistant", "text": response})

        for chunk in format_for_telegram(response):
            await message.answer(chunk)

    except Exception as e:
        await message.answer(f"Ошибка: {type(e).__name__}: {str(e)[:200]}")


def _format_context(messages: list[dict]) -> str:
    lines = []
    for msg in messages:
        if msg["role"] == "user":
            lines.append(f"Тим: {msg['text']}")
        else:
            lines.append(f"Маттиас: {msg['text'][:800]}")
    return "\n".join(lines)
