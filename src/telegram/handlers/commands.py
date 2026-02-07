"""Telegram command handlers (/start, /help, /report, etc.)."""

from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from ..bridge import AgentBridge
from ..formatters import format_for_telegram
from ..screenshot_storage import get_latest_balances

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "🏦 *Маттиас Бруннер — CFO Zinin Corp*\n\n"
        "Добрый день, Тим. Я Маттиас, ваш финансовый директор.\n\n"
        "*Команды:*\n"
        "/report — Финансовый отчёт\n"
        "/portfolio — Сводка портфеля\n"
        "/balances — Данные из скриншотов\n"
        "/help — Справка\n\n"
        "Можете написать любой финансовый вопрос "
        "или прислать скриншот банковского приложения.",
        parse_mode="Markdown",
    )


@router.message(Command("report"))
async def cmd_report(message: Message):
    await message.answer_chat_action("typing")
    try:
        report = await AgentBridge.run_financial_report()
        for chunk in format_for_telegram(report):
            await message.answer(chunk)
    except Exception as e:
        await message.answer(f"Ошибка при формировании отчёта: {str(e)[:300]}")


@router.message(Command("portfolio"))
async def cmd_portfolio(message: Message):
    await message.answer_chat_action("typing")
    try:
        result = await AgentBridge.run_portfolio_summary()
        for chunk in format_for_telegram(result):
            await message.answer(chunk)
    except Exception as e:
        await message.answer(f"Ошибка: {str(e)[:300]}")


@router.message(Command("balances"))
async def cmd_balances(message: Message):
    """Show latest balances from parsed screenshots."""
    latest = get_latest_balances()
    if not latest:
        await message.answer(
            "Пока нет данных из скриншотов. "
            "Пришлите скриншот баланса TBC Bank или @wallet."
        )
        return

    lines = ["Последние балансы (из скриншотов):\n"]
    for source, data in latest.items():
        lines.append(f"{source} (обновлено: {data['extracted_at'][:10]})")
        for acc in data.get("accounts", []):
            name = acc.get("name", "N/A")
            balance = acc.get("balance", "?")
            currency = acc.get("currency", "")
            lines.append(f"  {name}: {balance} {currency}")
        lines.append("")

    await message.answer("\n".join(lines))


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Текст → Маттиас отвечает как CFO\n"
        "Фото/скриншоты → автоматическое распознавание данных\n\n"
        "/report — Финансовый отчёт\n"
        "/portfolio — Портфель (банки + крипто)\n"
        "/balances — Данные из скриншотов\n"
    )
