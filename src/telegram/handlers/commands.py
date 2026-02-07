"""Telegram command handlers (/start, /help, /report, etc.)."""

import asyncio
import logging

from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from ..bridge import AgentBridge
from ..formatters import format_for_telegram
from ..screenshot_storage import get_latest_balances

logger = logging.getLogger(__name__)
router = Router()


async def keep_typing(message: Message, stop_event: asyncio.Event):
    """Send typing action every 4 seconds until stop_event is set."""
    while not stop_event.is_set():
        try:
            await message.answer_chat_action("typing")
        except Exception:
            pass
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=4.0)
        except asyncio.TimeoutError:
            pass


async def run_with_typing(message: Message, coro, wait_msg: str):
    """Run a coroutine while showing typing indicator and a wait message."""
    status = await message.answer(wait_msg)
    stop = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(message, stop))
    try:
        result = await coro
        for chunk in format_for_telegram(result):
            await message.answer(chunk)
    except Exception as e:
        logger.error(f"Command error: {e}", exc_info=True)
        await message.answer(f"Ошибка: {str(e)[:300]}")
    finally:
        stop.set()
        await typing_task
        try:
            await status.delete()
        except Exception:
            pass


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Маттиас Бруннер — CFO Zinin Corp\n\n"
        "Добрый день, Тим. Я Маттиас, ваш финансовый директор.\n\n"
        "Команды:\n"
        "/report — Финансовый отчёт\n"
        "/portfolio — Сводка портфеля\n"
        "/tinkoff — Сводка по Т-Банку\n"
        "/balances — Данные из скриншотов\n"
        "/help — Справка\n\n"
        "Можете написать любой финансовый вопрос, "
        "прислать скриншот или CSV-выписку из Т-Банка.",
    )


@router.message(Command("report"))
async def cmd_report(message: Message):
    await run_with_typing(
        message,
        AgentBridge.run_financial_report(),
        "📊 Готовлю финансовый отчёт... (30–60 сек)",
    )


@router.message(Command("portfolio"))
async def cmd_portfolio(message: Message):
    await run_with_typing(
        message,
        AgentBridge.run_portfolio_summary(),
        "💼 Собираю данные портфеля... (30–60 сек)",
    )


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


@router.message(Command("tinkoff"))
async def cmd_tinkoff(message: Message):
    """Show Tinkoff transaction summary."""
    from ..transaction_storage import get_summary
    summary = get_summary()
    if not summary:
        await message.answer(
            "Пока нет данных по Т-Банку.\n"
            "Пришлите CSV-выписку из приложения Т-Банка."
        )
        return

    lines = [
        f"Т-Банк: {summary['period'].get('start', '?')[:10]} — {summary['period'].get('end', '?')[:10]}",
        f"Операций: {summary['total_count']} (карты: {', '.join(summary['cards'])})",
        "",
        f"Доходы: +{summary['income']:,.2f} RUB",
        f"Расходы: -{summary['expenses']:,.2f} RUB",
        f"Нетто: {summary['net']:,.2f} RUB",
    ]

    if summary.get("top_categories"):
        lines.append("")
        lines.append("Топ расходов:")
        for cat, amt in summary["top_categories"][:10]:
            lines.append(f"  {cat}: {amt:,.2f} RUB")

    if summary.get("monthly"):
        lines.append("")
        lines.append("По месяцам:")
        for month, data in sorted(summary["monthly"].items(), reverse=True)[:6]:
            lines.append(
                f"  {month}: +{data['income']:,.0f} / -{data['expenses']:,.0f}"
            )

    lines.append(f"\nОбновлено: {summary['last_updated'][:16]}")
    await message.answer("\n".join(lines))


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Текст → Маттиас отвечает как CFO\n"
        "CSV-файл → разбор выписки Т-Банка\n"
        "Фото/скриншоты → распознавание данных\n\n"
        "/report — Финансовый отчёт\n"
        "/portfolio — Портфель (банки + крипто)\n"
        "/tinkoff — Сводка по Т-Банку\n"
        "/balances — Данные из скриншотов\n"
    )
