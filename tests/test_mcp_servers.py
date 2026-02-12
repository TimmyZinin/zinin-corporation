"""Tests for MCP servers (CFO + Tribute) and AgentBridge Task Pool integration."""

import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


# ──────────────────────────────────────────────────────────
# CFO MCP Server tests
# ──────────────────────────────────────────────────────────

class TestCFOMCPServer:
    """Verify CFO MCP server structure and tool registration."""

    def test_cfo_mcp_import(self):
        from src.mcp_servers.cfo_server import mcp
        assert mcp.name == "cfo-mcp"

    def test_cfo_mcp_has_tools(self):
        from src.mcp_servers.cfo_server import mcp
        tools = mcp._tool_manager._tools
        assert len(tools) == 8

    def test_cfo_tool_names(self):
        from src.mcp_servers.cfo_server import mcp
        names = set(mcp._tool_manager._tools.keys())
        expected = {
            "cfo_get_crypto_price",
            "cfo_get_portfolio",
            "cfo_get_tribute_products",
            "cfo_get_tribute_revenue",
            "cfo_get_tribute_subscriptions",
            "cfo_get_api_costs",
            "cfo_get_forex_rates",
            "cfo_get_balance",
        }
        assert names == expected

    def test_cfo_crypto_price_delegates(self):
        """cfo_get_crypto_price should delegate to CryptoPriceTool._run()."""
        from src.mcp_servers.cfo_server import cfo_get_crypto_price
        with patch("src.tools.financial.coingecko.CryptoPriceTool._run", return_value="BTC: $50000") as mock:
            result = cfo_get_crypto_price("bitcoin")
            mock.assert_called_once_with(coin_id="bitcoin")
            assert result == "BTC: $50000"

    def test_cfo_tribute_products_delegates(self):
        from src.mcp_servers.cfo_server import cfo_get_tribute_products
        with patch("src.tools.financial.tribute.TributeRevenueTool._run", return_value="Products list") as mock:
            result = cfo_get_tribute_products()
            mock.assert_called_once_with(action="products")
            assert result == "Products list"

    def test_cfo_tribute_revenue_delegates(self):
        from src.mcp_servers.cfo_server import cfo_get_tribute_revenue
        with patch("src.tools.financial.tribute.TributeRevenueTool._run", return_value="Revenue: $100") as mock:
            result = cfo_get_tribute_revenue("2026-01-01", "2026-01-31")
            mock.assert_called_once_with(action="revenue", date_from="2026-01-01", date_to="2026-01-31")

    def test_cfo_tribute_revenue_empty_dates(self):
        from src.mcp_servers.cfo_server import cfo_get_tribute_revenue
        with patch("src.tools.financial.tribute.TributeRevenueTool._run", return_value="Revenue") as mock:
            cfo_get_tribute_revenue()
            mock.assert_called_once_with(action="revenue", date_from=None, date_to=None)

    def test_cfo_tribute_subscriptions_delegates(self):
        from src.mcp_servers.cfo_server import cfo_get_tribute_subscriptions
        with patch("src.tools.financial.tribute.TributeRevenueTool._run", return_value="Subs: 5") as mock:
            result = cfo_get_tribute_subscriptions()
            mock.assert_called_once_with(action="subscriptions")

    def test_cfo_api_costs_aggregates(self):
        from src.mcp_servers.cfo_server import cfo_get_api_costs
        with patch("src.tools.financial.openrouter_usage.OpenRouterUsageTool._run", return_value="OR: $10"):
            with patch("src.tools.financial.elevenlabs_usage.ElevenLabsUsageTool._run", return_value="EL: $5"):
                with patch("src.tools.financial.openai_usage.OpenAIUsageTool._run", return_value="OAI: $2"):
                    result = cfo_get_api_costs()
                    assert "OR: $10" in result
                    assert "EL: $5" in result
                    assert "OAI: $2" in result

    def test_cfo_api_costs_handles_failures(self):
        from src.mcp_servers.cfo_server import cfo_get_api_costs
        with patch("src.tools.financial.openrouter_usage.OpenRouterUsageTool._run", side_effect=Exception("fail")):
            with patch("src.tools.financial.elevenlabs_usage.ElevenLabsUsageTool._run", return_value="EL: $5"):
                with patch("src.tools.financial.openai_usage.OpenAIUsageTool._run", return_value="OAI: $2"):
                    result = cfo_get_api_costs()
                    assert "⚠️" in result
                    assert "EL: $5" in result

    def test_cfo_forex_delegates(self):
        from src.mcp_servers.cfo_server import cfo_get_forex_rates
        with patch("src.tools.financial.forex.ForexRatesTool._run", return_value="USD/RUB: 90") as mock:
            result = cfo_get_forex_rates("USD", "RUB,EUR")
            mock.assert_called_once_with(base_currency="USD", target_currencies="RUB,EUR")

    def test_cfo_balance_delegates(self):
        from src.mcp_servers.cfo_server import cfo_get_balance
        with patch("src.tools.financial.tbank.TBankBalanceTool._run", return_value="Balance: 100K") as mock:
            result = cfo_get_balance()
            mock.assert_called_once()

    def test_cfo_portfolio_delegates(self):
        from src.mcp_servers.cfo_server import cfo_get_portfolio
        with patch("src.tools.financial.portfolio_summary.PortfolioSummaryTool._run", return_value="Total: $50K") as mock:
            result = cfo_get_portfolio()
            mock.assert_called_once()


