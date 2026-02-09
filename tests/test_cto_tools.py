"""
Tests for CTO (Мартин) enhanced tools: APIHealthMonitor & AgentPromptWriter.
"""

import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock


class TestAPIRegistry(unittest.TestCase):
    """Test the API registry structure."""

    def test_registry_exists(self):
        from src.tools.tech_tools import _API_REGISTRY
        self.assertIsInstance(_API_REGISTRY, dict)
        self.assertGreater(len(_API_REGISTRY), 10)

    def test_all_apis_have_required_fields(self):
        from src.tools.tech_tools import _API_REGISTRY
        required_fields = {"name", "category", "env_vars", "description"}
        for key, info in _API_REGISTRY.items():
            for field in required_fields:
                self.assertIn(field, info, f"API '{key}' missing field '{field}'")

    def test_categories_valid(self):
        from src.tools.tech_tools import _API_REGISTRY
        valid_categories = {"financial", "ai", "platform"}
        for key, info in _API_REGISTRY.items():
            self.assertIn(info["category"], valid_categories,
                          f"API '{key}' has invalid category '{info['category']}'")

    def test_financial_apis_present(self):
        from src.tools.tech_tools import _API_REGISTRY
        financial = [k for k, v in _API_REGISTRY.items() if v["category"] == "financial"]
        expected = ["tbank", "moralis", "helius", "tonapi", "coingecko", "tribute", "forex", "eventum"]
        for api in expected:
            self.assertIn(api, financial, f"Missing financial API: {api}")

    def test_ai_apis_present(self):
        from src.tools.tech_tools import _API_REGISTRY
        ai = [k for k, v in _API_REGISTRY.items() if v["category"] == "ai"]
        expected = ["openrouter", "elevenlabs", "openai", "groq"]
        for api in expected:
            self.assertIn(api, ai, f"Missing AI API: {api}")

    def test_platform_apis_present(self):
        from src.tools.tech_tools import _API_REGISTRY
        platform = [k for k, v in _API_REGISTRY.items() if v["category"] == "platform"]
        self.assertIn("linkedin", platform)
        self.assertIn("railway", platform)

    def test_auth_headers_callable(self):
        from src.tools.tech_tools import _API_REGISTRY
        for key, info in _API_REGISTRY.items():
            if "auth_header" in info:
                self.assertTrue(callable(info["auth_header"]),
                                f"API '{key}' auth_header is not callable")
                headers = info["auth_header"]()
                self.assertIsInstance(headers, dict)


class TestCheckSingleAPI(unittest.TestCase):
    """Test _check_single_api function."""

    def test_unknown_api(self):
        from src.tools.tech_tools import _check_single_api
        result = _check_single_api("nonexistent_api")
        self.assertFalse(result["ok"])
        self.assertIn("Unknown", result.get("error", ""))

    def test_missing_env_vars(self):
        from src.tools.tech_tools import _check_single_api
        with patch.dict(os.environ, {}, clear=True):
            result = _check_single_api("tbank")
            self.assertFalse(result["ok"])
            self.assertFalse(result.get("configured", True))
            self.assertIn("Missing", result.get("error", ""))

    def test_free_api_no_env_vars_needed(self):
        """CoinGecko and Forex don't need env vars."""
        from src.tools.tech_tools import _API_REGISTRY
        for api_key in ["coingecko", "forex", "eventum"]:
            info = _API_REGISTRY[api_key]
            self.assertEqual(info["env_vars"], [],
                             f"{api_key} should not require env vars")


