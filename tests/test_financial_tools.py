"""
Tests for financial tools — CFO agent (Маттиас Бруннер).

Tests cover:
1. CredentialBroker — env var handling
2. UnifiedTransaction — model validation
3. Each tool — graceful handling when API keys missing
4. Each tool — response format with mocked API calls
5. Portfolio Summary — aggregation logic
"""

import json
import os
import sys
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ══════════════════════════════════════════════════════════
# 1. CredentialBroker Tests
# ══════════════════════════════════════════════════════════

class TestCredentialBroker:
    def test_unknown_service_raises(self):
        from src.tools.financial.base import CredentialBroker
        with pytest.raises(ValueError, match="Unknown service"):
            CredentialBroker.get("nonexistent")

    def test_missing_env_vars_raises(self):
        from src.tools.financial.base import CredentialBroker
        # Clear any existing env vars
        for key in ("MORALIS_API_KEY",):
            os.environ.pop(key, None)
        with pytest.raises(EnvironmentError, match="Missing env vars"):
            CredentialBroker.get("moralis")

    def test_configured_service(self):
        from src.tools.financial.base import CredentialBroker
        os.environ["MORALIS_API_KEY"] = "test-key-123"
        try:
            creds = CredentialBroker.get("moralis")
            assert creds["api_key"] == "test-key-123"
            assert "moralis.io" in creds["base_url"]
        finally:
            del os.environ["MORALIS_API_KEY"]

    def test_is_configured_false(self):
        from src.tools.financial.base import CredentialBroker
        os.environ.pop("HELIUS_API_KEY", None)
        assert CredentialBroker.is_configured("helius") is False

    def test_is_configured_true(self):
        from src.tools.financial.base import CredentialBroker
        os.environ["HELIUS_API_KEY"] = "test"
        try:
            assert CredentialBroker.is_configured("helius") is True
        finally:
            del os.environ["HELIUS_API_KEY"]

    def test_all_services_in_registry(self):
        from src.tools.financial.base import CredentialBroker
        expected = {
            "tbank", "tbc", "vakifbank", "krungsri",
            "tribute", "stripe", "moralis", "helius",
            "tonapi", "coingecko",
        }
        assert set(CredentialBroker._REGISTRY.keys()) == expected


# ══════════════════════════════════════════════════════════
# 2. UnifiedTransaction Tests
# ══════════════════════════════════════════════════════════

class TestUnifiedTransaction:
    def test_create_basic(self):
        from src.models.financial.transaction import (
            UnifiedTransaction, Source, Category,
        )
        tx = UnifiedTransaction(
            source=Source.TBANK,
            source_id="tx-123",
            amount=Decimal("1500.50"),
            currency="RUB",
            category=Category.INCOME,
            timestamp=datetime(2025, 1, 15, 10, 30),
        )
        assert tx.amount == Decimal("1500.50")
        assert tx.currency == "RUB"
        assert tx.source == Source.TBANK

    def test_float_forbidden(self):
        from src.models.financial.transaction import (
            UnifiedTransaction, Source, Category,
        )
        with pytest.raises(ValueError, match="float is forbidden"):
            UnifiedTransaction(
                source=Source.TBANK,
                source_id="tx-float",
                amount=123.45,  # float!
                currency="RUB",
                category=Category.EXPENSE,
                timestamp=datetime.utcnow(),
            )

    def test_string_amount_ok(self):
        from src.models.financial.transaction import (
            UnifiedTransaction, Source, Category,
        )
        tx = UnifiedTransaction(
            source=Source.MORALIS,
            source_id="0xabc",
            amount="99.99",
            currency="ETH",
            category=Category.TRANSFER,
            timestamp=datetime.utcnow(),
        )
        assert tx.amount == Decimal("99.99")

    def test_currency_uppercased(self):
        from src.models.financial.transaction import (
            UnifiedTransaction, Source, Category,
        )
        tx = UnifiedTransaction(
            source=Source.HELIUS,
            source_id="sol-tx",
            amount=Decimal("1"),
            currency="sol",
            category=Category.STAKING,
            timestamp=datetime.utcnow(),
        )
        assert tx.currency == "SOL"

    def test_to_display(self):
        from src.models.financial.transaction import (
            UnifiedTransaction, Source, Category,
        )
        tx = UnifiedTransaction(
            source=Source.TRIBUTE,
            source_id="pay-1",
            amount=Decimal("25.00"),
            currency="USD",
            amount_usd=Decimal("25.00"),
            category=Category.INCOME,
            description="Subscription payment",
            timestamp=datetime(2025, 6, 1, 12, 0),
        )
        display = tx.to_display()
        assert "25.00" in display
        assert "USD" in display
        assert "income" in display
        assert "Subscription payment" in display


