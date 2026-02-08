"""Photo handler — parses financial screenshots via Claude Vision.

Auto-detects financial data (bank balances, crypto wallets, transactions)
and saves structured data to persistent storage.
"""

import base64
import io
import logging

from aiogram import Router, F
from aiogram.types import Message
from aiogram.enums import ParseMode

from ..vision import extract_financial_data
from ..screenshot_storage import save_screenshot_data, get_latest_balances
from ..formatters import mono_table

logger = logging.getLogger(__name__)
router = Router()


def _format_extracted(result: dict) -> str:
    """Format extracted data as a structured Telegram message."""
    lines = []

    source = result.get("source", "unknown")
    screen_type = result.get("screen_type", "unknown")
    lines.append(f"<b>{source}</b> — {screen_type}")
    lines.append("")

    # Accounts / balances
    accounts = result.get("accounts", [])
    if accounts:
        rows = []
        for acc in accounts:
            name = acc.get("name", "—")
            balance = acc.get("balance", "?")
            currency = acc.get("currency", "")
            rows.append([name, f"{balance} {currency}"])
        lines.append(mono_table(["Счёт", "Баланс"], rows))
        lines.append("")

    # Transactions
    transactions = result.get("transactions", [])
    if transactions:
        lines.append(f"<b>Транзакции ({len(transactions)}):</b>")
        for tx in transactions[:5]:
            date = tx.get("date", "")
            amount = tx.get("amount", "?")
            currency = tx.get("currency", "")
            desc = tx.get("description", "")[:40]
            counterparty = tx.get("counterparty", "")
            line = f"  {date} {amount} {currency}"
            if counterparty:
                line += f" → {counterparty}"
            elif desc:
                line += f" — {desc}"
            lines.append(line)
        if len(transactions) > 5:
            lines.append(f"  ... ещё {len(transactions) - 5}")
        lines.append("")

    # Summary
    summary = result.get("summary", "")
    if summary:
        lines.append(f"<i>{summary}</i>")

    return "\n".join(lines)


@router.message(F.photo)
async def handle_photo(message: Message):
    """Receive photo, extract financial data, save and show results."""
    await message.answer_chat_action("typing")

    # Get highest resolution
    photo = message.photo[-1]

    # Download
    bot = message.bot
    file = await bot.get_file(photo.file_id)
    buf = io.BytesIO()
    await bot.download_file(file.file_path, buf)
    buf.seek(0)

    b64 = base64.b64encode(buf.read()).decode("utf-8")
    caption = message.caption or ""

    try:
        result = await extract_financial_data(b64, user_hint=caption)

        # Always save extracted data
        saved = save_screenshot_data(result)

        # Format structured response
        response = _format_extracted(result)

        if saved:
            response += "\n\nДанные сохранены в базу."
        else:
            response += "\n\nНе удалось сохранить данные."

        # Count total sources
        latest = get_latest_balances()
        if latest:
            response += f"\nИсточников с данными: {len(latest)}"

        await message.answer(response, parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"Photo processing error: {e}", exc_info=True)
        await message.answer(f"Ошибка при обработке скриншота: {str(e)[:300]}")
