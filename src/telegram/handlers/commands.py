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
        "/report — Финансовый отчёт + дашборд\n"
        "/portfolio — Сводка портфеля + график\n"
        "/chart — 📊 График портфеля\n"
        "/expenses — 📉 График расходов\n"
        "/tinkoff — Сводка по Т-Банку\n"
        "/balances — Данные из скриншотов\n"
        "/status — Статус коннекторов\n"
        "/help — Справка\n\n"
        "Можете написать любой финансовый вопрос, "
        "прислать скриншот или CSV-выписку из Т-Банка.",
    )


@router.message(Command("report"))
async def cmd_report(message: Message):
    """Full financial report with auto-generated dashboard chart."""
    status = await message.answer("📊 Готовлю финансовый отчёт... (30–60 сек)")
    stop = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(message, stop))

    try:
        result = await AgentBridge.run_financial_report()
        for chunk in format_for_telegram(result):
            await message.answer(chunk)

        # Auto-generate dashboard
        try:
            portfolio = await asyncio.to_thread(_collect_portfolio_data)
            if portfolio and sum(portfolio.values()) > 1:
                from ..transaction_storage import get_summary
                expenses = None
                tinkoff = get_summary()
                if tinkoff and tinkoff.get("top_categories"):
                    expenses = dict(tinkoff["top_categories"][:8])

                from ..charts import dashboard
                png = dashboard(portfolio, expenses)
                if png:
                    photo = BufferedInputFile(png, filename="dashboard.png")
                    await message.answer_photo(photo=photo, caption="Финансовый дашборд")
        except Exception as e:
            logger.debug(f"Dashboard generation skipped: {e}")

    except Exception as e:
        logger.error(f"Report error: {e}", exc_info=True)
        await message.answer(f"Ошибка: {str(e)[:300]}")
    finally:
        stop.set()
        await typing_task
        try:
            await status.delete()
        except Exception:
            pass


@router.message(Command("portfolio"))
async def cmd_portfolio(message: Message):
    """Portfolio summary with auto-generated chart."""
    status = await message.answer("💼 Собираю данные портфеля... (30–60 сек)")
    stop = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(message, stop))

    try:
        # Run agent for text summary
        result = await AgentBridge.run_portfolio_summary()
        for chunk in format_for_telegram(result):
            await message.answer(chunk)

        # Auto-generate and send chart
        try:
            portfolio = await asyncio.to_thread(_collect_portfolio_data)
            if portfolio and sum(portfolio.values()) > 1:
                from ..charts import portfolio_pie
                png = portfolio_pie(portfolio, "Портфель Zinin Corp")
                if png:
                    photo = BufferedInputFile(png, filename="portfolio.png")
                    total = sum(portfolio.values())
                    await message.answer_photo(
                        photo=photo,
                        caption=f"Портфель — ${total:,.0f}",
                        parse_mode=ParseMode.HTML,
                    )
        except Exception as e:
            logger.debug(f"Chart generation skipped: {e}")

    except Exception as e:
        logger.error(f"Portfolio error: {e}", exc_info=True)
        await message.answer(f"Ошибка: {str(e)[:300]}")
    finally:
        stop.set()
        await typing_task
        try:
            await status.delete()
        except Exception:
            pass


@router.message(Command("balances"))
async def cmd_balances(message: Message):
    """Show latest balances from parsed screenshots as a table."""
    latest = get_latest_balances()
    if not latest:
        await message.answer(
            "Пока нет данных из скриншотов.\n"
            "Пришлите скриншот баланса TBC Bank или @wallet."
        )
        return

    rows = []
    for source, data in latest.items():
        date_str = data.get("extracted_at", "?")[:10]
        for acc in data.get("accounts", []):
            balance = acc.get("balance", "?")
            currency = acc.get("currency", "")
            rows.append([source, f"{balance} {currency}", date_str])

    table = mono_table(["Источник", "Баланс", "Дата"], rows)
    await message.answer(
        f"<b>Данные из скриншотов</b>\n\n{table}",
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("tinkoff"))
async def cmd_tinkoff(message: Message):
    """Show Tinkoff transaction summary with tables and sparklines."""
    from ..transaction_storage import get_summary
    summary = get_summary()
    if not summary:
        await message.answer(
            "Пока нет данных по Т-Банку.\n"
            "Пришлите CSV-выписку из приложения Т-Банка."
        )
        return

    period_start = summary['period'].get('start', '?')[:10]
    period_end = summary['period'].get('end', '?')[:10]

    lines = [
        f"<b>Т-Банк</b>  {period_start} — {period_end}",
        f"Операций: {summary['total_count']}",
        "",
    ]

    # Summary table
    summary_rows = [
        ["Доходы", f"+{summary['income']:,.0f} RUB"],
        ["Расходы", f"-{summary['expenses']:,.0f} RUB"],
        ["Нетто", f"{summary['net']:,.0f} RUB"],
    ]
    lines.append(mono_table(["", "Сумма"], summary_rows))

    # Top categories
    if summary.get("top_categories"):
        lines.append("")
        cat_rows = [
            [cat, f"{amt:,.0f} RUB"]
            for cat, amt in summary["top_categories"][:8]
        ]
        lines.append(mono_table(["Категория", "Расход"], cat_rows))

    # Monthly sparkline
    if summary.get("monthly"):
        months = sorted(summary["monthly"].items())[-6:]
        expense_values = [m[1]["expenses"] for m in months]
        spark = sparkline(expense_values)
        month_labels = " ".join(m[0][-2:] for m in months)
        lines.append(f"\nРасходы по месяцам:\n{spark}\n{month_labels}")

    lines.append(f"\n<i>Обновлено: {summary['last_updated'][:16]}</i>")
    await message.answer("\n".join(lines), parse_mode=ParseMode.HTML)


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
    caption = f"<b>Расходы — RUB {total:,.0f}</b>\nТоп {len(categories)} категорий"

    photo = BufferedInputFile(png, filename="expenses.png")
    await message.answer_photo(photo=photo, caption=caption, parse_mode=ParseMode.HTML)


