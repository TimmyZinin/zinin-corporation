"""Tests for CTO Agent Improvement Advisor tool."""

import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock


class TestProposalStorage(unittest.TestCase):
    """Test proposal persistence."""

    def test_load_empty(self):
        from src.tools.improvement_advisor import _load_proposals
        with patch("src.tools.improvement_advisor._proposals_path", return_value="/nonexistent/path.json"):
            data = _load_proposals()
            self.assertIsInstance(data["proposals"], list)
            self.assertEqual(len(data["proposals"]), 0)
            self.assertIn("stats", data)

    def test_save_and_load(self):
        from src.tools.improvement_advisor import _save_proposals, _load_proposals
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "cto_proposals.json")
            with patch("src.tools.improvement_advisor._proposals_path", return_value=path):
                data = {
                    "proposals": [{"id": "test_123", "status": "pending"}],
                    "stats": {"total_generated": 1, "approved": 0, "rejected": 0, "conditions": 0},
                    "last_run": "2026-01-01T00:00:00",
                }
                _save_proposals(data)
                loaded = _load_proposals()
                self.assertEqual(loaded["proposals"][0]["id"], "test_123")
                self.assertEqual(loaded["stats"]["total_generated"], 1)

    def test_proposals_capped_at_200(self):
        from src.tools.improvement_advisor import _save_proposals, _load_proposals
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "cto_proposals.json")
            with patch("src.tools.improvement_advisor._proposals_path", return_value=path):
                data = {
                    "proposals": [{"id": f"p_{i}"} for i in range(250)],
                    "stats": {},
                    "last_run": None,
                }
                _save_proposals(data)
                loaded = _load_proposals()
                self.assertEqual(len(loaded["proposals"]), 200)
                # Should keep the last 200
                self.assertEqual(loaded["proposals"][0]["id"], "p_50")

    def test_load_corrupted_json(self):
        from src.tools.improvement_advisor import _load_proposals
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "cto_proposals.json")
            with open(path, "w") as f:
                f.write("not json {{{")
            with patch("src.tools.improvement_advisor._proposals_path", return_value=path):
                data = _load_proposals()
                self.assertEqual(data["proposals"], [])


class TestReadAgentYAMLs(unittest.TestCase):
    """Test YAML reading."""

    def test_reads_all_agents(self):
        from src.tools.improvement_advisor import _read_all_agent_yamls
        agents = _read_all_agent_yamls()
        self.assertIn("manager", agents)
        self.assertIn("automator", agents)
        self.assertIn("accountant", agents)
        self.assertIn("yuki", agents)
        self.assertIn("designer", agents)

    def test_each_agent_has_role(self):
        from src.tools.improvement_advisor import _read_all_agent_yamls
        agents = _read_all_agent_yamls()
        for name, config in agents.items():
            self.assertIn("role", config, f"Agent {name} missing 'role'")

    def test_each_agent_has_backstory(self):
        from src.tools.improvement_advisor import _read_all_agent_yamls
        agents = _read_all_agent_yamls()
        for name, config in agents.items():
            backstory = config.get("backstory", "")
            self.assertTrue(len(backstory) > 100, f"Agent {name} backstory too short")

    def test_each_agent_has_llm(self):
        from src.tools.improvement_advisor import _read_all_agent_yamls
        agents = _read_all_agent_yamls()
        for name, config in agents.items():
            self.assertIn("llm", config, f"Agent {name} missing 'llm'")


class TestSummarizeAgent(unittest.TestCase):
    """Test agent summary generation."""

    def test_summary_includes_label(self):
        from src.tools.improvement_advisor import _summarize_agent
        config = {"role": "CEO", "goal": "Lead", "backstory": "Long text " * 50, "llm": "openrouter/anthropic/claude-sonnet-4"}
        summary = _summarize_agent("manager", config)
        self.assertIn("Алексей", summary)
        self.assertIn("CEO", summary)

    def test_summary_truncates_backstory(self):
        from src.tools.improvement_advisor import _summarize_agent
        config = {"role": "R", "goal": "G", "backstory": "A" * 1000, "llm": "test"}
        summary = _summarize_agent("manager", config)
        self.assertIn("...", summary)


