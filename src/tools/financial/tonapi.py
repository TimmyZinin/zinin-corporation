"""
TonAPI — TON blockchain data API.

API Docs: https://tonapi.io/docs
Base URL: https://tonapi.io/v2
Auth: Bearer token (Authorization header)

Key endpoints:
- GET /accounts/{address} — account info + balance
- GET /accounts/{address}/jettons — jetton (token) balances
- GET /accounts/{address}/events — transaction history (Actions API)
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, Type

import httpx
from pydantic import BaseModel, Field

from .base import FinancialBaseTool, load_financial_config

logger = logging.getLogger(__name__)


def _get_addresses() -> list[str]:
    """Get TON wallet addresses from config."""
    config = load_financial_config()
    return config.get("crypto_wallets", {}).get("ton", {}).get("addresses", [])


# ──────────────────────────────────────────────────────────
# Tool: TON Portfolio
# ──────────────────────────────────────────────────────────

class TONPortfolioInput(BaseModel):
    address: Optional[str] = Field(
        None,
        description=(
            "TON wallet address (UQ... or EQ...). "
            "Leave empty to check all configured addresses."
        ),
    )


class TONPortfolioTool(FinancialBaseTool):
    name: str = "ton_portfolio"
    description: str = (
        "Get TON wallet portfolio: TON balance + all Jettons "
        "(USDT, NOT, DOGS, etc.). Values in USD."
    )
    args_schema: Type[BaseModel] = TONPortfolioInput
    service_name: str = "tonapi"

    def _run(self, address: str = None) -> str:
        return self._safe_run(self._fetch_portfolio, address)

    def _fetch_portfolio(self, address: str = None) -> str:
        addresses = [address] if address else _get_addresses()
        if not addresses:
            return (
                "No TON wallet addresses configured. "
                "Add addresses to config/financial_sources.yaml"
            )

        creds = self._get_credentials()
        headers = {
            "Authorization": f"Bearer {creds['api_key']}",
            "Accept": "application/json",
        }

        all_lines = []
        grand_total = Decimal("0")

        for addr in addresses:
            addr_short = f"{addr[:4]}...{addr[-4:]}" if len(addr) > 8 else addr
            lines = [f"  Wallet {addr_short}:"]

            client = httpx.Client(
                base_url=creds["base_url"],
                headers=headers,
                timeout=30.0,
            )
            try:
                # 1. Get TON balance
                acc_resp = client.get(f"/accounts/{addr}")
                acc_resp.raise_for_status()
                acc_data = acc_resp.json()

                ton_nanotons = int(acc_data.get("balance", 0))
                ton_balance = Decimal(ton_nanotons) / Decimal(10**9)

                # Get TON price
                ton_usd = Decimal("0")
                try:
                    from .coingecko import get_usd_price
                    price = get_usd_price("the-open-network")
                    if price:
                        ton_usd = ton_balance * Decimal(str(price))
                except Exception:
                    pass

                lines.append(f"    TON: {ton_balance:.4f} (${ton_usd:,.2f})")
                grand_total += ton_usd

                status = acc_data.get("status", "unknown")
                lines.append(f"    Status: {status}")

                # 2. Get Jetton (token) balances
                jettons_resp = client.get(
                    f"/accounts/{addr}/jettons",
                    params={"currencies": "usd"},
                )
                jettons_resp.raise_for_status()
                jettons_data = jettons_resp.json()
                jettons = jettons_data.get("balances", jettons_data) if isinstance(jettons_data, dict) else jettons_data

                jetton_lines = []
                for jetton in jettons:
                    jw = jetton.get("jetton", {})
                    symbol = jw.get("symbol", "???")
                    decimals = int(jw.get("decimals", 9))
                    balance_raw = jetton.get("balance", "0")
                    balance = Decimal(str(balance_raw)) / Decimal(10 ** decimals)

                    # USD value from price field
                    price_data = jetton.get("price", {})
                    usd_price = price_data.get("prices", {}).get("USD", 0) if price_data else 0
                    usd_value = balance * Decimal(str(usd_price)) if usd_price else Decimal("0")

                    if balance > 0:
                        jetton_lines.append((symbol, balance, usd_value))
                        grand_total += usd_value

                # Sort by USD value
                jetton_lines.sort(key=lambda x: x[2], reverse=True)
                for symbol, balance, usd_value in jetton_lines[:15]:
                    usd_str = f"(${usd_value:,.2f})" if usd_value > 0 else ""
                    lines.append(f"    {symbol}: {balance:,.4f} {usd_str}")
                if len(jetton_lines) > 15:
                    lines.append(f"    ... +{len(jetton_lines) - 15} more jettons")

            except Exception as e:
                lines.append(f"    Error: {e}")
            finally:
                client.close()

            all_lines.extend(lines)

        header = [f"TON PORTFOLIO (${grand_total:,.2f} USD total):"]
        return "\n".join(header + all_lines)


# ──────────────────────────────────────────────────────────
# Tool: TON Transactions
# ──────────────────────────────────────────────────────────

class TONTransactionsInput(BaseModel):
    address: str = Field(
        ..., description="TON wallet address (UQ... or EQ...)."
    )
    limit: int = Field(
        default=20,
        description="Max transactions to return (max 50).",
    )


class TONTransactionsTool(FinancialBaseTool):
    name: str = "ton_transactions"
    description: str = (
        "Get TON transaction history. Actions API provides "
        "human-readable transaction descriptions. "
        "Shows: transfers, swaps, NFT operations, staking."
    )
    args_schema: Type[BaseModel] = TONTransactionsInput
    service_name: str = "tonapi"

    def _run(self, address: str, limit: int = 20) -> str:
        return self._safe_run(self._fetch_transactions, address, limit)

    def _fetch_transactions(self, address: str, limit: int) -> str:
        limit = min(limit, 50)
        creds = self._get_credentials()
        headers = {
            "Authorization": f"Bearer {creds['api_key']}",
            "Accept": "application/json",
        }

        client = httpx.Client(
            base_url=creds["base_url"],
            headers=headers,
            timeout=30.0,
        )
        try:
            response = client.get(
                f"/accounts/{address}/events",
                params={"limit": limit},
            )
            response.raise_for_status()
            data = response.json()
        finally:
            client.close()

        events = data.get("events", data) if isinstance(data, dict) else data
        if not events:
            return f"No transactions for {address[:8]}..."

        addr_short = f"{address[:4]}...{address[-4:]}" if len(address) > 8 else address
        lines = [f"TON TRANSACTIONS ({addr_short}):"]

        for event in events[:limit]:
            ts = event.get("timestamp", 0)
            date_str = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "N/A"

            actions = event.get("actions", [])
            for action in actions:
                action_type = action.get("type", "Unknown")
                status = action.get("status", "ok")
                simple = action.get("simple_preview", {})
                description = simple.get("description", "")

                # Parse specific action types
                details = ""
                if action_type == "TonTransfer":
                    transfer = action.get("TonTransfer", {})
                    amount_nanotons = int(transfer.get("amount", 0))
                    amount = Decimal(amount_nanotons) / Decimal(10**9)
                    sender = transfer.get("sender", {}).get("address", "")
                    recipient = transfer.get("recipient", {}).get("address", "")
                    direction = "IN" if recipient == address else "OUT"
                    details = f"{direction} {amount:.4f} TON"
                    comment = transfer.get("comment", "")
                    if comment:
                        details += f' "{comment[:40]}"'

                elif action_type == "JettonTransfer":
                    transfer = action.get("JettonTransfer", {})
                    amount_raw = transfer.get("amount", "0")
                    jetton = transfer.get("jetton", {})
                    symbol = jetton.get("symbol", "???")
                    decimals = int(jetton.get("decimals", 9))
                    amount = Decimal(str(amount_raw)) / Decimal(10 ** decimals)
                    direction = "IN" if transfer.get("recipient", {}).get("address") == address else "OUT"
                    details = f"{direction} {amount:,.4f} {symbol}"

                elif action_type == "JettonSwap":
                    swap = action.get("JettonSwap", {})
                    details = "SWAP"

                else:
                    details = description[:60] if description else action_type

                status_icon = "" if status == "ok" else " [FAILED]"
                lines.append(f"  {date_str} | {action_type}{status_icon} | {details}")

        return "\n".join(lines)
