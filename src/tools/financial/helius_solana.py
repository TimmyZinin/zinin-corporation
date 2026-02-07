"""
Helius — Solana blockchain data API.

API Docs: https://docs.helius.dev
Base URL: https://api.helius.xyz/v0
Auth: ?api-key= query parameter

Key endpoints:
- POST RPC (getAssetsByOwner) — DAS API for portfolio
- GET /addresses/{address}/transactions — enhanced tx history (70+ types)
- GET /addresses/{address}/balances — SOL + token balances
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
    """Get Solana wallet addresses from config."""
    config = load_financial_config()
    return config.get("crypto_wallets", {}).get("solana", {}).get("addresses", [])


# ──────────────────────────────────────────────────────────
# Tool: Solana Portfolio
# ──────────────────────────────────────────────────────────

class SolanaPortfolioInput(BaseModel):
    address: Optional[str] = Field(
        None,
        description=(
            "Solana wallet address. "
            "Leave empty to check all configured addresses."
        ),
    )


class SolanaPortfolioTool(FinancialBaseTool):
    name: str = "solana_portfolio"
    description: str = (
        "Get Solana wallet portfolio: SOL balance, SPL tokens, NFTs, "
        "staking positions. All values in USD."
    )
    args_schema: Type[BaseModel] = SolanaPortfolioInput
    service_name: str = "helius"

    def _run(self, address: str = None) -> str:
        return self._safe_run(self._fetch_portfolio, address)

    def _fetch_portfolio(self, address: str = None) -> str:
        addresses = [address] if address else _get_addresses()
        if not addresses:
            return (
                "No Solana wallet addresses configured. "
                "Add addresses to config/financial_sources.yaml"
            )

        creds = self._get_credentials()
        api_key = creds["api_key"]
        rpc_url = f"https://mainnet.helius-rpc.com/?api-key={api_key}"

        all_lines = []
        grand_total = Decimal("0")

        for addr in addresses:
            addr_short = f"{addr[:4]}...{addr[-4:]}"
            lines = [f"  Wallet {addr_short}:"]

            client = httpx.Client(timeout=30.0)
            try:
                # 1. Get SOL balance via RPC
                sol_resp = client.post(
                    rpc_url,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "getBalance",
                        "params": [addr],
                    },
                )
                sol_resp.raise_for_status()
                sol_data = sol_resp.json()
                sol_lamports = sol_data.get("result", {}).get("value", 0)
                sol_balance = Decimal(sol_lamports) / Decimal(10**9)

                # Get SOL price
                sol_usd = Decimal("0")
                try:
                    from .coingecko import get_usd_price
                    price = get_usd_price("solana")
                    if price:
                        sol_usd = sol_balance * Decimal(str(price))
                except Exception:
                    pass

                lines.append(f"    SOL: {sol_balance:.4f} (${sol_usd:,.2f})")
                grand_total += sol_usd

                # 2. Get token accounts via DAS API
                das_resp = client.post(
                    rpc_url,
                    json={
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "getAssetsByOwner",
                        "params": {
                            "ownerAddress": addr,
                            "page": 1,
                            "limit": 100,
                            "displayOptions": {
                                "showFungible": True,
                                "showNativeBalance": False,
                            },
                        },
                    },
                )
                das_resp.raise_for_status()
                das_data = das_resp.json()
                assets = das_data.get("result", {}).get("items", [])

                fungible_lines = []
                for asset in assets:
                    iface = asset.get("interface", "")
                    if iface not in ("FungibleToken", "FungibleAsset"):
                        continue

                    content = asset.get("content", {})
                    metadata = content.get("metadata", {})
                    symbol = metadata.get("symbol", "???")

                    token_info = asset.get("token_info", {})
                    balance_raw = token_info.get("balance", "0")
                    decimals = token_info.get("decimals", 0)
                    price_info = token_info.get("price_info", {})
                    usd_price = price_info.get("price_per_token", 0)

                    balance = Decimal(str(balance_raw)) / Decimal(10 ** decimals) if decimals else Decimal(str(balance_raw))
                    usd_value = balance * Decimal(str(usd_price)) if usd_price else Decimal("0")

                    if usd_value >= Decimal("0.01"):
                        fungible_lines.append((symbol, balance, usd_value))
                        grand_total += usd_value

                # Sort by USD value
                fungible_lines.sort(key=lambda x: x[2], reverse=True)
                for symbol, balance, usd_value in fungible_lines[:15]:
                    lines.append(f"    {symbol}: {balance:,.4f} (${usd_value:,.2f})")
                if len(fungible_lines) > 15:
                    lines.append(f"    ... +{len(fungible_lines) - 15} more tokens")

                # Count NFTs
                nft_count = sum(
                    1 for a in assets
                    if a.get("interface", "") in ("V1_NFT", "V2_NFT", "ProgrammableNFT")
                )
                if nft_count:
                    lines.append(f"    NFTs: {nft_count} items")

            except Exception as e:
                lines.append(f"    Error: {e}")
            finally:
                client.close()

            all_lines.extend(lines)

        header = [f"SOLANA PORTFOLIO (${grand_total:,.2f} USD total):"]
        return "\n".join(header + all_lines)


# ──────────────────────────────────────────────────────────
# Tool: Solana Transactions
# ──────────────────────────────────────────────────────────

class SolanaTransactionsInput(BaseModel):
    address: str = Field(
        ..., description="Solana wallet address."
    )
    limit: int = Field(
        default=20,
        description="Max transactions to return (max 50).",
    )
    tx_type: Optional[str] = Field(
        None,
        description=(
            "Filter by type: TRANSFER, SWAP, NFT_SALE, NFT_MINT, "
            "STAKE, UNSTAKE, COMPRESSED_NFT_MINT. Leave empty for all."
        ),
    )


class SolanaTransactionsTool(FinancialBaseTool):
    name: str = "solana_transactions"
    description: str = (
        "Get Solana transaction history. Enhanced Transactions API "
        "parses 70+ transaction types (swap, transfer, stake, NFT, etc.). "
        "Human-readable format."
    )
    args_schema: Type[BaseModel] = SolanaTransactionsInput
    service_name: str = "helius"

    def _run(
        self, address: str, limit: int = 20, tx_type: str = None
    ) -> str:
        return self._safe_run(
            self._fetch_transactions, address, limit, tx_type
        )

    def _fetch_transactions(
        self, address: str, limit: int, tx_type: str
    ) -> str:
        limit = min(limit, 50)
        creds = self._get_credentials()

        params = {"api-key": creds["api_key"]}
        url = f"{creds['base_url']}/addresses/{address}/transactions"
        if tx_type:
            params["type"] = tx_type

        client = httpx.Client(timeout=30.0)
        try:
            response = client.get(url, params=params)
            response.raise_for_status()
            txs = response.json()
        finally:
            client.close()

        if not txs:
            return f"No transactions for {address[:8]}..."

        addr_short = f"{address[:4]}...{address[-4:]}"
        lines = [f"SOLANA TRANSACTIONS ({addr_short}):"]

        for tx in txs[:limit]:
            ts = tx.get("timestamp", 0)
            date_str = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "N/A"

            tx_type_str = tx.get("type", "UNKNOWN")
            source = tx.get("source", "")
            fee = tx.get("fee", 0)
            fee_sol = Decimal(fee) / Decimal(10**9) if fee else Decimal("0")

            # Parse token transfers
            token_transfers = tx.get("tokenTransfers", [])
            transfer_parts = []
            for tt in token_transfers[:3]:
                mint = tt.get("mint", "")
                amount = tt.get("tokenAmount", 0)
                from_addr = tt.get("fromUserAccount", "")
                to_addr = tt.get("toUserAccount", "")

                direction = ""
                if to_addr == address:
                    direction = "IN"
                elif from_addr == address:
                    direction = "OUT"

                transfer_parts.append(f"{direction} {amount:.4f}")

            # Parse native transfers
            native_transfers = tx.get("nativeTransfers", [])
            for nt in native_transfers[:2]:
                amount_lamports = nt.get("amount", 0)
                sol_amount = Decimal(amount_lamports) / Decimal(10**9)
                if sol_amount > Decimal("0.001"):
                    from_addr = nt.get("fromUserAccount", "")
                    direction = "IN" if nt.get("toUserAccount") == address else "OUT"
                    transfer_parts.append(f"{direction} {sol_amount:.4f} SOL")

            transfers_str = " | ".join(transfer_parts) if transfer_parts else ""
            source_str = f" via {source}" if source else ""
            desc = tx.get("description", "")
            desc_short = desc[:60] if desc else ""

            line = f"  {date_str} | {tx_type_str}{source_str}"
            if transfers_str:
                line += f" | {transfers_str}"
            if desc_short:
                line += f" | {desc_short}"
            lines.append(line)

        return "\n".join(lines)