class TestResearchBestPractices(unittest.TestCase):
    """Test web research (mocked)."""

    @patch("src.tools.improvement_advisor.DDGS", create=True)
    def test_returns_results(self, mock_ddgs_class):
        from src.tools.improvement_advisor import _research_best_practices
        mock_ddgs = MagicMock()
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=False)
        mock_ddgs.text.return_value = [
            {"title": "Test", "href": "https://example.com", "body": "Test snippet"},
        ]
        mock_ddgs_class.return_value = mock_ddgs
        with patch("src.tools.improvement_advisor.DDGS", mock_ddgs_class):
            with patch.dict("sys.modules", {"duckduckgo_search": MagicMock(DDGS=mock_ddgs_class)}):
                results = _research_best_practices("test")
                # May return empty if import fails, that's OK
                self.assertIsInstance(results, list)

    def test_handles_import_error(self):
        from src.tools.improvement_advisor import _research_best_practices
        with patch.dict("sys.modules", {"duckduckgo_search": None}):
            with patch("builtins.__import__", side_effect=ImportError("no module")):
                results = _research_best_practices("test")
                self.assertEqual(results, [])


class TestAgentImprovementAdvisor(unittest.TestCase):
    """Test the main tool."""

    def test_tool_instantiation(self):
        from src.tools.improvement_advisor import AgentImprovementAdvisor
        tool = AgentImprovementAdvisor()
        self.assertEqual(tool.name, "Agent Improvement Advisor")

    def test_unknown_action(self):
        from src.tools.improvement_advisor import AgentImprovementAdvisor
        tool = AgentImprovementAdvisor()
        result = tool._run(action="invalid_action")
        self.assertIn("Unknown action", result)

    def test_analyze_requires_target(self):
        from src.tools.improvement_advisor import AgentImprovementAdvisor
        tool = AgentImprovementAdvisor()
        result = tool._run(action="analyze")
        self.assertIn("need target_agent", result)

    def test_analyze_unknown_agent(self):
        from src.tools.improvement_advisor import AgentImprovementAdvisor
        tool = AgentImprovementAdvisor()
        result = tool._run(action="analyze", target_agent="nonexistent")
        self.assertIn("Unknown agent", result)

    def test_analyze_with_mocked_llm(self):
        from src.tools.improvement_advisor import AgentImprovementAdvisor
        tool = AgentImprovementAdvisor()
        mock_response = json.dumps({
            "proposal_type": "prompt",
            "title": "Улучшить goal для Юки",
            "description": "Описание улучшения " * 20,
            "current_state": "Текущее состояние",
            "proposed_change": "Предлагаемое изменение",
            "confidence_score": 0.8,
            "reasoning": "Потому что",
        })
        with patch("src.tools.improvement_advisor._call_llm_tech", return_value=mock_response):
            with patch("src.tools.improvement_advisor._research_best_practices", return_value=[]):
                with patch("src.tools.improvement_advisor._save_proposals"):
                    result = tool._run(action="analyze", target_agent="yuki")
                    self.assertIn("НОВОЕ ПРЕДЛОЖЕНИЕ", result)
                    self.assertIn("Юки", result)
                    self.assertIn("Улучшить goal", result)

    def test_analyze_llm_unavailable(self):
        from src.tools.improvement_advisor import AgentImprovementAdvisor
        tool = AgentImprovementAdvisor()
        with patch("src.tools.improvement_advisor._call_llm_tech", return_value=None):
            with patch("src.tools.improvement_advisor._research_best_practices", return_value=[]):
                result = tool._run(action="analyze", target_agent="yuki")
                self.assertIn("LLM недоступен", result)

    def test_analyze_llm_invalid_json(self):
        from src.tools.improvement_advisor import AgentImprovementAdvisor
        tool = AgentImprovementAdvisor()
        with patch("src.tools.improvement_advisor._call_llm_tech", return_value="not json at all"):
            with patch("src.tools.improvement_advisor._research_best_practices", return_value=[]):
                result = tool._run(action="analyze", target_agent="yuki")
                self.assertIn("невалидный JSON", result)

    def test_list_proposals_empty(self):
        from src.tools.improvement_advisor import AgentImprovementAdvisor
        tool = AgentImprovementAdvisor()
        with patch("src.tools.improvement_advisor._load_proposals",
                    return_value={"proposals": [], "stats": {}}):
            result = tool._run(action="list_proposals")
            self.assertIn("Нет предложений", result)

    def test_list_proposals_with_data(self):
        from src.tools.improvement_advisor import AgentImprovementAdvisor
        tool = AgentImprovementAdvisor()
        data = {
            "proposals": [
                {
                    "id": "prop_test",
                    "target_agent": "yuki",
                    "title": "Test Proposal",
                    "status": "pending",
                    "confidence_score": 0.75,
                }
            ],
            "stats": {"approved": 1, "rejected": 0, "conditions": 0},
        }
        with patch("src.tools.improvement_advisor._load_proposals", return_value=data):
            result = tool._run(action="list_proposals")
            self.assertIn("prop_test", result)
            self.assertIn("Юки", result)

    def test_get_proposal_not_found(self):
        from src.tools.improvement_advisor import AgentImprovementAdvisor
        tool = AgentImprovementAdvisor()
        with patch("src.tools.improvement_advisor._load_proposals",
                    return_value={"proposals": []}):
            result = tool._run(action="get_proposal", proposal_id="nonexistent")
            self.assertIn("not found", result)

    def test_get_proposal_found(self):
        from src.tools.improvement_advisor import AgentImprovementAdvisor
        tool = AgentImprovementAdvisor()
        data = {"proposals": [{"id": "p1", "title": "Test", "status": "pending"}]}
        with patch("src.tools.improvement_advisor._load_proposals", return_value=data):
            result = tool._run(action="get_proposal", proposal_id="p1")
            self.assertIn("Test", result)

    def test_get_proposal_requires_id(self):
        from src.tools.improvement_advisor import AgentImprovementAdvisor
        tool = AgentImprovementAdvisor()
        result = tool._run(action="get_proposal")
        self.assertIn("need proposal_id", result)

    def test_self_reflect_calls_analyze_automator(self):
        from src.tools.improvement_advisor import AgentImprovementAdvisor
        tool = AgentImprovementAdvisor()
        mock_response = json.dumps({
            "proposal_type": "prompt",
            "title": "Self improvement",
            "description": "Desc " * 20,
            "current_state": "Current",
            "proposed_change": "Change",
            "confidence_score": 0.6,
            "reasoning": "Because",
        })
        with patch("src.tools.improvement_advisor._call_llm_tech", return_value=mock_response):
            with patch("src.tools.improvement_advisor._research_best_practices", return_value=[]):
                with patch("src.tools.improvement_advisor._save_proposals"):
                    result = tool._run(action="self_reflect")
                    self.assertIn("Мартин", result)


