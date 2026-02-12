"""
Tribute MCP Server — revenue and subscription data from Tribute platform.

Focused subset of CFO tools for revenue tracking and subscriber management.

Run: python run_tribute_mcp.py
"""

import logging

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "tribute-mcp",
    instructions="Tribute — Telegram monetization platform (revenue, subscriptions, products)",
)


@mcp.tool()
def tribute_get_products() -> str:
    """List all Tribute products with prices and types."""
    from ..tools.financial.tribute import TributeRevenueTool
    tool = TributeRevenueTool()
    return tool._run(action="products")


@mcp.tool()
def tribute_get_revenue(date_from: str = "", date_to: str = "") -> str:
    """Get revenue summary from stored webhook payments.

    Args:
        date_from: Start date YYYY-MM-DD (default: current month)
        date_to: End date YYYY-MM-DD (default: today)
    """
    from ..tools.financial.tribute import TributeRevenueTool
    tool = TributeRevenueTool()
    return tool._run(action="revenue", date_from=date_from or None, date_to=date_to or None)


@mcp.tool()
def tribute_get_subscriptions() -> str:
    """Get active subscriber statistics."""
    from ..tools.financial.tribute import TributeRevenueTool
    tool = TributeRevenueTool()
    return tool._run(action="subscriptions")


@mcp.tool()
def tribute_get_stats() -> str:
    """Get combined Tribute stats: products + revenue + subscriptions in one call."""
    from ..tools.financial.tribute import TributeRevenueTool
    tool = TributeRevenueTool()
    parts = []
    for action in ("products", "revenue", "subscriptions"):
        try:
            parts.append(tool._run(action=action))
        except Exception as e:
            parts.append(f"{action}: ⚠️ {e}")
    return "\n\n".join(parts)
