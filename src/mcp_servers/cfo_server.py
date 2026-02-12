"""
CFO MCP Server — wraps Маттиас's financial tools for Agent Teams access.

Each tool delegates to the existing CrewAI BaseTool._run() method.
Credentials are brokered — API keys never leak to the MCP client.

Run: python run_cfo_mcp.py
"""

import logging

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "cfo-mcp",
    instructions="CFO Маттиас — financial tools for Zinin Corporation",
)


@mcp.tool()
def cfo_get_crypto_price(symbol: str = "bitcoin") -> str:
    """Get current cryptocurrency price from CoinGecko.

    Args:
        symbol: CoinGecko coin ID (e.g. bitcoin, ethereum, solana, stacks)
    """
    from ..tools.financial.coingecko import CryptoPriceTool
    tool = CryptoPriceTool()
    return tool._run(coin_id=symbol)


@mcp.tool()
def cfo_get_portfolio() -> str:
    """Get full portfolio summary across all chains and exchanges."""
    from ..tools.financial.portfolio_summary import PortfolioSummaryTool
    tool = PortfolioSummaryTool()
    return tool._run()


@mcp.tool()
def cfo_get_tribute_products() -> str:
    """List all Tribute monetization products (subscriptions, tiers, prices)."""
    from ..tools.financial.tribute import TributeRevenueTool
    tool = TributeRevenueTool()
    return tool._run(action="products")


@mcp.tool()
def cfo_get_tribute_revenue(date_from: str = "", date_to: str = "") -> str:
    """Get revenue summary from Tribute webhook payments.

    Args:
        date_from: Start date YYYY-MM-DD (default: current month)
        date_to: End date YYYY-MM-DD (default: today)
    """
    from ..tools.financial.tribute import TributeRevenueTool
    tool = TributeRevenueTool()
    return tool._run(action="revenue", date_from=date_from or None, date_to=date_to or None)


@mcp.tool()
def cfo_get_tribute_subscriptions() -> str:
    """Get active subscription stats from Tribute."""
    from ..tools.financial.tribute import TributeRevenueTool
    tool = TributeRevenueTool()
    return tool._run(action="subscriptions")


@mcp.tool()
def cfo_get_api_costs() -> str:
    """Get AI API usage costs (OpenRouter, ElevenLabs, OpenAI)."""
    parts = []
    try:
        from ..tools.financial.openrouter_usage import OpenRouterUsageTool
        parts.append(OpenRouterUsageTool()._run())
    except Exception as e:
        parts.append(f"OpenRouter: ⚠️ {e}")
    try:
        from ..tools.financial.elevenlabs_usage import ElevenLabsUsageTool
        parts.append(ElevenLabsUsageTool()._run())
    except Exception as e:
        parts.append(f"ElevenLabs: ⚠️ {e}")
    try:
        from ..tools.financial.openai_usage import OpenAIUsageTool
        parts.append(OpenAIUsageTool()._run())
    except Exception as e:
        parts.append(f"OpenAI: ⚠️ {e}")
    return "\n\n".join(parts)


@mcp.tool()
def cfo_get_forex_rates(base: str = "USD", targets: str = "RUB,EUR,GEL,TRY,THB") -> str:
    """Get current forex exchange rates.

    Args:
        base: Base currency code (default: USD)
        targets: Comma-separated target currencies
    """
    from ..tools.financial.forex import ForexRatesTool
    tool = ForexRatesTool()
    return tool._run(base_currency=base, target_currencies=targets)


@mcp.tool()
def cfo_get_balance() -> str:
    """Get T-Bank (Tinkoff) account balance."""
    from ..tools.financial.tbank import TBankBalanceTool
    tool = TBankBalanceTool()
    return tool._run()