# ══════════════════════════════════════════════════════════
# 3. Tools — Graceful Degradation (no API keys)
# ══════════════════════════════════════════════════════════

class TestToolsWithoutKeys:
    """Each tool should return a warning when API keys are not set."""

    def _clear_env(self):
        keys_to_clear = [
            "TBANK_API_KEY", "TBANK_CLIENT_ID",
            "TRIBUTE_API_KEY", "TRIBUTE_WEBHOOK_SECRET",
            "MORALIS_API_KEY", "HELIUS_API_KEY",
            "TONAPI_KEY", "COINGECKO_API_KEY",
            "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET",
            "TBC_API_KEY", "VAKIFBANK_API_KEY", "KRUNGSRI_API_KEY",
        ]
        for key in keys_to_clear:
            os.environ.pop(key, None)

    def test_tbank_balance_no_key(self):
        self._clear_env()
        from src.tools.financial.tbank import TBankBalanceTool
        result = TBankBalanceTool()._run()
        assert "не настроен" in result or "Нет доступа" in result or "⚠️" in result

    def test_tbank_statement_no_key(self):
        self._clear_env()
        from src.tools.financial.tbank import TBankStatementTool
        result = TBankStatementTool()._run(account_number="12345")
        assert "⚠️" in result

    def test_tribute_revenue_no_key(self):
        self._clear_env()
        from src.tools.financial.tribute import TributeRevenueTool
        result = TributeRevenueTool()._run(action="products")
        assert "⚠️" in result

    def test_evm_portfolio_no_key(self):
        self._clear_env()
        from src.tools.financial.moralis_evm import EVMPortfolioTool
        result = EVMPortfolioTool()._run(address="0x1234567890abcdef")
        assert "⚠️" in result or "not configured" in result.lower() or "не настроен" in result

    def test_solana_portfolio_no_key(self):
        self._clear_env()
        from src.tools.financial.helius_solana import SolanaPortfolioTool
        result = SolanaPortfolioTool()._run(address="SomeAddr")
        assert "⚠️" in result

    def test_ton_portfolio_no_key(self):
        self._clear_env()
        from src.tools.financial.tonapi import TONPortfolioTool
        result = TONPortfolioTool()._run(address="UQAddr")
        assert "⚠️" in result

    def test_crypto_price_no_key(self):
        self._clear_env()
        from src.tools.financial.coingecko import CryptoPriceTool
        result = CryptoPriceTool()._run(coin_ids="bitcoin")
        assert "⚠️" in result

    def test_stripe_not_connected(self):
        from src.tools.financial.stripe_tool import StripeRevenueTool
        result = StripeRevenueTool()._run()
        assert "not connected" in result.lower() or "⚠️" in result

    def test_tbc_not_connected(self):
        from src.tools.financial.tbc_bank import TBCBalanceTool
        result = TBCBalanceTool()._run()
        assert "not connected" in result.lower() or "⚠️" in result

    def test_vakifbank_not_connected(self):
        from src.tools.financial.vakifbank import VakifbankBalanceTool
        result = VakifbankBalanceTool()._run()
        assert "not connected" in result.lower() or "⚠️" in result

    def test_krungsri_not_connected(self):
        from src.tools.financial.krungsri import KrungsriBalanceTool
        result = KrungsriBalanceTool()._run()
        assert "not connected" in result.lower() or "⚠️" in result


