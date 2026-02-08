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
        "/chart — 📊 Финансовый дашборд\n"
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
    """Generate comprehensive financial dashboard."""
    status = await message.answer("📊 Строю финансовый дашборд...")
    stop = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(message, stop))

    try:
        data = await asyncio.wait_for(
            asyncio.to_thread(_collect_all_financial_data),
            timeout=90,
        )
        logger.info(f"Chart: total=${data.get('total_usd', 0):.0f}")

        if not data or data.get("total_usd", 0) < 1:
            await message.answer("Нет данных для графика. Попробуйте /portfolio сначала.")
            return

        from ..charts import render_financial_dashboard
        png = render_financial_dashboard(data)

        if not png:
            # Fallback to basic pie chart
            from ..charts import portfolio_pie
            png = portfolio_pie(data.get("crypto", {}), "Портфель Zinin Corp")

        if not png:
            await message.answer("Не удалось построить дашборд.")
            return

        caption = _build_chart_caption(data)
        photo = BufferedInputFile(png, filename="dashboard.png")
        await message.answer_photo(photo=photo, caption=caption, parse_mode=ParseMode.HTML)

        # Send detailed text if there's more data than fits in caption
        full_text = _build_chart_text(data)
        if full_text and len(caption) > 200:
            await message.answer(full_text, parse_mode=ParseMode.HTML)

    except asyncio.TimeoutError:
        logger.error("Chart: data collection timed out (90s)")
        await message.answer("Таймаут: сбор данных занял больше 90 секунд.")
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


def _build_chart_caption(data: dict) -> str:
    """Build short caption for the chart photo (max 1024 chars)."""
    total = data.get("total_usd", 0)

    # Merge all sources and sort
    all_sources: list[tuple[str, float, str]] = []
    for name, val in data.get("crypto", {}).items():
        if val > 0.5:
            all_sources.append((name, val, ""))
    for name, info in data.get("fiat", {}).items():
        all_sources.append((name, info["usd"], info.get("original", "")))
    for name, info in data.get("manual", {}).items():
        all_sources.append((name, info["usd"], info.get("original", "")))

    all_sources.sort(key=lambda x: -x[1])
    top = all_sources[:5]

    lines = [f"<b>Портфель — ${total:,.0f}</b>"]
    for name, val, orig in top:
        suffix = f" ({orig})" if orig else ""
        lines.append(f"  {name}: ${val:,.0f}{suffix}")

    if len(all_sources) > 5:
        lines.append(f"  ...и ещё {len(all_sources) - 5} источников")

    return "\n".join(lines)


def _build_chart_text(data: dict) -> str:
    """Build detailed text message with full breakdown table."""
    rows = []
    for name, val in sorted(data.get("crypto", {}).items(), key=lambda x: -x[1]):
        if val > 0.5:
            rows.append([name, f"${val:,.0f}"])
    for name, info in data.get("fiat", {}).items():
        rows.append([name, f"${info['usd']:,.0f} ({info.get('original', '')})"])
    for name, info in data.get("manual", {}).items():
        rows.append([name, f"${info['usd']:,.0f} ({info.get('original', '')})"])

    if not rows:
        return ""

    total = data.get("total_usd", 0)
    rows.append(["ИТОГО", f"${total:,.0f}"])

    table = mono_table(["Источник", "Баланс"], rows)

    # Add T-Bank mini summary
    tbank = data.get("tbank_summary")
    tbank_line = ""
    if tbank:
        income = tbank.get("income", 0)
        expenses = tbank.get("expenses", 0)
        tbank_line = f"\nT-Bank: +{income:,.0f} / -{expenses:,.0f} RUB"

    return f"{table}{tbank_line}"


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

    def _parse_usd_total(text: str) -> float | None:
        m = re.search(r"\$([0-9,.]+)\s+USD\s+total", text)
        return float(m.group(1).replace(",", "")) if m else None

    def _parse_itogo(text: str) -> float | None:
        if "ИТОГО" not in text:
            return None
        m = re.search(r"\$([0-9,.]+)", text.split("ИТОГО")[-1])
        return float(m.group(1).replace(",", "")) if m else None

    # EVM via Moralis
    if os.environ.get("MORALIS_API_KEY"):
        try:
            from src.tools.financial.moralis_evm import EVMPortfolioTool
            result = EVMPortfolioTool()._run("")
            val = _parse_usd_total(result)
            if val is not None:
                portfolio["EVM (5 chains)"] = val
            else:
                logger.warning("Chart/EVM: no total parsed from result")
        except Exception as e:
            logger.warning(f"Chart/EVM error: {e}")
    else:
        logger.info("Chart/EVM: MORALIS_API_KEY not set, skipping")

    # Papaya
    try:
        from src.tools.financial.papaya import PapayaPositionsTool
        result = PapayaPositionsTool()._run()
        val = _parse_itogo(result)
        if val is not None:
            portfolio["Papaya"] = val
        else:
            logger.warning("Chart/Papaya: no ИТОГО parsed")
    except Exception as e:
        logger.warning(f"Chart/Papaya error: {e}")

    # Eventum
    try:
        from src.tools.financial.eventum import EventumPortfolioTool
        result = EventumPortfolioTool()._run()
        val = _parse_itogo(result)
        if val is not None:
            portfolio["Eventum L3"] = val
        else:
            logger.warning("Chart/Eventum: no ИТОГО parsed")
    except Exception as e:
        logger.warning(f"Chart/Eventum error: {e}")

    # Stacks
    try:
        from src.tools.financial.stacks import StacksPortfolioTool
        result = StacksPortfolioTool()._run()
        if "ИТОГО STX:" in result:
            m = re.search(r"ИТОГО STX:\s*([0-9,.]+)", result)
            if m:
                stx_amount = float(m.group(1).replace(",", ""))
                if stx_amount > 0:
                    portfolio["Stacks"] = stx_amount * 0.5
        else:
            logger.warning("Chart/Stacks: no ИТОГО STX parsed")
    except Exception as e:
        logger.warning(f"Chart/Stacks error: {e}")

    # Solana
    try:
        from src.tools.financial.helius_solana import SolanaPortfolioTool
        result = SolanaPortfolioTool()._run("")
        val = _parse_usd_total(result)
        if val is not None:
            portfolio["Solana"] = val
        else:
            logger.warning("Chart/Solana: no total parsed")
    except Exception as e:
        logger.warning(f"Chart/Solana error: {e}")

    # TON
    try:
        from src.tools.financial.tonapi import TONPortfolioTool
        result = TONPortfolioTool()._run("")
        val = _parse_usd_total(result)
        if val is not None:
            portfolio["TON"] = val
        else:
            logger.warning("Chart/TON: no total parsed")
    except Exception as e:
        logger.warning(f"Chart/TON error: {e}")

    logger.info(f"Chart portfolio collected: {portfolio}")
    return portfolio