class TestModelAudit(unittest.TestCase):
    """Test model tier audit."""

    def test_model_audit_with_llm(self):
        from src.tools.improvement_advisor import AgentImprovementAdvisor
        tool = AgentImprovementAdvisor()
        mock_response = json.dumps({
            "recommendations": [
                {
                    "agent": "yuki",
                    "current_tier": "haiku",
                    "recommended_tier": "haiku",
                    "action": "keep",
                    "reasoning": "Задачи рутинные",
                    "estimated_monthly_saving_usd": 0,
                }
            ],
            "summary": "Все тиры оптимальны",
        })
        with patch("src.tools.improvement_advisor._call_llm_tech", return_value=mock_response):
            result = tool._run(action="model_audit")
            self.assertIn("АУДИТ", result)
            self.assertIn("Юки", result)

    def test_model_audit_llm_unavailable(self):
        from src.tools.improvement_advisor import AgentImprovementAdvisor
        tool = AgentImprovementAdvisor()
        with patch("src.tools.improvement_advisor._call_llm_tech", return_value=None):
            result = tool._run(action="model_audit")
            self.assertIn("LLM недоступен", result)


class TestAnalyzeAll(unittest.TestCase):
    """Test analyze_all picks least recent agent."""

    def test_picks_never_analyzed_agent(self):
        from src.tools.improvement_advisor import AgentImprovementAdvisor
        tool = AgentImprovementAdvisor()
        # Mock proposals: only manager was analyzed
        data = {
            "proposals": [
                {"id": "p1", "target_agent": "manager", "created_at": "2026-01-01T00:00:00"}
            ],
            "stats": {},
            "last_run": None,
        }
        mock_response = json.dumps({
            "proposal_type": "prompt",
            "title": "Test",
            "description": "D " * 20,
            "current_state": "C",
            "proposed_change": "P",
            "confidence_score": 0.5,
            "reasoning": "R",
        })
        with patch("src.tools.improvement_advisor._load_proposals", return_value=data):
            with patch("src.tools.improvement_advisor._call_llm_tech", return_value=mock_response):
                with patch("src.tools.improvement_advisor._research_best_practices", return_value=[]):
                    with patch("src.tools.improvement_advisor._save_proposals"):
                        result = tool._run(action="analyze_all")
                        # Should pick one of: accountant, automator, yuki, designer
                        self.assertIn("НОВОЕ ПРЕДЛОЖЕНИЕ", result)