class TestAPIHealthMonitor(unittest.TestCase):
    """Test APIHealthMonitor tool."""

    def test_tool_instantiation(self):
        from src.tools.tech_tools import APIHealthMonitor
        tool = APIHealthMonitor()
        self.assertEqual(tool.name, "API Health Monitor")
        self.assertIn("health monitoring", tool.description)

    def test_args_schema(self):
        from src.tools.tech_tools import APIHealthInput
        # Valid actions
        valid = APIHealthInput(action="full_check")
        self.assertEqual(valid.action, "full_check")

        valid2 = APIHealthInput(action="check_one", api_name="moralis")
        self.assertEqual(valid2.api_name, "moralis")

    def test_unknown_action(self):
        from src.tools.tech_tools import APIHealthMonitor
        tool = APIHealthMonitor()
        result = tool._run(action="invalid_action")
        self.assertIn("Unknown action", result)

    def test_check_one_missing_name(self):
        from src.tools.tech_tools import APIHealthMonitor
        tool = APIHealthMonitor()
        result = tool._run(action="check_one")
        self.assertIn("need api_name", result)

    def test_check_one_unknown_api(self):
        from src.tools.tech_tools import APIHealthMonitor
        tool = APIHealthMonitor()
        result = tool._run(action="check_one", api_name="nonexistent")
        self.assertIn("Unknown API", result)

    def test_report_empty(self):
        """Report with no history returns appropriate message."""
        from src.tools.tech_tools import APIHealthMonitor, _health_data_path
        tool = APIHealthMonitor()
        # Mock empty data
        with patch("src.tools.tech_tools._load_health_data", return_value={"checks": [], "alerts": []}):
            result = tool._run(action="report")
            self.assertIn("No health checks recorded", result)

    def test_history_empty(self):
        from src.tools.tech_tools import APIHealthMonitor
        tool = APIHealthMonitor()
        with patch("src.tools.tech_tools._load_health_data", return_value={"checks": [], "alerts": []}):
            result = tool._run(action="history")
            self.assertIn("No health check history", result)

    def test_full_check_returns_structured_output(self):
        """Full check should return categorized output even if APIs are down."""
        from src.tools.tech_tools import APIHealthMonitor

        # Mock _check_single_api to return fast results without actual HTTP calls
        mock_result = {"ok": True, "configured": True, "ms": 50, "code": 200}
        with patch("src.tools.tech_tools._check_single_api", return_value=mock_result):
            with patch("src.tools.tech_tools._save_health_data"):
                tool = APIHealthMonitor()
                result = tool._run(action="full_check")
                self.assertIn("FULL API HEALTH CHECK", result)
                self.assertIn("Financial APIs", result)
                self.assertIn("AI APIs", result)
                self.assertIn("Platform APIs", result)
                self.assertIn("SUMMARY", result)
                self.assertIn("HEALTHY", result)

    def test_check_financial_only(self):
        mock_result = {"ok": True, "configured": True, "ms": 50, "code": 200}
        with patch("src.tools.tech_tools._check_single_api", return_value=mock_result):
            with patch("src.tools.tech_tools._save_health_data"):
                from src.tools.tech_tools import APIHealthMonitor
                tool = APIHealthMonitor()
                result = tool._run(action="check_financial")
                self.assertIn("FINANCIAL APIs HEALTH CHECK", result)
                # Should NOT have AI section
                self.assertNotIn("AI APIs", result)

    def test_check_ai_only(self):
        mock_result = {"ok": True, "configured": True, "ms": 50, "code": 200}
        with patch("src.tools.tech_tools._check_single_api", return_value=mock_result):
            with patch("src.tools.tech_tools._save_health_data"):
                from src.tools.tech_tools import APIHealthMonitor
                tool = APIHealthMonitor()
                result = tool._run(action="check_ai")
                self.assertIn("AI APIs HEALTH CHECK", result)
                self.assertNotIn("Financial APIs", result)

    def test_degraded_status_on_failures(self):
        """If some APIs fail, status should be degraded."""
        from src.tools.tech_tools import APIHealthMonitor

        call_count = [0]
        def mock_check(api_key):
            call_count[0] += 1
            if call_count[0] <= 2:
                return {"ok": False, "configured": True, "ms": 0, "error": "Timeout"}
            return {"ok": True, "configured": True, "ms": 50}

        with patch("src.tools.tech_tools._check_single_api", side_effect=mock_check):
            with patch("src.tools.tech_tools._save_health_data"):
                tool = APIHealthMonitor()
                result = tool._run(action="full_check")
                self.assertIn("DEGRADED", result)


class TestCheckHeliosHealth(unittest.TestCase):
    """Test Helius RPC health check."""

    def test_missing_api_key(self):
        from src.tools.tech_tools import _check_helius_health
        with patch.dict(os.environ, {}, clear=True):
            result = _check_helius_health()
            self.assertFalse(result["ok"])
            self.assertIn("not set", result.get("error", ""))


class TestRunAPIHealthCheck(unittest.TestCase):
    """Test standalone health check function (for scheduler)."""

    def test_returns_dict(self):
        from src.tools.tech_tools import run_api_health_check
        mock_result = {"ok": True, "configured": True, "ms": 50}
        with patch("src.tools.tech_tools._check_single_api", return_value=mock_result):
            with patch("src.tools.tech_tools._save_health_data"):
                result = run_api_health_check()
                self.assertIsInstance(result, dict)
                self.assertIn("overall", result)
                self.assertIn("total_ok", result)
                self.assertIn("total_fail", result)
                self.assertIn("failed_apis", result)
                self.assertIn("timestamp", result)

    def test_category_filter(self):
        from src.tools.tech_tools import run_api_health_check, _API_REGISTRY
        mock_result = {"ok": True, "configured": True, "ms": 50}
        with patch("src.tools.tech_tools._check_single_api", return_value=mock_result) as mock_fn:
            with patch("src.tools.tech_tools._save_health_data"):
                result = run_api_health_check(categories=["ai"])
                ai_count = sum(1 for v in _API_REGISTRY.values() if v["category"] == "ai")
                self.assertEqual(result["total_ok"], ai_count)

    def test_healthy_status(self):
        from src.tools.tech_tools import run_api_health_check
        mock_result = {"ok": True, "configured": True, "ms": 50}
        with patch("src.tools.tech_tools._check_single_api", return_value=mock_result):
            with patch("src.tools.tech_tools._save_health_data"):
                result = run_api_health_check()
                self.assertEqual(result["overall"], "healthy")
                self.assertEqual(result["total_fail"], 0)

    def test_critical_status(self):
        from src.tools.tech_tools import run_api_health_check
        mock_result = {"ok": False, "configured": True, "ms": 0, "error": "Down"}
        with patch("src.tools.tech_tools._check_single_api", return_value=mock_result):
            with patch("src.tools.tech_tools._save_health_data"):
                result = run_api_health_check()
                self.assertEqual(result["overall"], "critical")
                self.assertGreater(result["total_fail"], 2)


