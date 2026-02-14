"""
Lightweight Telegram notification sender for webhook events.

Uses httpx directly (no aiogram dependency) — safe to call from Starlette context.
"""

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"


def _get_chat_id() -> Optional[str]:
    """Get primary admin chat ID from env."""
    users = os.getenv("TELEGRAM_CEO_ALLOWED_USERS", "")
    if users:
        return users.split(",")[0].strip()
    return None


async def notify_ceo(message: str, parse_mode: str = "HTML") -> bool:
    """Send notification via CEO bot."""
    token = os.getenv("TELEGRAM_CEO_BOT_TOKEN")
    chat_id = _get_chat_id()
    if token and chat_id:
        return await _send_telegram(token, chat_id, message, parse_mode)
    return False


async def notify_cfo(message: str, parse_mode: str = "HTML") -> bool:
    """Send notification via CFO bot."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = _get_chat_id()
    if token and chat_id:
        return await _send_telegram(token, chat_id, message, parse_mode)
    return False


async def _send_telegram(
    token: str, chat_id: str, text: str, parse_mode: str = "HTML"
) -> bool:
    """Send message via Telegram Bot API. Returns True on success."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{TELEGRAM_API}/bot{token}/sendMessage",
                json={
                    "chat_id": int(chat_id),
                    "text": text,
                    "parse_mode": parse_mode,
                },
            )
            if resp.status_code == 200:
                return True
            logger.warning(
                "Telegram notify failed: %s %s", resp.status_code, resp.text[:200]
            )
            return False
    except Exception as e:
        logger.error("Telegram notification error: %s", e)
        return False
