"""CrewAI Tool: Eventum (EVEDEX L3) — check balances via Blockscout API.

Eventum is an Arbitrum Orbit L3 chain used by EVEDEX exchange.
Explorer runs Blockscout with public API — no key needed.
"""

import logging

import httpx
from crewai.tools import BaseTool

logger = logging.getLogger(__name__)

EXPLORER_API = "https://explorer.evedex.com/api/v2"


def _load_eventum_addresses() -> list[str]:
    """Load Eventum addresses from financial config (supports env var on Railway)."""
    from .base import load_financial_config
    config = load_financial_config()
    addrs = config.get("crypto_wallets", {}).get("eventum", {}).get("addresses", [])
    return [a for a in addrs if a]


def get_eventum_balance(address: str) -> dict | None:
    """Get native ETH + token balances on Eventum."""
    # Native balance
    resp = httpx.get(f"{EXPLORER_API}/addresses/{address}", timeout=10)
    resp.raise_for_status()
    addr_data = resp.json()

    eth_raw = int(addr_data.get("coin_balance") or "0")
    eth_balance = eth_raw / 1e18

    # Token balances
    resp = httpx.get(f"{EXPLORER_API}/addresses/{address}/tokens", timeout=10)
    resp.raise_for_status()
    token_data = resp.json()

    tokens = []
    for item in token_data.get("items", []):
        token_info = item.get("token", {})
        value_raw = int(item.get("value", "0"))
        decimals = int(token_info.get("decimals", "18"))
        balance = value_raw / 10**decimals

        if balance > 0:
            tokens.append({
                "symbol": token_info.get("symbol", "?"),
                "name": token_info.get("name", "?"),
                "balance": round(balance, 6),
                "contract": token_info.get("address_hash", ""),
            })

    if eth_balance == 0 and not tokens:
        return None

    return {
        "address": address,
        "eth_balance": round(eth_balance, 6),
        "tokens": tokens,
    }


class EventumPortfolioTool(BaseTool):
    name: str = "eventum_portfolio"
    description: str = (
        "Баланс на Eventum (EVEDEX L3 — Arbitrum Orbit).\n"
        "Проверяет ETH и токены (USDT, USDC, WETH, WBTC) через Blockscout API.\n"
        "Бесплатный API, без ключа.\n"
        "Параметр: EVM-адрес (опционально — если не указан, берёт из конфига)."
    )

    def _run(self, argument: str = "") -> str:
        try:
            if argument.strip().startswith("0x"):
                addresses = [argument.strip()]
            else:
                addresses = _load_eventum_addresses()

            if not addresses:
                return (
                    "Нет адресов Eventum для проверки. "
                    "Укажи адрес: eventum_portfolio 0x... "
                    "или добавь в config/financial_sources.yaml → crypto_wallets.eventum.addresses"
                )

            results = []
            for addr in addresses:
                try:
                    result = get_eventum_balance(addr)
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.debug(f"Eventum {addr[:10]}: {e}")

            if not results:
                return f"Eventum (EVEDEX L3): балансов не найдено. Проверено {len(addresses)} адрес(ов)."

            lines = ["EVENTUM (EVEDEX L3) — балансы:", ""]
            total_usd = 0

            for r in results:
                addr_short = r["address"][:6] + "..." + r["address"][-4:]
                lines.append(f"  [{addr_short}]")

                if r["eth_balance"] > 0:
                    lines.append(f"    ETH: {r['eth_balance']:,.6f}")

                for token in r["tokens"]:
                    lines.append(f"    {token['symbol']}: {token['balance']:,.6f}")
                    # Stablecoins count as USD
                    if token["symbol"] in ("USDT", "USDC", "DAI", "BUSD"):
                        total_usd += token["balance"]

                lines.append("")

            if total_usd > 0:
                lines.append(f"ИТОГО стейблкоинов: ~${total_usd:,.2f}")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Eventum portfolio fetch failed: {e}")
            return f"Ошибка Eventum: {e}"
