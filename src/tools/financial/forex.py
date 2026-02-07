"""CrewAI Tool: Forex exchange rates — free API, no key needed.

Uses open.er-api.com (based on central bank data).
Supports 166 currencies including RUB, GEL, TRY, THB.
"""

import logging
import time

import httpx
from crewai.tools import BaseTool

logger = logging.getLogger(__name__)

API_URL = "https://open.er-api.com/v6/latest/{base}"

# Cache rates for 1 hour (API updates daily)
_cache: dict = {}
_cache_ts: float = 0
CACHE_TTL = 3600

# Currencies relevant to Zinin Corp
CORP_CURRENCIES = ["RUB", "GEL", "TRY", "THB", "EUR", "GBP", "BTC"]


def get_rates(base: str = "USD") -> dict:
    """Fetch exchange rates with caching."""
    global _cache, _cache_ts

    base = base.upper()
    now = time.time()
    if _cache.get("base") == base and (now - _cache_ts) < CACHE_TTL:
        return _cache

    resp = httpx.get(API_URL.format(base=base), timeout=10)
    resp.raise_for_status()
    data = resp.json()

    if data.get("result") != "success":
        raise ValueError(f"API error: {data}")

    _cache = {
        "base": base,
        "rates": data["rates"],
        "updated": data.get("time_last_update_utc", "?"),
    }
    _cache_ts = now
    return _cache


def convert(amount: float, from_cur: str, to_cur: str) -> float:
    """Convert between any two currencies."""
    from_cur = from_cur.upper()
    to_cur = to_cur.upper()

    if from_cur == to_cur:
        return amount

    data = get_rates("USD")
    rates = data["rates"]

    if from_cur not in rates and from_cur != "USD":
        raise ValueError(f"Unknown currency: {from_cur}")
    if to_cur not in rates and to_cur != "USD":
        raise ValueError(f"Unknown currency: {to_cur}")

    # Convert to USD first, then to target
    usd_amount = amount / rates.get(from_cur, 1.0) if from_cur != "USD" else amount
    result = usd_amount * rates.get(to_cur, 1.0) if to_cur != "USD" else usd_amount
    return result


class ForexRatesTool(BaseTool):
    name: str = "forex_rates"
    description: str = (
        "Актуальные курсы валют (166 валют, обновляются ежедневно).\n"
        "Бесплатный API, без ключа.\n"
        "Поддерживает: RUB, GEL, TRY, THB, EUR, GBP, и другие.\n\n"
        "Использование:\n"
        "  forex_rates — курсы корпоративных валют к USD\n"
        "  forex_rates convert 85700 RUB USD — конвертация\n"
        "  forex_rates base=EUR — все курсы относительно EUR\n"
        "  forex_rates rate RUB — курс одной валюты к USD"
    )

    def _run(self, argument: str = "") -> str:
        try:
            arg = argument.strip().lower()

            # Convert mode: "convert 85700 RUB USD"
            if arg.startswith("convert"):
                parts = arg.split()
                if len(parts) < 4:
                    return "Формат: convert <сумма> <из_валюты> <в_валюту>. Пример: convert 85700 RUB USD"
                amount = float(parts[1])
                from_cur = parts[2].upper()
                to_cur = parts[3].upper()
                result = convert(amount, from_cur, to_cur)
                data = get_rates("USD")
                rate = data["rates"].get(from_cur, 1.0)
                return (
                    f"{amount:,.2f} {from_cur} = {result:,.2f} {to_cur}\n"
                    f"Курс: 1 USD = {rate:,.4f} {from_cur}\n"
                    f"Обновлено: {data['updated']}"
                )

            # Single rate: "rate RUB"
            if arg.startswith("rate"):
                parts = arg.split()
                cur = parts[1].upper() if len(parts) > 1 else "RUB"
                data = get_rates("USD")
                rate = data["rates"].get(cur)
                if rate is None:
                    return f"Валюта {cur} не найдена."
                return (
                    f"1 USD = {rate:,.4f} {cur}\n"
                    f"1 {cur} = {1/rate:,.6f} USD\n"
                    f"Обновлено: {data['updated']}"
                )

            # Default: show all corporate currencies
            data = get_rates("USD")
            rates = data["rates"]

            lines = [
                "КУРСЫ ВАЛЮТ (к USD):",
                f"Обновлено: {data['updated']}",
                "",
            ]

            for cur in CORP_CURRENCIES:
                rate = rates.get(cur)
                if rate:
                    inv = 1 / rate
                    lines.append(f"  {cur}: 1 USD = {rate:,.4f} {cur}  |  1 {cur} = {inv:,.6f} USD")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Forex rates fetch failed: {e}")
            return f"Ошибка курсов валют: {e}"