class TestAgentPromptWriter(unittest.TestCase):
    """Test AgentPromptWriter tool."""

    def test_tool_instantiation(self):
        from src.tools.tech_tools import AgentPromptWriter
        tool = AgentPromptWriter()
        self.assertEqual(tool.name, "Agent Prompt Writer")
        self.assertIn("prompt engineer", tool.description)

    def test_list_team(self):
        from src.tools.tech_tools import AgentPromptWriter
        tool = AgentPromptWriter()
        result = tool._run(action="list_team")
        self.assertIn("Алексей", result)
        self.assertIn("Маттиас", result)
        self.assertIn("Мартин", result)
        self.assertIn("Юки", result)
        self.assertIn("Райан", result)

    def test_generate_missing_description(self):
        from src.tools.tech_tools import AgentPromptWriter
        tool = AgentPromptWriter()
        result = tool._run(action="generate")
        self.assertIn("need description", result)

    def test_review_missing_description(self):
        from src.tools.tech_tools import AgentPromptWriter
        tool = AgentPromptWriter()
        result = tool._run(action="review")
        self.assertIn("need description", result)

    def test_improve_missing_description(self):
        from src.tools.tech_tools import AgentPromptWriter
        tool = AgentPromptWriter()
        result = tool._run(action="improve")
        self.assertIn("need description", result)

    def test_unknown_action(self):
        from src.tools.tech_tools import AgentPromptWriter
        tool = AgentPromptWriter()
        result = tool._run(action="invalid")
        self.assertIn("Unknown action", result)

    def test_generate_calls_llm(self):
        from src.tools.tech_tools import AgentPromptWriter
        tool = AgentPromptWriter()
        with patch("src.tools.tech_tools._call_llm_tech", return_value="role: Test Agent"):
            result = tool._run(action="generate", description="HR менеджер")
            self.assertIn("GENERATED AGENT YAML", result)

    def test_generate_llm_unavailable(self):
        from src.tools.tech_tools import AgentPromptWriter
        tool = AgentPromptWriter()
        with patch("src.tools.tech_tools._call_llm_tech", return_value=None):
            result = tool._run(action="generate", description="HR менеджер")
            self.assertIn("LLM недоступен", result)

    def test_review_calls_llm(self):
        from src.tools.tech_tools import AgentPromptWriter
        tool = AgentPromptWriter()
        with patch("src.tools.tech_tools._call_llm_tech", return_value="Оценка: 8/10"):
            result = tool._run(action="review", description="role: test\ngoal: test")
            self.assertIn("REVIEW", result)

    def test_improve_calls_llm(self):
        from src.tools.tech_tools import AgentPromptWriter
        tool = AgentPromptWriter()
        with patch("src.tools.tech_tools._call_llm_tech", return_value="role: Improved Agent"):
            result = tool._run(action="improve", description="role: test")
            self.assertIn("IMPROVED", result)

    def test_model_tier_sonnet(self):
        from src.tools.tech_tools import AgentPromptWriter
        tool = AgentPromptWriter()
        calls = []
        def mock_llm(prompt, system="", max_tokens=3000):
            calls.append(prompt)
            return "role: Test"
        with patch("src.tools.tech_tools._call_llm_tech", side_effect=mock_llm):
            tool._run(action="generate", description="Test agent", model_tier="sonnet")
            self.assertIn("claude-sonnet-4", calls[0])

    def test_model_tier_haiku_default(self):
        from src.tools.tech_tools import AgentPromptWriter
        tool = AgentPromptWriter()
        calls = []
        def mock_llm(prompt, system="", max_tokens=3000):
            calls.append(prompt)
            return "role: Test"
        with patch("src.tools.tech_tools._call_llm_tech", side_effect=mock_llm):
            tool._run(action="generate", description="Test agent")
            self.assertIn("haiku", calls[0])


