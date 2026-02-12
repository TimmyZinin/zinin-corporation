"""Unified error handler for all Telegram bots.

Encapsulates the common try/except/finally pattern used across
CEO, CFO, and SMM bot message handlers.
"""

import asyncio
import html
import logging
from enum import Enum
from typing import Optional

from aiogram.types import Message

logger = logging.getLogger(__name__)


class ErrorCategory(str, Enum):
    """Error classification for retry/report decisions."""
    TRANSIENT = "transient"   # retry: timeout, 429, 503, connection errors
    PERMANENT = "permanent"   # report: bad config, missing keys, auth
    TIMEOUT = "timeout"       # warn: slow response but might recover


# Transient error indicators (substring match)
_TRANSIENT_PATTERNS = [
    "timeout", "timed out", "429", "rate limit", "too many requests",
    "503", "502", "504", "service unavailable", "connection",
    "temporarily", "retry", "overloaded",
]

# Permanent error indicators
_PERMANENT_PATTERNS = [
    "401", "403", "forbidden", "unauthorized", "invalid key",
    "api key", "not found", "module", "import", "attribute",
    "permission", "denied",
]


def categorize_error(error: Exception) -> ErrorCategory:
    """Classify an error for retry/report decisions."""
    error_str = str(error).lower()
    error_type = type(error).__name__.lower()

    if isinstance(error, asyncio.TimeoutError):
        return ErrorCategory.TIMEOUT

    for pattern in _TRANSIENT_PATTERNS:
        if pattern in error_str or pattern in error_type:
            return ErrorCategory.TRANSIENT

    for pattern in _PERMANENT_PATTERNS:
        if pattern in error_str:
            return ErrorCategory.PERMANENT

    return ErrorCategory.TRANSIENT  # default: assume transient


def format_error_for_user(error: Exception) -> str:
    """Format error for Telegram display (max 200 chars, HTML-safe)."""
    type_name = type(error).__name__
    msg = str(error)[:180]
    raw = f"{type_name}: {msg}"
    return html.escape(raw[:200])


async def safe_agent_call(
    message: Message,
    agent_name: str,
    user_text: str,
    chat_context: str = "",
    status_text: str = "Думает...",
    max_retries: int = 1,
    bot=None,
    chat_id: int = None,
) -> Optional[str]:
    """Call AgentBridge with unified error handling.

    Encapsulates: status message → typing → AgentBridge → error handling → cleanup.

    Args:
        message: Aiogram Message object
        agent_name: Agent key ("manager", "accountant", "smm", etc.)
        user_text: User message text
        chat_context: Formatted chat context string
        status_text: Status message to show while processing
        max_retries: Max retries for transient errors (default 1 = no retry)
        bot: Bot instance (optional, passed to AgentBridge)
        chat_id: Chat ID (optional, passed to AgentBridge)

    Returns:
        Agent response text, or None if all retries failed.
    """
    from .telegram.bridge import AgentBridge
    from .telegram.handlers.commands import keep_typing

    status = await message.answer(status_text)
    stop = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(message, stop))

    last_error: Optional[Exception] = None

    try:
        for attempt in range(max_retries):
            try:
                kwargs = {
                    "message": user_text,
                    "agent_name": agent_name,
                    "chat_context": chat_context,
                }
                if bot is not None:
                    kwargs["bot"] = bot
                if chat_id is not None:
                    kwargs["chat_id"] = chat_id

                response = await AgentBridge.send_to_agent(**kwargs)
                return response

            except Exception as e:
                last_error = e
                category = categorize_error(e)
                logger.error(
                    f"Agent call failed [{agent_name}] attempt {attempt + 1}/{max_retries} "
                    f"({category.value}): {e}",
                    exc_info=True,
                )

                if category == ErrorCategory.PERMANENT or attempt == max_retries - 1:
                    break

                # Brief delay before retry for transient errors
                await asyncio.sleep(2)

        # All retries exhausted
        if last_error:
            error_msg = format_error_for_user(last_error)
            await message.answer(f"Ошибка: {error_msg}")

        return None

    finally:
        stop.set()
        await typing_task
        try:
            await status.delete()
        except Exception:
            pass