# ══════════════════════════════════════════════════════════
# 4. Tools — With Mocked API Responses
# ══════════════════════════════════════════════════════════

class TestCoinGeckoMocked:
    def test_format_prices(self):
        from src.tools.financial.coingecko import CryptoPriceTool
        tool = CryptoPriceTool()
        data = {
            "bitcoin": {"usd": 67500.0, "usd_24h_change": 2.5, "usd_market_cap": 1330000000000},
            "ethereum": {"usd": 3500.0, "usd_24h_change": -1.2, "usd_market_cap": 420000000000},
        }
        result = tool._format_prices(data)
        assert "Bitcoin" in result
        assert "Ethereum" in result
        assert "67,500.00" in result
        assert "+2.5%" in result
        assert "-1.2%" in result

    def test_top_shortcut(self):
        from src.tools.financial.coingecko import CryptoPriceTool
        tool = CryptoPriceTool()
        # Mock the _fetch_prices to check that "top" gets expanded
        os.environ["COINGECKO_API_KEY"] = "test"
        try:
            with patch("httpx.Client") as mock_client:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.json.return_value = {
                    "bitcoin": {"usd": 67000},
                    "ethereum": {"usd": 3400},
                    "solana": {"usd": 145},
                    "the-open-network": {"usd": 6.5},
                }
                mock_resp.raise_for_status = MagicMock()
                mock_client.return_value.__enter__ = lambda s: s
                mock_client.return_value.__exit__ = MagicMock(return_value=False)
                mock_client.return_value.get.return_value = mock_resp

                result = tool._fetch_prices("top", "usd")
                assert "Bitcoin" in result or "bitcoin" in result.lower()
        finally:
            del os.environ["COINGECKO_API_KEY"]


class TestTBankMocked:
    def test_balance_formatted(self):
        from src.tools.financial.tbank import TBankBalanceTool
        os.environ["TBANK_API_KEY"] = "test"
        os.environ["TBANK_CLIENT_ID"] = "test"
        try:
            tool = TBankBalanceTool()
            with patch("httpx.Client") as mock_client:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.json.return_value = [
                    {
                        "accountNumber": "40802810100000012345",
                        "currency": "RUB",
                        "balance": 150000.50,
                        "availableBalance": 145000.00,
                        "status": "active",
                    },
                ]
                mock_resp.raise_for_status = MagicMock()
                mock_client.return_value.__enter__ = lambda s: s
                mock_client.return_value.__exit__ = MagicMock(return_value=False)
                mock_client.return_value.get.return_value = mock_resp

                result = tool._fetch_balance()
                assert "T-BANK BALANCES" in result
                assert "2345" in result  # last 4 digits
                assert "150,000.50" in result
                assert "RUB" in result
        finally:
            del os.environ["TBANK_API_KEY"]
            del os.environ["TBANK_CLIENT_ID"]

    def test_statement_formatted(self):
        from src.tools.financial.tbank import TBankStatementTool
        os.environ["TBANK_API_KEY"] = "test"
        os.environ["TBANK_CLIENT_ID"] = "test"
        try:
            tool = TBankStatementTool()
            with patch("httpx.Client") as mock_client:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.json.return_value = {
                    "operations": [
                        {
                            "amount": 50000,
                            "currency": "RUB",
                            "date": "2025-01-15",
                            "description": "Payment for services",
                            "counterpartyName": "OOO Romashka",
                        },
                        {
                            "amount": -12500,
                            "currency": "RUB",
                            "date": "2025-01-16",
                            "description": "Office rent",
                            "counterpartyName": "IP Petrov",
                        },
                    ]
                }
                mock_resp.raise_for_status = MagicMock()
                mock_client.return_value.__enter__ = lambda s: s
                mock_client.return_value.__exit__ = MagicMock(return_value=False)
                mock_client.return_value.get.return_value = mock_resp

                result = tool._fetch_statement("12345", "2025-01-01", "2025-01-31")
                assert "T-BANK STATEMENT" in result
                assert "50,000.00" in result
                assert "12,500.00" in result
                assert "SUMMARY" in result
        finally:
            del os.environ["TBANK_API_KEY"]
            del os.environ["TBANK_CLIENT_ID"]


