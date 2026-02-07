"""Telegram command handlers (/start, /help, /report, /chart, etc.)."""

import asyncio
import logging

from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, BufferedInputFile
from aiogram.enums import ParseMode

from ..bridge import AgentBridge
from ..formatters import format_for_telegram, mono_table, sparkline, progress_bar
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
        "/chart — 📊 График портфеля\n"
        "/expenses — 📉 График расходов\n"
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


@router.message(Command("chart"))
async def cmd_chart(message: Message):
    """Generate portfolio pie chart from real data."""
    status = await message.answer("📊 Строю график...")
    stop = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(message, stop))

    try:
        portfolio = await asyncio.to_thread(_collect_portfolio_data)
        if not portfolio:
            await message.answer("Нет данных для графика. Попробуйте /portfolio сначала.")
            return

        from ..charts import portfolio_pie
        png = portfolio_pie(portfolio, "Портфель Zinin Corp")
        if not png:
            await message.answer("Не удалось построить график.")
            return

        total = sum(portfolio.values())
        top3 = sorted(portfolio.items(), key=lambda x: -x[1])[:3]
        caption = (
            f"<b>Портфель — ${total:,.0f}</b>\n"
            + "\n".join(f"  {name}: ${val:,.0f}" for name, val in top3)
        )

        photo = BufferedInputFile(png, filename="portfolio.png")
        await message.answer_photo(photo=photo, caption=caption, parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"Chart error: {e}", exc_info=True)
        await message.answer(f"Ошибка графика: {str(e)[:300]}")
    finally:
        stop.set()
        await typing_task
        try:
            await status.delete()
        except Exception:
            pass


@router.message(Command("expenses"))
async def cmd_expenses(message: Message):
    """Generate expense bar chart from Tinkoff data."""
    from ..transaction_storage import get_summary
    summary = get_summary()
    if not summary or not summary.get("top_categories"):
        await message.answer("Нет данных по расходам. Пришлите CSV-выписку из Т-Банка.")
        return

    categories = dict(summary["top_categories"][:10])

    from ..charts import expense_bars
    png = expense_bars(categories, "Расходы — Т-Банк")
    if not png:
        await message.answer("Не удалось построить график расходов.")
        return

    total = sum(categories.values())
    caption = f"<b>Расходы — ₽{total:,.0f}</b>\nТоп {len(categories)} категорий"

    photo = BufferedInputFile(png, filename="expenses.png")
    await message.answer_photo(photo=photo, caption=caption, parse_mode=ParseMode.HTML)


def _collect_portfolio_data() -> dict[str, float]:
    """Collect balance data from all tools for chart generation."""
    import os
    portfolio = {}

    # EVM via Moralis
    if os.environ.get("MORALIS_API_KEY"):
        try:
            from src.tools.financial.moralis_evm import EVMPortfolioTool
            tool = EVMPortfolioTool()
            result = tool._run("")
            # Parse total from first line
            if "total" in result.lower():
                import re
                m = re.search(r"\$([0-9,.]+)\s+USD\s+total", result)
                if m:
                    portfolio["EVM (5 chains)"] = float(m.group(1).replace(",", ""))
        except Exception as e:
            logger.debug(f"EVM data: {e}")

    # Papaya
    try:
        from src.tools.financial.papaya import PapayaPositionsTool
        tool = PapayaPositionsTool()
        result = tool._run()
        if "ИТОГО" in result:
            import re
            m = re.search(r"\$([0-9,.]+)", result.split("ИТОГО")[-1])
            if m:
                portfolio["Papaya"] = float(m.group(1).replace(",", ""))
    except Exception as e:
        logger.debug(f"Papaya data: {e}")

    # Eventum
    try:
        from src.tools.financial.eventum import EventumPortfolioTool
        tool = EventumPortfolioTool()
        result = tool._run()
        if "ИТОГО" in result:
            import re
            m = re.search(r"\$([0-9,.]+)", result.split("ИТОГО")[-1])
            if m:
                portfolio["Eventum L3"] = float(m.group(1).replace(",", ""))
    except Exception as e:
        logger.debug(f"Eventum data: {e}")

    # Solana
    try:
        from src.tools.financial.helius_solana import SolanaPortfolioTool
        tool = SolanaPortfolioTool()
        result = tool._run("")
        if "total" in result.lower():
            import re
            m = re.search(r"\$([0-9,.]+)\s+USD\s+total", result)
            if m:
                portfolio["Solana"] = float(m.group(1).replace(",", ""))
    except Exception as e:
        logger.debug(f"Solana data: {e}")

    # TON
    try:
        from src.tools.financial.tonapi import TONPortfolioTool
        tool = TONPortfolioTool()
        result = tool._run("")
        if "total" in result.lower():
            import re
            m = re.search(r"\$([0-9,.]+)\s+USD\s+total", result)
            if m:
                portfolio["TON"] = float(m.group(1).replace(",", ""))
    except Exception as e:
        logger.debug(f"TON data: {e}")

    return portfolio


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Текст → Маттиас отвечает как CFO\n"
        "CSV-файл → разбор выписки Т-Банка\n"
        "Фото/скриншоты → распознавание данных\n\n"
        "/report — Финансовый отчёт\n"
        "/portfolio — Портфель (банки + крипто)\n"
        "/chart — Круговая диаграмма портфеля\n"
        "/expenses — График расходов (Т-Банк)\n"
        "/tinkoff — Сводка по Т-Банку\n"
        "/balances — Данные из скриншотов\n"
    )
