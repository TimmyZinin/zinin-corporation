"""Parser for Tinkoff Bank CSV statements."""

import csv
import io
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Expected CSV header columns (semicolon-separated)
EXPECTED_COLUMNS = [
    "Дата операции",
    "Дата платежа",
    "Номер карты",
    "Статус",
    "Сумма операции",
    "Валюта операции",
    "Сумма платежа",
    "Валюта платежа",
    "Кэшбэк",
    "Категория",
    "MCC",
    "Описание",
    "Бонусы (включая кэшбэк)",
    "Округление на инвесткопилку",
    "Сумма операции с округлением",
]


def is_tinkoff_csv(text: str) -> bool:
    """Check if text looks like a Tinkoff CSV statement (by header)."""
    first_line = text.strip().split("\n")[0]
    return "Дата операции" in first_line and "Сумма операции" in first_line


def parse_tinkoff_csv(content: str) -> dict:
    """Parse a Tinkoff CSV statement into structured data.

    Returns dict with:
        transactions: list of parsed transactions
        summary: dict with totals
        cards: list of unique card numbers
        period: dict with start/end dates
        errors: list of parsing errors
    """
    transactions = []
    errors = []

    reader = csv.DictReader(
        io.StringIO(content),
        delimiter=";",
        quotechar='"',
    )

    for i, row in enumerate(reader):
        try:
            tx = _parse_row(row)
            if tx:
                transactions.append(tx)
        except Exception as e:
            errors.append(f"Row {i + 2}: {e}")

    # Sort by date (newest first)
    transactions.sort(key=lambda x: x.get("date", ""), reverse=True)

    # Build summary
    summary = _build_summary(transactions)

    # Extract unique cards
    cards = sorted(set(tx["card"] for tx in transactions if tx.get("card")))

    # Period
    dates = [tx["date"] for tx in transactions if tx.get("date")]
    period = {
        "start": min(dates) if dates else None,
        "end": max(dates) if dates else None,
    }

    return {
        "source": "tinkoff",
        "transactions": transactions,
        "summary": summary,
        "cards": cards,
        "period": period,
        "total_count": len(transactions),
        "errors": errors,
        "parsed_at": datetime.now().isoformat(),
    }


def _parse_amount(value: str) -> float:
    """Parse '−1 500,00' or '5000,00' to float."""
    if not value:
        return 0.0
    cleaned = value.strip().replace("\u2212", "-").replace("\u2013", "-")
    cleaned = cleaned.replace(" ", "").replace("\u00a0", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _parse_row(row: dict) -> Optional[dict]:
    """Parse a single CSV row into a transaction dict."""
    status = row.get("Статус", "").strip()
    # Skip failed transactions
    if status == "FAILED":
        return None

    date_str = row.get("Дата операции", "").strip()
    date = ""
    if date_str:
        try:
            dt = datetime.strptime(date_str, "%d.%m.%Y %H:%M:%S")
            date = dt.isoformat()
        except ValueError:
            date = date_str

    payment_date = row.get("Дата платежа", "").strip()

    amount = _parse_amount(row.get("Сумма операции", ""))
    payment_amount = _parse_amount(row.get("Сумма платежа", ""))
    currency = row.get("Валюта операции", "RUB").strip()
    payment_currency = row.get("Валюта платежа", "RUB").strip()

    card = row.get("Номер карты", "").strip()
    category = row.get("Категория", "").strip()
    mcc = row.get("MCC", "").strip()
    description = row.get("Описание", "").strip()

    cashback = _parse_amount(row.get("Кэшбэк", ""))
    bonuses = _parse_amount(row.get("Бонусы (включая кэшбэк)", ""))

    # Determine operation type
    if amount > 0:
        op_type = "credit"
    elif category == "Переводы" and "Между своими" in description:
        op_type = "internal_transfer"
    elif category == "Переводы":
        op_type = "transfer"
    else:
        op_type = "debit"

    return {
        "date": date,
        "payment_date": payment_date,
        "card": card,
        "status": status,
        "amount": amount,
        "currency": currency,
        "payment_amount": payment_amount,
        "payment_currency": payment_currency,
        "category": category,
        "mcc": mcc,
        "description": description,
        "cashback": cashback,
        "bonuses": bonuses,
        "op_type": op_type,
    }


def _build_summary(transactions: list[dict]) -> dict:
    """Build summary statistics from transactions."""
    income = 0.0
    expenses = 0.0
    internal = 0.0
    categories: dict[str, float] = {}

    for tx in transactions:
        amt = tx.get("amount", 0)
        op = tx.get("op_type", "")
        cat = tx.get("category", "Другое") or "Другое"

        if op == "credit":
            income += amt
        elif op == "internal_transfer":
            internal += abs(amt)
        elif op in ("debit", "transfer"):
            expenses += abs(amt)
            categories[cat] = categories.get(cat, 0) + abs(amt)

    top_categories = sorted(categories.items(), key=lambda x: x[1], reverse=True)

    return {
        "income": round(income, 2),
        "expenses": round(expenses, 2),
        "internal_transfers": round(internal, 2),
        "net": round(income - expenses, 2),
        "top_categories": top_categories[:15],
        "total_transactions": len(transactions),
    }


def format_summary_text(parsed: dict) -> str:
    """Format parsed CSV data into a readable text summary."""
    s = parsed["summary"]
    p = parsed["period"]

    lines = [
        f"Выписка Т-Банк: {p['start'][:10] if p.get('start') else '?'} — {p['end'][:10] if p.get('end') else '?'}",
        f"Операций: {parsed['total_count']} (карты: {', '.join(parsed['cards'])})",
        "",
        f"Доходы: +{s['income']:,.2f} RUB",
        f"Расходы: -{s['expenses']:,.2f} RUB",
        f"Нетто: {s['net']:,.2f} RUB",
    ]

    if s["internal_transfers"] > 0:
        lines.append(f"Переводы между счетами: {s['internal_transfers']:,.2f} RUB")

    if s["top_categories"]:
        lines.append("")
        lines.append("Топ расходов по категориям:")
        for cat, amt in s["top_categories"]:
            lines.append(f"  {cat}: {amt:,.2f} RUB")

    if parsed["errors"]:
        lines.append(f"\n(Ошибки парсинга: {len(parsed['errors'])})")

    return "\n".join(lines)
