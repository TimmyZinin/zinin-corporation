"""
Portfolio Summary — Aggregates ALL financial sources into one report.

Calls each source tool internally and combines results.
If a source is unavailable, shows remaining sources + warning.
Used for morning reports and full financial overview.
"""

import logging
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from .base import CredentialBroker, load_financial_config

logger = logging.getLogger(__name__)


class PortfolioSummaryInput(BaseModel):
    include_transactions: bool = Field(
        default=False,
        description=(
            "If True, include recent transactions summary. "
            "If False (default), only show balances and totals."
        ),
    )


class PortfolioSummaryTool(BaseTool):
    name: str = "full_portfolio"
    description: str = (
        "Full summary of ALL financial assets:\n"
        "- Banks: T-Bank, TBC, Vakıfbank, Krungsri — balances in local currencies + USD\n"
        "- Crypto: EVM + Solana + TON wallets — full portfolios in USD\n"
        "- Revenue: Tribute + Stripe — income for period\n"
        "- Total: aggregate value of all assets in USD\n"
        "Use for morning reports and financial monitoring."
    )
    args_schema: Type[BaseModel] = PortfolioSummaryInput

    def _run(self, include_transactions: bool = False) -> str:
        sections = []
        warnings = []
        config = load_financial_config()

        # ── BANKS ──
        bank_section = self._collect_banks(config, warnings)
        if bank_section:
            sections.append(bank_section)

        # ── CRYPTO ──
        crypto_section = self._collect_crypto(config, warnings)
        if crypto_section:
            sections.append(crypto_section)

        # ── REVENUE ──
        revenue_section = self._collect_revenue(config, warnings)
        if revenue_section:
            sections.append(revenue_section)

        # ── WARNINGS ──
        if warnings:
            sections.append(
                "WARNINGS:\n" + "\n".join(f"  ⚠️ {w}" for w in warnings)
            )

        if not sections:
            return (
                "No financial data available. "
                "Configure sources in config/financial_sources.yaml "
                "and set API keys in environment variables."
            )

        header = "═══ FULL PORTFOLIO SUMMARY ═══"
        return f"{header}\n\n" + "\n\n".join(sections)

    def _collect_banks(self, config: dict, warnings: list) -> str:
        """Collect bank balances."""
        banks_config = config.get("banks", {})
        results = []

        # T-Bank
        if banks_config.get("tbank", {}).get("enabled"):
            try:
                from .tbank import TBankBalanceTool
                tool = TBankBalanceTool()
                result = tool._run()
                results.append(result)
            except Exception as e:
                warnings.append(f"T-Bank: {e}")

        # TBC Bank
        if banks_config.get("tbc", {}).get("enabled"):
            try:
                from .tbc_bank import TBCBalanceTool
                tool = TBCBalanceTool()
                result = tool._run()
                results.append(result)
            except Exception as e:
                warnings.append(f"TBC Bank: {e}")

        # Vakifbank
        if banks_config.get("vakifbank", {}).get("enabled"):
            try:
                from .vakifbank import VakifbankBalanceTool
                tool = VakifbankBalanceTool()
                result = tool._run()
                results.append(result)
            except Exception as e:
                warnings.append(f"Vakıfbank: {e}")

        # Krungsri
        if banks_config.get("krungsri", {}).get("enabled"):
            try:
                from .krungsri import KrungsriBalanceTool
                tool = KrungsriBalanceTool()
                result = tool._run()
                results.append(result)
            except Exception as e:
                warnings.append(f"Krungsri: {e}")

        if results:
            return "BANKS:\n" + "\n".join(results)
        return ""

    def _collect_crypto(self, config: dict, warnings: list) -> str:
        """Collect crypto portfolio data."""
        crypto_config = config.get("crypto_wallets", {})
        results = []

        # EVM
        if crypto_config.get("evm", {}).get("enabled"):
            if crypto_config.get("evm", {}).get("addresses"):
                try:
                    from .moralis_evm import EVMPortfolioTool
                    tool = EVMPortfolioTool()
                    result = tool._run()
                    results.append(result)
                except Exception as e:
                    warnings.append(f"EVM (Moralis): {e}")
            else:
                warnings.append("EVM enabled but no addresses configured")

        # Solana
        if crypto_config.get("solana", {}).get("enabled"):
            if crypto_config.get("solana", {}).get("addresses"):
                try:
                    from .helius_solana import SolanaPortfolioTool
                    tool = SolanaPortfolioTool()
                    result = tool._run()
                    results.append(result)
                except Exception as e:
                    warnings.append(f"Solana (Helius): {e}")
            else:
                warnings.append("Solana enabled but no addresses configured")

        # TON
        if crypto_config.get("ton", {}).get("enabled"):
            if crypto_config.get("ton", {}).get("addresses"):
                try:
                    from .tonapi import TONPortfolioTool
                    tool = TONPortfolioTool()
                    result = tool._run()
                    results.append(result)
                except Exception as e:
                    warnings.append(f"TON (TonAPI): {e}")
            else:
                warnings.append("TON enabled but no addresses configured")

        if results:
            return "CRYPTO:\n" + "\n".join(results)
        return ""

    def _collect_revenue(self, config: dict, warnings: list) -> str:
        """Collect revenue data."""
        payments_config = config.get("payments", {})
        results = []

        # Tribute
        if payments_config.get("tribute", {}).get("enabled"):
            try:
                from .tribute import TributeRevenueTool
                tool = TributeRevenueTool()
                result = tool._run(action="revenue")
                results.append(result)
            except Exception as e:
                warnings.append(f"Tribute: {e}")

        # Stripe
        if payments_config.get("stripe", {}).get("enabled"):
            try:
                from .stripe_tool import StripeRevenueTool
                tool = StripeRevenueTool()
                result = tool._run()
                results.append(result)
            except Exception as e:
                warnings.append(f"Stripe: {e}")

        if results:
            return "REVENUE:\n" + "\n".join(results)
        return ""
