"""
CoinGecko — Cryptocurrency price tool.

Free tier: 10-30 calls/min (enough for CFO agent).
Used by other tools for USD conversion.
"""

import logging
import time
from typing import Optional, Type

from pydantic import BaseModel, Field

from .base import FinancialBaseTool

logger = logging.getLogger(__name__)

# In-memory price cache to respect rate limits
_price_cache: dict[str, dict] = {}
_cache_ts: float = 0
_CACHE_TTL = 300  # 5 minutes


class CryptoPriceInput(BaseModel):
    coin_ids: str = Field(
        ...,
        description=(
            "Comma-separated CoinGecko coin IDs. "
            "Examples: bitcoin, ethereum, solana, the-open-network, "
            "matic-network, toncoin. "
            "Use 'top' for BTC+ETH+SOL+TON."
        ),
    )
    vs_currencies: str = Field(
        default="usd",
        description="Comma-separated fiat currencies: usd, rub, try, thb, gel",
    )


class CryptoPriceTool(FinancialBaseTool):
    name: str = "crypto_price"
    description: str = (
        "Get current cryptocurrency prices in USD (and other fiat). "
        "Supports 15,000+ coins via CoinGecko. "
        "Use for portfolio valuation and currency conversion."
    )
    args_schema: Type[BaseModel] = CryptoPriceInput
    service_name: str = "coingecko"

    def _run(self, coin_ids: str, vs_currencies: str = "usd") -> str:
        return self._safe_run(self._fetch_prices, coin_ids, vs_currencies)

    def _fetch_prices(self, coin_ids: str, vs_currencies: str) -> str:
        global _price_cache, _cache_ts

        if coin_ids.strip().lower() == "top":
            coin_ids = "bitcoin,ethereum,solana,the-open-network"

        # Check cache
        now = time.time()
        cache_key = f"{coin_ids}:{vs_currencies}"
        if now - _cache_ts < _CACHE_TTL and cache_key in _price_cache:
            data = _price_cache[cache_key]
            return self._format_prices(data, "(cached)")

        # Fetch fresh data
        creds = self._get_credentials()
        params = {
            "ids": coin_ids.strip(),
            "vs_currencies": vs_currencies.strip(),
            "include_24hr_change": "true",
            "include_market_cap": "true",
        }
        # CoinGecko uses x-cg-demo-key or x-cg-pro-key header
        import httpx
        headers = {
            "Content-Type": "application/json",
            "x-cg-demo-key": creds.get("api_key", ""),
        }
        client = httpx.Client(
            base_url=creds["base_url"],
            headers=headers,
            timeout=30.0,
        )
        try:
            response = client.get("/simple/price", params=params)
            response.raise_for_status()
            data = response.json()
        finally:
            client.close()

        # Update cache
        _price_cache[cache_key] = data
        _cache_ts = now

        return self._format_prices(data)

    @staticmethod
    def _format_prices(data: dict, suffix: str = "") -> str:
        if not data:
            return "No price data available."

        lines = [f"CRYPTO PRICES {suffix}".strip() + ":"]
        for coin_id, prices in data.items():
            name = coin_id.replace("-", " ").title()
            parts = []
            for currency, value in prices.items():
                if currency.endswith("_24h_change"):
                    continue
                if currency.endswith("_market_cap"):
                    continue
                change_key = f"{currency}_24h_change"
                change = prices.get(change_key)
                change_str = ""
                if change is not None:
                    sign = "+" if change >= 0 else ""
                    change_str = f" ({sign}{change:.1f}%)"
                parts.append(
                    f"  {currency.upper()}: {value:,.2f}{change_str}"
                )
            mcap_usd = prices.get("usd_market_cap")
            mcap_str = ""
            if mcap_usd:
                if mcap_usd >= 1_000_000_000:
                    mcap_str = f" | MCap: ${mcap_usd/1e9:.1f}B"
                elif mcap_usd >= 1_000_000:
                    mcap_str = f" | MCap: ${mcap_usd/1e6:.0f}M"
            lines.append(f"  {name}{mcap_str}:")
            lines.extend(parts)
        return "\n".join(lines)


def get_usd_price(coin_id: str) -> Optional[float]:
    """
    Helper: get a single coin's USD price.
    Used by other financial tools for conversion.
    Returns None if unavailable.
    """
    global _price_cache, _cache_ts

    now = time.time()
    cache_key = f"{coin_id}:usd"

    # Check cache first
    if now - _cache_ts < _CACHE_TTL and cache_key in _price_cache:
        data = _price_cache[cache_key]
        return data.get(coin_id, {}).get("usd")

    # Try fetching
    try:
        from .base import CredentialBroker
        creds = CredentialBroker.get("coingecko")
        import httpx
        headers = {
            "x-cg-demo-key": creds.get("api_key", ""),
        }
        client = httpx.Client(
            base_url=creds["base_url"],
            headers=headers,
            timeout=15.0,
        )
        try:
            response = client.get(
                "/simple/price",
                params={"ids": coin_id, "vs_currencies": "usd"},
            )
            response.raise_for_status()
            data = response.json()
            _price_cache[cache_key] = data
            _cache_ts = now
            return data.get(coin_id, {}).get("usd")
        finally:
            client.close()
    except Exception as e:
        logger.warning(f"Could not fetch price for {coin_id}: {e}")
        return None