def _collect_all_financial_data() -> dict:
    """Collect ALL financial data: crypto + fiat + manual sources."""
    import re
    from datetime import datetime

    result: dict = {
        "crypto": {},
        "fiat": {},
        "manual": {},
        "total_usd": 0.0,
        "tbank_summary": None,
        "rates": {},
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    # 1. Crypto portfolio
    result["crypto"] = _collect_portfolio_data()

    # 2. Exchange rates (fetch once, reuse)
    try:
        from src.tools.financial.forex import get_rates
        rates_data = get_rates("USD")
        result["rates"] = rates_data.get("rates", {})
    except Exception as e:
        logger.warning(f"Chart/forex rates: {e}")

    # 3. T-Bank summary
    try:
        from ..transaction_storage import get_summary
        tbank = get_summary()
        if tbank:
            result["tbank_summary"] = tbank
            net_rub = tbank.get("net", 0)
            rub_rate = result["rates"].get("RUB")
            if net_rub and rub_rate:
                usd_val = net_rub / rub_rate
                result["fiat"]["T-Bank"] = {
                    "usd": round(usd_val, 2),
                    "original": f"{net_rub:,.0f} RUB",
                }
    except Exception as e:
        logger.warning(f"Chart/T-Bank: {e}")

    # 4. Telegram @wallet from config
    try:
        from src.tools.financial.base import load_financial_config
        config = load_financial_config()
        manual = config.get("manual_sources", {})
        tg_wallet = manual.get("telegram_wallet", {})
        balance_str = tg_wallet.get("last_known_balance", "")
        if balance_str:
            m = re.search(r"([0-9,.]+)", balance_str.replace(",", ""))
            if m:
                amount = float(m.group(1))
                cur = "RUB"
                for c in ["USD", "EUR", "GEL", "TRY", "THB"]:
                    if c in balance_str.upper():
                        cur = c
                        break
                rub_rate = result["rates"].get(cur, 1.0)
                usd_val = amount / rub_rate if cur != "USD" else amount
                result["manual"]["TG @wallet"] = {
                    "usd": round(usd_val, 2),
                    "original": balance_str.strip(),
                }
    except Exception as e:
        logger.warning(f"Chart/TG wallet: {e}")

    # 5. Screenshot balances
    try:
        screenshots = get_latest_balances()
        for source, data in screenshots.items():
            for acc in data.get("accounts", []):
                balance = acc.get("balance")
                currency = str(acc.get("currency", "USD")).upper()
                if balance is None:
                    continue
                try:
                    num_balance = float(str(balance).replace(",", "").replace(" ", ""))
                except (ValueError, TypeError):
                    continue
                rate = result["rates"].get(currency, 1.0)
                usd_val = num_balance / rate if currency != "USD" else num_balance
                key = source
                if key in result["manual"]:
                    key = f"{source} ({currency})"
                result["manual"][key] = {
                    "usd": round(usd_val, 2),
                    "original": f"{num_balance:,.0f} {currency}",
                }
    except Exception as e:
        logger.warning(f"Chart/screenshots: {e}")

    # Total
    crypto_total = sum(result["crypto"].values())
    fiat_total = sum(v["usd"] for v in result["fiat"].values())
    manual_total = sum(v["usd"] for v in result["manual"].values())
    result["total_usd"] = round(crypto_total + fiat_total + manual_total, 2)

    logger.info(
        f"Chart all data: crypto=${crypto_total:.0f}, "
        f"fiat=${fiat_total:.0f}, manual=${manual_total:.0f}, "
        f"total=${result['total_usd']:.0f}"
    )
    return result


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
        "/chart — Финансовый дашборд (все источники)\n"
        "/expenses — График расходов (Т-Банк)\n"
        "/tinkoff — Сводка по Т-Банку\n"
        "/balances — Данные из скриншотов\n"
        "/status — Статус коннекторов\n"
    )