# ──────────────────────────────────────────────────────────
# Tribute MCP Server tests
# ──────────────────────────────────────────────────────────

class TestTributeMCPServer:
    """Verify Tribute MCP server structure and tool registration."""

    def test_tribute_mcp_import(self):
        from src.mcp_servers.tribute_server import mcp
        assert mcp.name == "tribute-mcp"

    def test_tribute_mcp_has_tools(self):
        from src.mcp_servers.tribute_server import mcp
        tools = mcp._tool_manager._tools
        assert len(tools) == 4

    def test_tribute_tool_names(self):
        from src.mcp_servers.tribute_server import mcp
        names = set(mcp._tool_manager._tools.keys())
        expected = {
            "tribute_get_products",
            "tribute_get_revenue",
            "tribute_get_subscriptions",
            "tribute_get_stats",
        }
        assert names == expected

    def test_tribute_products_delegates(self):
        from src.mcp_servers.tribute_server import tribute_get_products
        with patch("src.tools.financial.tribute.TributeRevenueTool._run", return_value="Products") as mock:
            result = tribute_get_products()
            mock.assert_called_once_with(action="products")

    def test_tribute_revenue_delegates(self):
        from src.mcp_servers.tribute_server import tribute_get_revenue
        with patch("src.tools.financial.tribute.TributeRevenueTool._run", return_value="Rev") as mock:
            tribute_get_revenue("2026-02-01")
            mock.assert_called_once_with(action="revenue", date_from="2026-02-01", date_to=None)

    def test_tribute_subscriptions_delegates(self):
        from src.mcp_servers.tribute_server import tribute_get_subscriptions
        with patch("src.tools.financial.tribute.TributeRevenueTool._run", return_value="Subs") as mock:
            tribute_get_subscriptions()
            mock.assert_called_once_with(action="subscriptions")

    def test_tribute_stats_aggregates(self):
        from src.mcp_servers.tribute_server import tribute_get_stats
        call_count = 0
        def mock_run(action, **kwargs):
            nonlocal call_count
            call_count += 1
            return f"Result for {action}"
        with patch("src.tools.financial.tribute.TributeRevenueTool._run", side_effect=mock_run):
            result = tribute_get_stats()
            assert call_count == 3
            assert "products" in result
            assert "revenue" in result
            assert "subscriptions" in result

    def test_tribute_stats_handles_error(self):
        from src.mcp_servers.tribute_server import tribute_get_stats
        calls = []
        def mock_run(action, **kwargs):
            calls.append(action)
            if action == "revenue":
                raise Exception("API down")
            return f"OK: {action}"
        with patch("src.tools.financial.tribute.TributeRevenueTool._run", side_effect=mock_run):
            result = tribute_get_stats()
            assert len(calls) == 3
            assert "⚠️" in result
            assert "OK: products" in result


# ──────────────────────────────────────────────────────────
# AgentBridge Task Pool integration tests
# ──────────────────────────────────────────────────────────

