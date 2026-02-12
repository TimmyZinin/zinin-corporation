"""Entry point for Telegram MCP Server (Task Pool bridge)."""

from src.mcp_servers.telegram_server import mcp

if __name__ == "__main__":
    mcp.run()
