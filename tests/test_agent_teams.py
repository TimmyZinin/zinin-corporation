"""Tests for Agent Teams coordination utilities."""

import os
import pytest
from unittest.mock import patch

from src.agent_teams import (
    TEAM_ROLES,
    MCP_SERVERS,
    get_mcp_server_commands,
    get_mcp_servers_for_settings,
    format_teammate_context,
    validate_team_readiness,
)


class TestTeamRoles:
    def test_has_researcher(self):
        assert "researcher" in TEAM_ROLES

    def test_has_implementer(self):
        assert "implementer" in TEAM_ROLES

    def test_has_reviewer(self):
        assert "reviewer" in TEAM_ROLES

    def test_roles_have_descriptions(self):
        for role, desc in TEAM_ROLES.items():
            assert len(desc) > 10, f"{role} description too short"


class TestMCPServers:
    def test_has_4_servers(self):
        assert len(MCP_SERVERS) == 4

    def test_server_names(self):
        expected = {"cfo-mcp", "tribute-mcp", "telegram-mcp", "kb-mcp"}
        assert set(MCP_SERVERS.keys()) == expected

    def test_each_has_command(self):
        for name, cfg in MCP_SERVERS.items():
            assert "command" in cfg
            assert "args" in cfg
            assert cfg["command"] == "python"

    def test_each_has_description(self):
        for name, cfg in MCP_SERVERS.items():
            assert "description" in cfg
            assert len(cfg["description"]) > 10

    def test_tool_counts(self):
        assert MCP_SERVERS["cfo-mcp"]["tools"] == 8
        assert MCP_SERVERS["tribute-mcp"]["tools"] == 4
        assert MCP_SERVERS["telegram-mcp"]["tools"] == 6
        assert MCP_SERVERS["kb-mcp"]["tools"] == 3


class TestGetMCPServerCommands:
    def test_returns_dict(self):
        cmds = get_mcp_server_commands()
        assert isinstance(cmds, dict)

    def test_has_all_servers(self):
        cmds = get_mcp_server_commands()
        assert len(cmds) == 4

    def test_command_format(self):
        cmds = get_mcp_server_commands()
        for name, cmd in cmds.items():
            assert cmd.startswith("python run_")
            assert cmd.endswith("_mcp.py")


class TestGetMCPServersForSettings:
    def test_returns_dict(self):
        settings = get_mcp_servers_for_settings()
        assert isinstance(settings, dict)

    def test_format(self):
        settings = get_mcp_servers_for_settings()
        for name, cfg in settings.items():
            assert "command" in cfg
            assert "args" in cfg
            assert isinstance(cfg["args"], list)


class TestFormatTeammateContext:
    def test_includes_task(self):
        ctx = format_teammate_context("Fix the bug")
        assert "Fix the bug" in ctx

    def test_includes_project(self):
        ctx = format_teammate_context("test")
        assert "Zinin Corporation" in ctx

    def test_includes_mcp_servers(self):
        ctx = format_teammate_context("test")
        assert "cfo-mcp" in ctx
        assert "telegram-mcp" in ctx

    def test_includes_files(self):
        ctx = format_teammate_context("test", files=["src/app.py", "src/crew.py"])
        assert "src/app.py" in ctx
        assert "src/crew.py" in ctx

    def test_no_files(self):
        ctx = format_teammate_context("test")
        assert "Relevant files" not in ctx


class TestValidateTeamReadiness:
    def test_returns_dict(self):
        result = validate_team_readiness()
        assert isinstance(result, dict)

    def test_checks_agent_teams(self):
        result = validate_team_readiness()
        assert "agent_teams_enabled" in result

    def test_checks_claude_md(self):
        result = validate_team_readiness()
        assert "claude_md" in result

    def test_checks_mcp_entry_points(self):
        result = validate_team_readiness()
        for name in MCP_SERVERS:
            assert f"mcp_{name}" in result
