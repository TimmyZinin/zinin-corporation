"""Agent Teams coordination utilities.

Provides helper functions for Claude Code Agent Teams:
- MCP server configuration
- Teammate context formatting
- Team readiness validation
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Available team roles for Agent Teams
TEAM_ROLES = {
    "researcher": "Research and gather information from codebase and external sources",
    "implementer": "Write code, create tests, modify existing files",
    "reviewer": "Review and validate changes, run tests, check quality",
}

# MCP servers available for teammates
MCP_SERVERS = {
    "cfo-mcp": {
        "command": "python",
        "args": ["run_cfo_mcp.py"],
        "description": "Financial data: balance, portfolio, crypto, tribute, forex, API costs",
        "tools": 8,
    },
    "tribute-mcp": {
        "command": "python",
        "args": ["run_tribute_mcp.py"],
        "description": "Revenue/subscriber data: products, revenue, subscriptions, stats",
        "tools": 4,
    },
    "telegram-mcp": {
        "command": "python",
        "args": ["run_telegram_mcp.py"],
        "description": "Task Pool bridge: create/get/assign/complete tasks, pool summary",
        "tools": 6,
    },
    "kb-mcp": {
        "command": "python",
        "args": ["run_kb_mcp.py"],
        "description": "Knowledge base: search, list topics, read topic",
        "tools": 3,
    },
}


def get_mcp_server_commands() -> dict[str, str]:
    """Get launch commands for all MCP servers.

    Returns dict: server_name → 'python run_xxx_mcp.py'
    """
    return {
        name: f"{cfg['command']} {' '.join(cfg['args'])}"
        for name, cfg in MCP_SERVERS.items()
    }


def get_mcp_servers_for_settings() -> dict:
    """Get MCP server config formatted for .claude/settings.json.

    Returns dict ready to be used as 'mcpServers' value.
    """
    return {
        name: {"command": cfg["command"], "args": cfg["args"]}
        for name, cfg in MCP_SERVERS.items()
    }


def format_teammate_context(task: str, files: list[str] = None) -> str:
    """Format context string for a teammate agent.

    Args:
        task: Task description for the teammate
        files: Optional list of relevant file paths

    Returns:
        Formatted context string
    """
    lines = [
        f"Task: {task}",
        "",
        "Project: Zinin Corporation (AI Multi-Agent System)",
        "Location: /Users/timofeyzinin/ai_corporation",
        "Key docs: CLAUDE.md, AGENTS.md, STATE.md",
        "",
    ]

    if files:
        lines.append("Relevant files:")
        for f in files:
            lines.append(f"  - {f}")
        lines.append("")

    lines.extend([
        "Available MCP servers:",
    ])
    for name, cfg in MCP_SERVERS.items():
        lines.append(f"  - {name} ({cfg['tools']} tools): {cfg['description']}")

    return "\n".join(lines)


def validate_team_readiness() -> dict:
    """Check if Agent Teams prerequisites are met.

    Returns dict with status for each requirement.
    """
    results = {}

    # Check Agent Teams env var
    results["agent_teams_enabled"] = (
        os.getenv("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS") == "1"
    )

    # Check MCP entry points exist
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for name, cfg in MCP_SERVERS.items():
        entry_point = os.path.join(base, cfg["args"][0])
        results[f"mcp_{name}"] = os.path.exists(entry_point)

    # Check CLAUDE.md exists
    claude_md = os.path.join(base, "CLAUDE.md")
    results["claude_md"] = os.path.exists(claude_md)

    # Check key env vars
    results["openrouter_key"] = bool(os.getenv("OPENROUTER_API_KEY"))

    return results