class TestCallLLMTech(unittest.TestCase):
    """Test the _call_llm_tech helper."""

    def test_no_providers(self):
        from src.tools.tech_tools import _call_llm_tech
        with patch.dict(os.environ, {}, clear=True):
            result = _call_llm_tech("test")
            self.assertIsNone(result)


class TestAgentIntegration(unittest.TestCase):
    """Test that new tools are properly wired into the agent."""

    def test_automator_imports_new_tools(self):
        from src.tools.tech_tools import (
            SystemHealthChecker, IntegrationManager,
            APIHealthMonitor, AgentPromptWriter,
        )
        # All tools instantiate without error
        tools = [
            SystemHealthChecker(),
            IntegrationManager(),
            APIHealthMonitor(),
            AgentPromptWriter(),
        ]
        self.assertEqual(len(tools), 4)

    def test_automator_yaml_has_cto_role(self):
        import yaml
        for path in ["agents/automator.yaml", "/app/agents/automator.yaml"]:
            if os.path.exists(path):
                with open(path) as f:
                    config = yaml.safe_load(f)
                role = config.get("role", "")
                self.assertIn("CTO", role)
                self.assertIn("Мартин", role)
                break
        else:
            self.skipTest("automator.yaml not found")

    def test_crew_has_api_health_report_method(self):
        from src.crew import AICorporation
        corp = AICorporation()
        self.assertTrue(hasattr(corp, "api_health_report"))
        self.assertTrue(callable(corp.api_health_report))

    def test_bridge_has_api_health_method(self):
        from src.telegram.bridge import AgentBridge
        self.assertTrue(hasattr(AgentBridge, "run_api_health_report"))
        self.assertTrue(callable(AgentBridge.run_api_health_report))

    def test_delegation_rules_include_api_health_keywords(self):
        from src.crew import AICorporation
        corp = AICorporation()
        rules = corp._DELEGATION_RULES
        automator_rule = next(r for r in rules if r["agent_key"] == "automator")
        self.assertIn("health check", automator_rule["keywords"])
        self.assertIn("статус api", automator_rule["keywords"])
        self.assertIn("создай агент", automator_rule["keywords"])

    def test_auto_delegation_api_health(self):
        from src.crew import AICorporation
        corp = AICorporation()
        result = corp._detect_delegation_need("Проверь статус api всех сервисов")
        self.assertIsNotNone(result)
        self.assertEqual(result["agent_key"], "automator")

    def test_auto_delegation_create_agent(self):
        from src.crew import AICorporation
        corp = AICorporation()
        result = corp._detect_delegation_need("Создай агент для аналитики данных")
        self.assertIsNotNone(result)
        self.assertEqual(result["agent_key"], "automator")


class TestHealthDataPersistence(unittest.TestCase):
    """Test health data save/load."""

    def test_save_and_load(self):
        from src.tools.tech_tools import _save_health_data, _load_health_data

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "api_health.json")
            with patch("src.tools.tech_tools._health_data_path", return_value=path):
                data = {"checks": [{"test": 1}], "alerts": [], "last_full_check": "2025-01-01"}
                _save_health_data(data)
                loaded = _load_health_data()
                self.assertEqual(loaded["checks"], [{"test": 1}])

    def test_load_nonexistent(self):
        from src.tools.tech_tools import _load_health_data
        with patch("src.tools.tech_tools._health_data_path", return_value="/nonexistent/path.json"):
            data = _load_health_data()
            self.assertEqual(data["checks"], [])
            self.assertIsNone(data["last_full_check"])


class TestAgentWriterSystem(unittest.TestCase):
    """Test the system prompt for agent writer."""

    def test_system_prompt_contains_team(self):
        from src.tools.tech_tools import _AGENT_WRITER_SYSTEM
        self.assertIn("Алексей", _AGENT_WRITER_SYSTEM)
        self.assertIn("Маттиас", _AGENT_WRITER_SYSTEM)
        self.assertIn("Мартин", _AGENT_WRITER_SYSTEM)
        self.assertIn("Юки", _AGENT_WRITER_SYSTEM)
        self.assertIn("Райан", _AGENT_WRITER_SYSTEM)

    def test_system_prompt_contains_rules(self):
        from src.tools.tech_tools import _AGENT_WRITER_SYSTEM
        self.assertIn("АБСОЛЮТНЫЙ ЗАПРЕТ НА ВЫДУМКИ", _AGENT_WRITER_SYSTEM)
        self.assertIn("ТВОЯ КОМАНДА", _AGENT_WRITER_SYSTEM)
        self.assertIn("YAML", _AGENT_WRITER_SYSTEM)


if __name__ == "__main__":
    unittest.main()