class TestTributeMocked:
    def test_products_formatted(self):
        from src.tools.financial.tribute import TributeRevenueTool
        os.environ["TRIBUTE_API_KEY"] = "test"
        os.environ["TRIBUTE_WEBHOOK_SECRET"] = "test"
        try:
            tool = TributeRevenueTool()
            with patch("httpx.Client") as mock_client:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.json.return_value = {
                    "rows": [
                        {
                            "name": "Premium Subscription",
                            "amount": 999,
                            "currency": "usd",
                            "type": "digital",
                            "status": "active",
                            "webLink": "https://web.tribute.tg/p/test",
                        },
                    ],
                    "meta": {"total": 1},
                }
                mock_resp.raise_for_status = MagicMock()
                mock_client.return_value.__enter__ = lambda s: s
                mock_client.return_value.__exit__ = MagicMock(return_value=False)
                mock_client.return_value.get.return_value = mock_resp

                result = tool._fetch_products()
                assert "TRIBUTE PRODUCTS" in result
                assert "Premium Subscription" in result
                assert "9.99" in result
        finally:
            del os.environ["TRIBUTE_API_KEY"]
            del os.environ["TRIBUTE_WEBHOOK_SECRET"]

    def test_revenue_no_data(self):
        from src.tools.financial.tribute import TributeRevenueTool
        os.environ["TRIBUTE_API_KEY"] = "test"
        os.environ["TRIBUTE_WEBHOOK_SECRET"] = "test"
        try:
            tool = TributeRevenueTool()
            # Patch _load_payments to return empty
            with patch("src.tools.financial.tribute._load_payments", return_value=[]):
                result = tool._revenue_summary(None, None)
                assert "webhook" in result.lower() or "нет" in result.lower()
        finally:
            del os.environ["TRIBUTE_API_KEY"]
            del os.environ["TRIBUTE_WEBHOOK_SECRET"]

    def test_revenue_with_data(self):
        from src.tools.financial.tribute import TributeRevenueTool
        os.environ["TRIBUTE_API_KEY"] = "test"
        os.environ["TRIBUTE_WEBHOOK_SECRET"] = "test"
        try:
            tool = TributeRevenueTool()
            payments = [
                {"amount": 9.99, "type": "subscription", "timestamp": "2025-01-15T12:00:00"},
                {"amount": 25.00, "type": "donation", "timestamp": "2025-01-16T14:00:00"},
            ]
            with patch("src.tools.financial.tribute._load_payments", return_value=payments):
                result = tool._revenue_summary(None, None)
                assert "TRIBUTE REVENUE" in result
                assert "34.99" in result
                assert "2 payments" in result
        finally:
            del os.environ["TRIBUTE_API_KEY"]
            del os.environ["TRIBUTE_WEBHOOK_SECRET"]


class TestTributeWebhookVerifier:
    def test_verify_signature(self):
        import hashlib
        import hmac
        from src.tools.financial.tribute import TributeWebhookVerifier

        api_key = "test-secret-key"
        body = b'{"event": "newSubscription", "amount": 9.99}'
        expected_sig = hmac.new(
            api_key.encode(), body, hashlib.sha256
        ).hexdigest()

        assert TributeWebhookVerifier.verify_signature(body, expected_sig, api_key)
        assert not TributeWebhookVerifier.verify_signature(body, "wrong-sig", api_key)


# ══════════════════════════════════════════════════════════
# 5. Agent Integration Test
# ══════════════════════════════════════════════════════════

