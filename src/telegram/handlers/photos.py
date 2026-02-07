"""Photo handler — parses financial screenshots via Claude Vision."""

import base64
import io

from aiogram import Router, F
from aiogram.types import Message

from ..vision import extract_financial_data
from ..screenshot_storage import save_screenshot_data
from ..bridge import AgentBridge
from ..formatters import format_for_telegram

router = Router()


@router.message(F.photo)
async def handle_photo(message: Message):
    """Receive photo, extract financial data, optionally analyze."""
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
        save_screenshot_data(result)

        summary = result.get("summary", "Данные извлечены")
        await message.answer(f"Скриншот обработан.\n\n{summary}")

        # If user asked for analysis in caption
        if caption and any(
            kw in caption.lower()
            for kw in ["анализ", "отчёт", "проанализируй", "сравни"]
        ):
            analysis = await AgentBridge.send_to_agent(
                message=(
                    f"Тим прислал скриншот. Извлечённые данные:\n{summary}\n\n"
                    "Проанализируй эти данные."
                ),
                agent_name="accountant",
            )
            for chunk in format_for_telegram(analysis):
                await message.answer(chunk)

    except Exception as e:
        await message.answer(f"Ошибка при обработке скриншота: {str(e)[:300]}")