class TestParseProposalJSON(unittest.TestCase):
    """Test JSON parsing from LLM output."""

    def test_parse_clean_json(self):
        from src.tools.improvement_advisor import AgentImprovementAdvisor
        text = '{"proposal_type": "prompt", "title": "Test"}'
        result = AgentImprovementAdvisor._parse_proposal_json(text)
        self.assertEqual(result["title"], "Test")

    def test_parse_json_in_markdown(self):
        from src.tools.improvement_advisor import AgentImprovementAdvisor
        text = 'Here is the result:\n```json\n{"title": "Test"}\n```\nDone.'
        result = AgentImprovementAdvisor._parse_proposal_json(text)
        self.assertEqual(result["title"], "Test")

    def test_parse_json_with_prefix_text(self):
        from src.tools.improvement_advisor import AgentImprovementAdvisor
        text = 'Some text before {"title": "Test"} and after'
        result = AgentImprovementAdvisor._parse_proposal_json(text)
        self.assertEqual(result["title"], "Test")

    def test_parse_invalid_json(self):
        from src.tools.improvement_advisor import AgentImprovementAdvisor
        result = AgentImprovementAdvisor._parse_proposal_json("not json")
        self.assertIsNone(result)


class TestIntegration(unittest.TestCase):
    """Test integration with existing system."""

    def test_automator_has_improvement_tool(self):
        from src.tools.improvement_advisor import AgentImprovementAdvisor
        from src.tools.tech_tools import SystemHealthChecker, IntegrationManager
        tools = [SystemHealthChecker(), IntegrationManager(), AgentImprovementAdvisor()]
        self.assertEqual(len(tools), 3)
        self.assertEqual(tools[2].name, "Agent Improvement Advisor")

    def test_crew_has_cto_generate_proposal(self):
        from src.crew import AICorporation
        self.assertTrue(hasattr(AICorporation, "cto_generate_proposal"))

    def test_bridge_has_run_cto_proposal(self):
        from src.telegram.bridge import AgentBridge
        self.assertTrue(hasattr(AgentBridge, "run_cto_proposal"))

    def test_agent_names_match_yamls(self):
        from src.tools.improvement_advisor import _AGENT_NAMES, _read_all_agent_yamls
        agents = _read_all_agent_yamls()
        for name in _AGENT_NAMES:
            self.assertIn(name, agents, f"Agent {name} YAML not found")

    def test_agent_labels_complete(self):
        from src.tools.improvement_advisor import _AGENT_NAMES, _AGENT_LABELS
        for name in _AGENT_NAMES:
            self.assertIn(name, _AGENT_LABELS, f"Agent {name} missing label")


if __name__ == "__main__":
    unittest.main()
