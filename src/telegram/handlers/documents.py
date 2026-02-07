"""Document handler — parses CSV bank statements sent to the bot."""

import asyncio
import logging

from aiogram import Router, F, Bot
from aiogram.types import Message

from ..tinkoff_parser import is_tinkoff_csv, parse_tinkoff_csv, format_summary_text
from ..transaction_storage import save_statement
from ..formatters import format_for_telegram

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.document)
async def handle_document(message: Message, bot: Bot):
    """Handle document uploads — look for CSV bank statements."""
    doc = message.document
    if not doc:
        return

    filename = doc.file_name or ""
    mime = doc.mime_type or ""

    # Accept CSV files or text files that might be CSV
    is_csv = (
        filename.lower().endswith(".csv")
        or "csv" in mime.lower()
        or "text" in mime.lower()
    )

    if not is_csv:
        # Not a CSV — ignore, let other handlers deal with it
        return

    status = await message.answer("Читаю файл...")

    try:
        # Download file content
        file = await bot.download(doc)
        if file is None:
            await message.answer("Не удалось скачать файл.")
            return

        raw_bytes = file.read()

        # Try different encodings
        content = None
        for encoding in ["utf-8", "cp1251", "windows-1251", "latin-1"]:
            try:
                content = raw_bytes.decode(encoding)
                break
            except (UnicodeDecodeError, LookupError):
                continue

        if content is None:
            await message.answer("Не удалось прочитать файл — неизвестная кодировка.")
            return

        # Check if it's a Tinkoff CSV
        if not is_tinkoff_csv(content):
            await message.answer(
                "Это не похоже на выписку Т-Банка. "
                "Нужен CSV с колонками: Дата операции, Сумма операции и т.д."
            )
            return

        # Parse
        await status.edit_text("Разбираю выписку...")
        parsed = await asyncio.to_thread(parse_tinkoff_csv, content)

        if not parsed.get("transactions"):
            await message.answer("Файл распознан, но операций не найдено.")
            return

        # Save to storage (merge + dedup)
        new_count = save_statement(parsed)

        # Format response
        summary = format_summary_text(parsed)
        response = (
            f"Выписка загружена!\n"
            f"Новых операций: {new_count} (всего в файле: {parsed['total_count']})\n\n"
            f"{summary}"
        )

        for chunk in format_for_telegram(response):
            await message.answer(chunk)

    except Exception as e:
        logger.error(f"Document handler error: {e}", exc_info=True)
        await message.answer(f"Ошибка при обработке файла: {str(e)[:300]}")
    finally:
        try:
            await status.delete()
        except Exception:
            pass
