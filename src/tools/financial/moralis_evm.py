"""
Moralis — EVM multi-chain crypto portfolio & transactions.

API Docs: https://docs.moralis.io/web3-data-api
Base URL: https://deep-index.moralis.io/api/v2.2
Auth: X-API-Key header

Supported chains: eth, polygon, arbitrum, base, bsc (0x1, 0x89, 0xa4b1, 0x2105, 0x38)
Key endpoints:
- GET /wallets/{address}/net-worth — full portfolio value
- GET /wallets/{address}/tokens — token balances
- GET /wallets/{address}/history — transaction history
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Type

import httpx
from pydantic import BaseModel, Field

from .base import FinancialBaseTool, load_financial_config

logger = logging.getLogger(__name__)

# Chain name → Moralis chain parameter
CHAIN_MAP = {
    "eth": "0x1",
    "ethereum": "0x1",
    "polygon": "0x89",
    "arbitrum": "0xa4b1",
    "base": "0x2105",
    "bsc": "0x38",
}

CHAIN_NAMES = {
    "0x1": "Ethereum",
    "0x89": "Polygon",
    "0xa4b1": "Arbitrum",
    "0x2105": "Base",
    "0x38": "BSC",
}


def _get_addresses() -> list[str]:
    """Get EVM wallet addresses from config."""
    config = load_financial_config()
    return config.get("crypto_wallets", {}).get("evm", {}).get("addresses", [])


def _get_chains() -> list[str]:
    """Get enabled chains from config."""
    config = load_financial_config()
    chain_names = config.get("crypto_wallets", {}).get("evm", {}).get(
        "chains", ["eth", "polygon", "arbitrum", "base", "bsc"]
    )
    return [CHAIN_MAP.get(c, c) for c in chain_names]


# ──────────────────────────────────────────────────────────
# Tool: EVM Portfolio
# ──────────────────────────────────────────────────────────

class EVMPortfolioInput(BaseModel):
    address: Optional[str] = Field(
        None,
        description=(
            "EVM wallet address (0x...). "
            "Leave empty to check all configured addresses."
        ),
    )
    chains: Optional[str] = Field(
        None,
        description=(
            "Comma-separated chains: eth, polygon, arbitrum, base, bsc. "
            "Leave empty for all configured chains."
        ),
    )


class EVMPortfolioTool(FinancialBaseTool):
    name: str = "evm_portfolio"
    description: str = (
        "Get full EVM crypto portfolio: all tokens with USD balances, "
        "across Ethereum, Polygon, Arbitrum, Base, BSC. "
        "One call = complete picture of all crypto holdings on EVM chains."
    )
    args_schema: Type[BaseModel] = EVMPortfolioInput
    service_name: str = "moralis"

    def _run(self, address: str = None, chains: str = None) -> str:
        return self._safe_run(self._fetch_portfolio, address, chains)

    def _fetch_portfolio(self, address: str, chains: str) -> str:
        addresses = [address] if address else _get_addresses()
        if not addresses:
            return (
                "No EVM wallet addresses configured. "
                "Add addresses to config/financial_sources.yaml"
            )

        chain_ids = (
            [CHAIN_MAP.get(c.strip(), c.strip()) for c in chains.split(",")]
            if chains
            else _get_chains()
        )

        creds = self._get_credentials()
        headers = {
            "X-API-Key": creds["api_key"],
            "Accept": "application/json",
        }
        client = httpx.Client(
            base_url=creds["base_url"],
            headers=headers,
            timeout=30.0,
        )

        all_results = []
        grand_total = Decimal("0")

        try:
            for addr in addresses:
                addr_short = f"{addr[:6]}...{addr[-4:]}"
                lines = [f"  Wallet {addr_short}:"]

                for chain_id in chain_ids:
                    chain_name = CHAIN_NAMES.get(chain_id, chain_id)
                    try:
                        # Get token balances with prices
                        response = client.get(
                            f"/wallets/{addr}/tokens",
                            params={
                                "chain": chain_id,
                                "exclude_spam": "true",
                            },
                        )
                        response.raise_for_status()
                        data = response.json()
                        tokens = data if isinstance(data, list) else data.get("result", [])

                        chain_total = Decimal("0")
                        token_lines = []
                        for token in tokens:
                            symbol = token.get("symbol", "???")
                            balance_raw = token.get("balance", "0")
                            decimals = int(token.get("decimals", 18))
                            balance = Decimal(balance_raw) / Decimal(10 ** decimals)
                            usd_price = token.get("usd_price")
                            usd_value = Decimal("0")
                            if usd_price:
                                usd_value = balance * Decimal(str(usd_price))
                                chain_total += usd_value

                            if usd_value >= Decimal("0.01") or balance > 0:
                                token_lines.append(
                                    f"      {symbol}: {balance:.4f} (${usd_value:,.2f})"
                                )

                        # Sort by USD value descending
                        token_lines.sort(
                            key=lambda x: float(x.split("$")[-1].replace(",", "").rstrip(")")),
                            reverse=True,
                        )

                        if token_lines:
                            lines.append(f"    {chain_name} (${chain_total:,.2f}):")
                            lines.extend(token_lines[:15])
                            if len(token_lines) > 15:
                                lines.append(f"      ... +{len(token_lines) - 15} more tokens")
                        grand_total += chain_total

                    except Exception as e:
                        lines.append(f"    {chain_name}: error — {e}")

                all_results.extend(lines)
        finally:
            client.close()

        header = [f"EVM PORTFOLIO (${grand_total:,.2f} USD total):"]
        return "\n".join(header + all_results)


# ──────────────────────────────────────────────────────────
# Tool: EVM Transactions
# ──────────────────────────────────────────────────────────

class EVMTransactionsInput(BaseModel):
    address: str = Field(
        ...,
        description="EVM wallet address (0x...).",
    )
    chain: str = Field(
        default="eth",
        description="Chain: eth, polygon, arbitrum, base, bsc.",
    )
    limit: int = Field(
        default=20,
        description="Max number of transactions to return (max 50).",
    )


class EVMTransactionsTool(FinancialBaseTool):
    name: str = "evm_transactions"
    description: str = (
        "Get transaction history for an EVM wallet. "
        "Shows transfers, swaps, approvals with values in USD. "
        "Specify chain: eth, polygon, arbitrum, base, bsc."
    )
    args_schema: Type[BaseModel] = EVMTransactionsInput
    service_name: str = "moralis"

    def _run(self, address: str, chain: str = "eth", limit: int = 20) -> str:
        return self._safe_run(self._fetch_transactions, address, chain, limit)

    def _fetch_transactions(
        self, address: str, chain: str, limit: int
    ) -> str:
        chain_id = CHAIN_MAP.get(chain, chain)
        chain_name = CHAIN_NAMES.get(chain_id, chain)
        limit = min(limit, 50)

        creds = self._get_credentials()
        headers = {
            "X-API-Key": creds["api_key"],
            "Accept": "application/json",
        }
        client = httpx.Client(
            base_url=creds["base_url"],
            headers=headers,
            timeout=30.0,
        )

        try:
            response = client.get(
                f"/wallets/{address}/history",
                params={
                    "chain": chain_id,
                    "limit": str(limit),
                    "include_internal_transactions": "false",
                },
            )
            response.raise_for_status()
            data = response.json()
        finally:
            client.close()

        txs = data if isinstance(data, list) else data.get("result", [])
        if not txs:
            return f"No transactions found for {address[:10]}... on {chain_name}."

        addr_short = f"{address[:6]}...{address[-4:]}"
        lines = [f"EVM TRANSACTIONS ({chain_name}, {addr_short}):"]

        for tx in txs[:limit]:
            block_ts = tx.get("block_timestamp", "")
            if block_ts:
                try:
                    dt = datetime.fromisoformat(block_ts.replace("Z", "+00:00"))
                    date_str = dt.strftime("%Y-%m-%d %H:%M")
                except (ValueError, TypeError):
                    date_str = block_ts[:16]
            else:
                date_str = "N/A"

            category = tx.get("category", "unknown")
            summary = tx.get("summary", "")
            value = tx.get("value", "0")
            value_decimal = tx.get("value_decimal")

            # Native value
            native_str = ""
            if value_decimal:
                native_str = f" {value_decimal}"
            elif value and value != "0":
                try:
                    native_val = Decimal(value) / Decimal(10**18)
                    if native_val > 0:
                        native_str = f" {native_val:.6f}"
                except Exception:
                    pass

            # Token transfers
            transfers = tx.get("erc20_transfers", tx.get("token_transfers", []))
            transfer_str = ""
            if transfers:
                for t in transfers[:2]:
                    symbol = t.get("token_symbol", "???")
                    t_val = t.get("value_formatted", t.get("value", "0"))
                    direction = "in" if t.get("direction") == "receive" else "out"
                    transfer_str += f" [{direction} {t_val} {symbol}]"

            lines.append(
                f"  {date_str} | {category}{native_str}{transfer_str}"
                f"{f' | {summary}' if summary else ''}"
            )

        return "\n".join(lines)
