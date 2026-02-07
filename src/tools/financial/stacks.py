"""CrewAI Tool: Stacks (STX) blockchain — check balances via Hiro API.

Public API, no key needed. STX uses 6 decimals.
"""

import logging
import os
import yaml

import httpx
from crewai.tools import BaseTool

logger = logging.getLogger(__name__)

HIRO_API = "https://api.hiro.so"
STX_DECIMALS = 6


def _load_stacks_addresses() -> list[str]:
    """Load Stacks addresses from financial config."""
    for path in ["config/financial_sources.yaml", "/app/config/financial_sources.yaml"]:
        if os.path.exists(path):
            with open(path, "r") as f:
                config = yaml.safe_load(f) or {}
            addrs = config.get("crypto_wallets", {}).get("stacks", {}).get("addresses", [])
            return [a for a in addrs if a]
    return []


def get_stacks_balance(address: str) -> dict | None:
    """Get STX and token balances for one address."""
    url = f"{HIRO_API}/extended/v1/address/{address}/balances"
    resp = httpx.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    stx = data.get("stx", {})
    balance_micro = int(stx.get("balance", "0"))
    locked_micro = int(stx.get("locked", "0"))
    balance = balance_micro / 10**STX_DECIMALS
    locked = locked_micro / 10**STX_DECIMALS

    tokens = []
    for token_id, info in data.get("fungible_tokens", {}).items():
        token_balance = int(info.get("balance", "0"))
        if token_balance > 0:
            # Token name from contract ID (last part)
            name = token_id.split("::")[-1] if "::" in token_id else token_id
            tokens.append({"name": name, "balance_raw": token_balance, "contract": token_id})

    if balance == 0 and locked == 0 and not tokens:
        return None

    return {
        "address": address,
        "stx_balance": round(balance, 6),
        "stx_locked": round(locked, 6),
        "fungible_tokens": tokens,
    }


class StacksPortfolioTool(BaseTool):
    name: str = "stacks_portfolio"
    description: str = (
        "Баланс STX и токенов на блокчейне Stacks.\n"
        "Проверяет все Stacks-адреса Тима (из конфига).\n"
        "Показывает: баланс STX, залоченные STX, fungible токены.\n"
        "Бесплатный API (Hiro), без ключа.\n"
        "Параметр: Stacks-адрес (опционально — если не указан, берёт из конфига)."
    )

    def _run(self, argument: str = "") -> str:
        try:
            if argument.strip().startswith("SP") or argument.strip().startswith("SM"):
                addresses = [argument.strip()]
            else:
                addresses = _load_stacks_addresses()

            if not addresses:
                return (
                    "Нет Stacks-адресов для проверки. "
                    "Укажи адрес: stacks_portfolio address=SP... "
                    "или добавь в config/financial_sources.yaml → crypto_wallets.stacks.addresses"
                )

            results = []
            for addr in addresses:
                try:
                    result = get_stacks_balance(addr)
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.debug(f"Stacks {addr[:10]}: {e}")

            if not results:
                return f"Stacks: балансов не найдено. Проверено {len(addresses)} адрес(ов)."

            lines = ["STACKS (STX) — балансы:", ""]
            total_stx = 0

            for r in results:
                addr_short = r["address"][:6] + "..." + r["address"][-4:]
                lines.append(f"  [{addr_short}]")
                lines.append(f"    STX: {r['stx_balance']:,.6f}")
                total_stx += r["stx_balance"]

                if r["stx_locked"] > 0:
                    lines.append(f"    Залочено: {r['stx_locked']:,.6f} STX")

                for token in r["fungible_tokens"]:
                    lines.append(f"    {token['name']}: {token['balance_raw']}")

                lines.append("")

            lines.append(f"ИТОГО STX: {total_stx:,.6f}")
            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Stacks portfolio fetch failed: {e}")
            return f"Ошибка Stacks: {e}"
