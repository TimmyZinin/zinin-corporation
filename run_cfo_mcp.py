"""Entry point for CFO MCP Server (Маттиас financial tools)."""

from src.mcp_servers.cfo_server import mcp

if __name__ == "__main__":
    mcp.run()