class TestBridgeTaskPoolIntegration:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        path = str(tmp_path / "pool.json")
        monkeypatch.setattr("src.task_pool._pool_path", lambda: path)

    def test_track_delegation_creates_task(self):
        from src.telegram.bridge import AgentBridge
        from src.task_pool import get_all_tasks

        task = AgentBridge._track_delegation("Подготовь бюджет", "accountant")
        assert task is not None
        assert task.assignee == "accountant"
        assert task.assigned_by == "ceo-alexey"
        assert task.source == "delegation"

        all_tasks = get_all_tasks()
        assert len(all_tasks) == 1

    def test_track_delegation_truncates_long_message(self):
        from src.telegram.bridge import AgentBridge

        long_msg = "x" * 200
        task = AgentBridge._track_delegation(long_msg, "smm")
        assert len(task.title) <= 103  # 100 + "..."

    def test_complete_delegation(self):
        from src.telegram.bridge import AgentBridge
        from src.task_pool import get_task, TaskStatus

        task = AgentBridge._track_delegation("Test task", "automator")
        AgentBridge._complete_delegation(task, "Done successfully")

        updated = get_task(task.id)
        assert updated.status == TaskStatus.DONE
        assert "Done successfully" in updated.result

    def test_complete_delegation_truncates_result(self):
        from src.telegram.bridge import AgentBridge
        from src.task_pool import get_task

        task = AgentBridge._track_delegation("Test", "smm")
        AgentBridge._complete_delegation(task, "r" * 1000)

        updated = get_task(task.id)
        assert len(updated.result) == 500

    def test_complete_delegation_with_none_task(self):
        from src.telegram.bridge import AgentBridge
        # Should not raise
        AgentBridge._complete_delegation(None, "result")

    def test_track_delegation_error_returns_none(self):
        from src.telegram.bridge import AgentBridge
        with patch("src.task_pool.create_task", side_effect=Exception("DB error")):
            result = AgentBridge._track_delegation("msg", "smm")
            assert result is None


# ──────────────────────────────────────────────────────────
# MCP __init__ module test
# ──────────────────────────────────────────────────────────

class TestMCPInit:
    def test_mcp_package_imports(self):
        import src.mcp_servers
        assert hasattr(src.mcp_servers, "__doc__")

    def test_entry_points_importable(self):
        """Verify run_*.py entry points reference valid modules."""
        from src.mcp_servers.cfo_server import mcp as cfo
        from src.mcp_servers.tribute_server import mcp as tribute
        assert cfo.name == "cfo-mcp"
        assert tribute.name == "tribute-mcp"

    def test_telegram_mcp_importable(self):
        from src.mcp_servers.telegram_server import mcp as tg
        assert tg.name == "telegram-mcp"

    def test_kb_mcp_importable(self):
        from src.mcp_servers.kb_server import mcp as kb
        assert kb.name == "kb-mcp"


# ──────────────────────────────────────────────────────────
# Telegram MCP Server tests
# ──────────────────────────────────────────────────────────