def _collect_portfolio_data() -> dict[str, float]:
    """Collect balance data from all tools for chart generation."""
    import os
    import re
    portfolio = {}

    # EVM via Moralis
    if os.environ.get("MORALIS_API_KEY"):
        try:
            from src.tools.financial.moralis_evm import EVMPortfolioTool
            tool = EVMPortfolioTool()
            result = tool._run("")
            if "total" in result.lower():
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
            m = re.search(r"\$([0-9,.]+)", result.split("ИТОГО")[-1])
            if m:
                portfolio["Eventum L3"] = float(m.group(1).replace(",", ""))
    except Exception as e:
        logger.debug(f"Eventum data: {e}")

    # Stacks
    try:
        from src.tools.financial.stacks import StacksPortfolioTool
        tool = StacksPortfolioTool()
        result = tool._run()
        if "ИТОГО STX:" in result:
            m = re.search(r"ИТОГО STX:\s*([0-9,.]+)", result)
            if m:
                stx_amount = float(m.group(1).replace(",", ""))
                if stx_amount > 0:
                    portfolio["Stacks"] = stx_amount * 0.5  # rough USD estimate
    except Exception as e:
        logger.debug(f"Stacks data: {e}")

    # Solana
    try:
        from src.tools.financial.helius_solana import SolanaPortfolioTool
        tool = SolanaPortfolioTool()
        result = tool._run("")
        if "total" in result.lower():
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
            m = re.search(r"\$([0-9,.]+)\s+USD\s+total", result)
            if m:
                portfolio["TON"] = float(m.group(1).replace(",", ""))
    except Exception as e:
        logger.debug(f"TON data: {e}")

    return portfolio


@router.message(Command("status"))
async def cmd_status(message: Message):
    """Show status of all financial data connectors."""
    import os
    from src.tools.financial.base import CredentialBroker, load_financial_config

    config = load_financial_config()
    crypto = config.get("crypto_wallets", {})
    banks = config.get("banks", {})
    payments = config.get("payments", {})

    rows = []

    # API-based connectors
    checks = [
        ("EVM (Moralis)", "moralis", crypto.get("evm", {}).get("enabled")),
        ("Solana (Helius)", "helius", crypto.get("solana", {}).get("enabled")),
        ("TON (TonAPI)", "tonapi", crypto.get("ton", {}).get("enabled")),
        ("Tribute", "tribute", payments.get("tribute", {}).get("enabled")),
        ("T-Bank", "tbank", banks.get("tbank", {}).get("enabled")),
    ]

    for name, service, enabled in checks:
        if not enabled:
            rows.append([name, "ВЫКЛ"])
        elif CredentialBroker.is_configured(service):
            rows.append([name, "OK"])
        else:
            rows.append([name, "НЕТ КЛЮЧА"])

    # Free API connectors (no key needed)
    free_checks = [
        ("Papaya", bool(crypto.get("evm", {}).get("addresses"))),
        ("Stacks", bool(crypto.get("stacks", {}).get("addresses"))),
        ("Eventum", bool(crypto.get("eventum", {}).get("addresses"))),
        ("CoinGecko", True),
        ("Forex", True),
    ]
    for name, has_config in free_checks:
        rows.append([name, "OK" if has_config else "НЕТ КОНФИГ"])

    # Data sources
    screenshots = get_latest_balances()
    from ..transaction_storage import get_summary
    tinkoff = get_summary()

    rows.append(["Скриншоты", f"{len(screenshots)} ист." if screenshots else "НЕТ ДАННЫХ"])
    rows.append(["Т-Банк CSV", f"{tinkoff['total_count']} оп." if tinkoff else "НЕТ ДАННЫХ"])

    table = mono_table(["Источник", "Статус"], rows)
    await message.answer(
        f"<b>Статус коннекторов</b>\n\n{table}",
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Текст → Маттиас отвечает как CFO\n"
        "CSV-файл → разбор выписки Т-Банка\n"
        "Фото/скриншоты → распознавание данных\n\n"
        "/report — Финансовый отчёт + дашборд\n"
        "/portfolio — Портфель + график\n"
        "/chart — Круговая диаграмма портфеля\n"
        "/expenses — График расходов (Т-Банк)\n"
        "/tinkoff — Сводка по Т-Банку\n"
        "/balances — Данные из скриншотов\n"
        "/status — Статус коннекторов\n"
    )