class TestAgentIntegration:
    def test_accountant_has_financial_tools(self):
        os.environ["OPENROUTER_API_KEY"] = "test-key"
        from src.agents import create_accountant_agent
        agent = create_accountant_agent()
        assert agent is not None
        tool_names = [t.name for t in agent.tools]

        # Real-time financial tools
        assert "tbank_balance" in tool_names
        assert "tbank_statement" in tool_names
        assert "tribute_revenue" in tool_names
        assert "evm_portfolio" in tool_names
        assert "solana_portfolio" in tool_names
        assert "ton_portfolio" in tool_names
        assert "crypto_price" in tool_names
        assert "full_portfolio" in tool_names
        assert "OpenRouter API Usage" in tool_names
        assert "ElevenLabs Usage" in tool_names
        assert "OpenAI API Usage" in tool_names
        assert "stacks_portfolio" in tool_names
        assert "forex_rates" in tool_names
        assert "eventum_portfolio" in tool_names

    def test_accountant_tool_count(self):
        os.environ["OPENROUTER_API_KEY"] = "test-key"
        from src.agents import create_accountant_agent
        agent = create_accountant_agent()
        # 20 real-time financial tools (no legacy)
        assert len(agent.tools) == 20

    def test_accountant_goal_updated(self):
        os.environ["OPENROUTER_API_KEY"] = "test-key"
        from src.agents import create_accountant_agent
        agent = create_accountant_agent()
        assert "T-Bank" in agent.goal or "Tribute" in agent.goal

    def test_accountant_backstory_has_data_access(self):
        os.environ["OPENROUTER_API_KEY"] = "test-key"
        from src.agents import create_accountant_agent
        agent = create_accountant_agent()
        assert "ДОСТУП К ДАННЫМ" in agent.backstory


# ══════════════════════════════════════════════════════════
# 6. Financial Config Tests
# ══════════════════════════════════════════════════════════

class TestFinancialConfig:
    def test_load_config(self):
        from src.tools.financial.base import load_financial_config
        config = load_financial_config()
        assert "banks" in config
        assert "crypto_wallets" in config
        assert "payments" in config

    def test_config_tbank_enabled(self):
        from src.tools.financial.base import load_financial_config
        config = load_financial_config()
        assert config["banks"]["tbank"]["enabled"] is True

    def test_config_stripe_disabled(self):
        from src.tools.financial.base import load_financial_config
        config = load_financial_config()
        assert config["payments"]["stripe"]["enabled"] is False

    def test_config_evm_chains(self):
        from src.tools.financial.base import load_financial_config
        config = load_financial_config()
        chains = config["crypto_wallets"]["evm"]["chains"]
        assert "eth" in chains
        assert "polygon" in chains


# ══════════════════════════════════════════════════════════
# 7. Portfolio Summary Tests
# ══════════════════════════════════════════════════════════

class TestPortfolioSummary:
    def test_no_data_available(self):
        """Portfolio summary with no configured sources returns helpful message."""
        from src.tools.financial.portfolio_summary import PortfolioSummaryTool
        # Patch config to disable everything
        with patch(
            "src.tools.financial.portfolio_summary.load_financial_config",
            return_value={
                "banks": {},
                "crypto_wallets": {},
                "payments": {},
            },
        ):
            tool = PortfolioSummaryTool()
            result = tool._run()
            assert "No financial data" in result or "PORTFOLIO" in result or "configure" in result.lower()

    def test_partial_data(self):
        """Summary shows what's available + warnings for unavailable sources."""
        from src.tools.financial.portfolio_summary import PortfolioSummaryTool
        config = {
            "banks": {"tbank": {"enabled": True}},
            "crypto_wallets": {
                "evm": {"enabled": True, "addresses": []},
                "solana": {"enabled": False},
                "ton": {"enabled": False},
            },
            "payments": {"tribute": {"enabled": True}, "stripe": {"enabled": False}},
        }
        with patch(
            "src.tools.financial.portfolio_summary.load_financial_config",
            return_value=config,
        ):
            tool = PortfolioSummaryTool()
            result = tool._run()
            # Should have warnings about missing data
            assert "⚠️" in result or "WARNING" in result or "PORTFOLIO" in result