class TestTelegramMCPServer:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        path = str(tmp_path / "pool.json")
        monkeypatch.setattr("src.task_pool._pool_path", lambda: path)

    def test_telegram_mcp_has_tools(self):
        from src.mcp_servers.telegram_server import mcp
        assert len(mcp._tool_manager._tools) == 6

    def test_telegram_tool_names(self):
        from src.mcp_servers.telegram_server import mcp
        names = set(mcp._tool_manager._tools.keys())
        expected = {
            "telegram_create_task",
            "telegram_get_tasks",
            "telegram_get_task",
            "telegram_assign_task",
            "telegram_complete_task",
            "telegram_get_pool_summary",
        }
        assert names == expected

    def test_create_task_via_mcp(self):
        from src.mcp_servers.telegram_server import telegram_create_task
        result = telegram_create_task("Test MCP task")
        assert "Test MCP task" in result

    def test_create_task_with_tags(self):
        from src.mcp_servers.telegram_server import telegram_create_task
        result = telegram_create_task("Finance task", tags="finance,revenue")
        assert "finance" in result.lower() or "Finance" in result

    def test_get_tasks_all(self):
        from src.mcp_servers.telegram_server import telegram_create_task, telegram_get_tasks
        telegram_create_task("Task A")
        telegram_create_task("Task B")
        result = telegram_get_tasks()
        assert "Task A" in result
        assert "Task B" in result

    def test_get_tasks_by_status(self):
        from src.mcp_servers.telegram_server import telegram_create_task, telegram_get_tasks
        telegram_create_task("Todo task")
        result = telegram_get_tasks(status="TODO")
        assert "Todo task" in result

    def test_get_tasks_invalid_status(self):
        from src.mcp_servers.telegram_server import telegram_get_tasks
        result = telegram_get_tasks(status="INVALID")
        assert "Unknown status" in result

    def test_get_task_found(self):
        from src.mcp_servers.telegram_server import telegram_create_task, telegram_get_task
        from src.task_pool import get_all_tasks
        telegram_create_task("Detail task")
        tasks = get_all_tasks()
        result = telegram_get_task(tasks[0].id)
        assert "Detail task" in result

    def test_get_task_not_found(self):
        from src.mcp_servers.telegram_server import telegram_get_task
        result = telegram_get_task("nonexist")
        assert "not found" in result

    def test_assign_task_via_mcp(self):
        from src.mcp_servers.telegram_server import telegram_create_task, telegram_assign_task
        from src.task_pool import get_all_tasks
        telegram_create_task("Assign me")
        tid = get_all_tasks()[0].id
        result = telegram_assign_task(tid, "smm")
        assert "smm" in result

    def test_complete_task_via_mcp(self):
        from src.mcp_servers.telegram_server import telegram_create_task, telegram_assign_task, telegram_complete_task
        from src.task_pool import get_all_tasks
        telegram_create_task("Complete me")
        tid = get_all_tasks()[0].id
        telegram_assign_task(tid, "smm")
        result = telegram_complete_task(tid, "Done!")
        assert "Completed" in result

    def test_pool_summary_via_mcp(self):
        from src.mcp_servers.telegram_server import telegram_create_task, telegram_get_pool_summary
        telegram_create_task("Summary task")
        result = telegram_get_pool_summary()
        assert "Task Pool" in result


# ──────────────────────────────────────────────────────────
# KB MCP Server tests
# ──────────────────────────────────────────────────────────

class TestKBMCPServer:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        kb_dir = str(tmp_path / "knowledge")
        os.makedirs(kb_dir, exist_ok=True)
        # Create test knowledge files
        with open(os.path.join(kb_dir, "company.md"), "w") as f:
            f.write("# Zinin Corporation\n\nAI multi-agent system for revenue.\n")
        with open(os.path.join(kb_dir, "team.md"), "w") as f:
            f.write("# Team\n\nCEO Alexey, CFO Matthias, CTO Martin.\n")
        monkeypatch.setattr("src.mcp_servers.kb_server._kb_dir", lambda: kb_dir)

    def test_kb_mcp_has_tools(self):
        from src.mcp_servers.kb_server import mcp
        assert len(mcp._tool_manager._tools) == 3

    def test_kb_tool_names(self):
        from src.mcp_servers.kb_server import mcp
        names = set(mcp._tool_manager._tools.keys())
        assert names == {"kb_search", "kb_list_topics", "kb_read_topic"}

    def test_kb_search_found(self):
        from src.mcp_servers.kb_server import kb_search
        result = kb_search("Zinin")
        assert "company.md" in result
        assert "Zinin" in result

    def test_kb_search_not_found(self):
        from src.mcp_servers.kb_server import kb_search
        result = kb_search("xyznonexistent")
        assert "No matches" in result

    def test_kb_search_case_insensitive(self):
        from src.mcp_servers.kb_server import kb_search
        result = kb_search("zinin")
        assert "company.md" in result

    def test_kb_list_topics(self):
        from src.mcp_servers.kb_server import kb_list_topics
        result = kb_list_topics()
        assert "company.md" in result
        assert "team.md" in result

    def test_kb_read_topic(self):
        from src.mcp_servers.kb_server import kb_read_topic
        result = kb_read_topic("company.md")
        assert "Zinin Corporation" in result

    def test_kb_read_topic_not_found(self):
        from src.mcp_servers.kb_server import kb_read_topic
        result = kb_read_topic("nonexistent.md")
        assert "not found" in result

    def test_kb_read_topic_path_traversal(self):
        from src.mcp_servers.kb_server import kb_read_topic
        result = kb_read_topic("../../etc/passwd")
        assert "not found" in result
