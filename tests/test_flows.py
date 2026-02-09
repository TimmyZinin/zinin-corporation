"""
Tests for CorporationFlow (#1) — CrewAI Flows migration.
"""

import os
import ast
import inspect
import pytest


FLOWS_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "flows.py")
CREW_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "crew.py")


def _read_source(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ── Module structure ────────────────────────────────────────

class TestFlowsModuleStructure:
    def test_flows_module_exists(self):
        assert os.path.isfile(FLOWS_PATH), "src/flows.py must exist"

    def test_imports_flow_decorators(self):
        source = _read_source(FLOWS_PATH)
        assert "from crewai.flow.flow import Flow, start, listen, router" in source

    def test_corporation_state_defined(self):
        from src.flows import CorporationState
        assert CorporationState is not None

    def test_corporation_flow_defined(self):
        from src.flows import CorporationFlow
        assert CorporationFlow is not None

    def test_agent_pool_defined(self):
        from src.flows import _AgentPool
        assert _AgentPool is not None

    def test_public_api_functions_exist(self):
        from src.flows import run_task, run_strategic_review, run_full_report
        assert callable(run_task)
        assert callable(run_strategic_review)
        assert callable(run_full_report)

    def test_detect_delegation_exists(self):
        from src.flows import detect_delegation
        assert callable(detect_delegation)


# ── CorporationState ──────────────────────────────────────

class TestCorporationState:
    def test_state_has_required_fields(self):
        from src.flows import CorporationState
        state = CorporationState()
        assert hasattr(state, "task_description")
        assert hasattr(state, "agent_name")
        assert hasattr(state, "use_memory")
        assert hasattr(state, "flow_type")
        assert hasattr(state, "delegation_target")
        assert hasattr(state, "final_output")

    def test_state_defaults(self):
        from src.flows import CorporationState
        state = CorporationState()
        assert state.task_description == ""
        assert state.agent_name == "manager"
        assert state.use_memory is True
        assert state.flow_type == ""
        assert state.final_output == ""

    def test_state_is_pydantic(self):
        from pydantic import BaseModel
        from src.flows import CorporationState
        assert issubclass(CorporationState, BaseModel)

    def test_agent_result_model(self):
        from src.flows import AgentResult
        r = AgentResult(agent_name="test", success=True, output="hello")
        assert r.agent_name == "test"
        assert r.success is True
        assert r.output == "hello"

    def test_state_nested_agent_results(self):
        from src.flows import CorporationState, AgentResult
        state = CorporationState()
        assert isinstance(state.specialist_result, AgentResult)
        assert isinstance(state.accountant_result, AgentResult)
        assert isinstance(state.manager_result, AgentResult)


# ── CorporationFlow ──────────────────────────────────────

class TestCorporationFlowClass:
    def test_inherits_flow(self):
        from crewai.flow.flow import Flow
        from src.flows import CorporationFlow
        assert issubclass(CorporationFlow, Flow)

    def test_has_classify_task_method(self):
        from src.flows import CorporationFlow
        assert hasattr(CorporationFlow, "classify_task")

    def test_has_route_method(self):
        from src.flows import CorporationFlow
        assert hasattr(CorporationFlow, "route")

    def test_has_run_single_agent(self):
        from src.flows import CorporationFlow
        assert hasattr(CorporationFlow, "run_single_agent")

    def test_has_run_specialist(self):
        from src.flows import CorporationFlow
        assert hasattr(CorporationFlow, "run_specialist")

    def test_has_run_strategic_review(self):
        from src.flows import CorporationFlow
        assert hasattr(CorporationFlow, "run_strategic_review")

    def test_has_run_full_report(self):
        from src.flows import CorporationFlow
        assert hasattr(CorporationFlow, "run_full_report")

    def test_has_handle_error(self):
        from src.flows import CorporationFlow
        assert hasattr(CorporationFlow, "handle_error")

    def test_flow_methods_are_decorated(self):
        """Verify flow methods have proper CrewAI decorators."""
        source = _read_source(FLOWS_PATH)
        # Check key decorator patterns
        assert "@start()" in source
        assert "@router(classify_task)" in source
        assert '@listen("single")' in source
        assert '@listen("delegated")' in source
        assert '@listen("strategic_review")' in source
        assert '@listen("full_report")' in source
        assert '@listen("error")' in source


# ── Delegation detection ──────────────────────────────────

class TestDelegationDetection:
    def test_detect_finance_keywords(self):
        from src.flows import detect_delegation
        assert detect_delegation("Покажи бюджет") == "accountant"
        assert detect_delegation("Какой доход за месяц?") == "accountant"

    def test_detect_tech_keywords(self):
        from src.flows import detect_delegation
        assert detect_delegation("Проверь api статус") == "automator"
        assert detect_delegation("Деплой на Railway") == "automator"

    def test_detect_smm_keywords(self):
        from src.flows import detect_delegation
        assert detect_delegation("Напиши пост для LinkedIn") == "smm"
        assert detect_delegation("Контент-план на неделю") == "smm"

    def test_detect_designer_keywords(self):
        from src.flows import detect_delegation
        assert detect_delegation("Создай баннер") == "designer"
        assert detect_delegation("Нужна инфографика") == "designer"

    def test_designer_priority_over_smm(self):
        """Design keywords should override SMM for mixed prompts."""
        from src.flows import detect_delegation
        result = detect_delegation("Создай изображение для поста в LinkedIn")
        assert result == "designer"

    def test_no_delegation_for_strategy(self):
        from src.flows import detect_delegation
        result = detect_delegation("Какая стратегия на квартал?")
        assert result is None


# ── Agent Pool ────────────────────────────────────────────

class TestAgentPool:
    def test_pool_starts_not_ready(self):
        from src.flows import _AgentPool
        pool = _AgentPool()
        assert pool.is_ready is False

    def test_pool_get_returns_none_when_not_initialized(self):
        from src.flows import _AgentPool
        pool = _AgentPool()
        assert pool.get("manager") is None

    def test_pool_all_agents_empty_when_not_initialized(self):
        from src.flows import _AgentPool
        pool = _AgentPool()
        assert pool.all_agents() == []


# ── _run_agent_crew helper ────────────────────────────────

class TestRunAgentCrew:
    def test_function_exists(self):
        from src.flows import _run_agent_crew
        assert callable(_run_agent_crew)

    def test_signature_matches_original(self):
        from src.flows import _run_agent_crew
        sig = inspect.signature(_run_agent_crew)
        params = list(sig.parameters.keys())
        assert "agent" in params
        assert "task_description" in params
        assert "agent_name" in params
        assert "use_memory" in params
        assert "guardrail" in params


# ── Crew.py integration ──────────────────────────────────

class TestCrewIntegration:
    def test_execute_task_delegates_to_flow(self):
        source = _read_source(CREW_PATH)
        assert "from .flows import run_task" in source

    def test_strategic_review_delegates_to_flow(self):
        source = _read_source(CREW_PATH)
        assert "from .flows import run_strategic_review" in source

    def test_full_report_delegates_to_flow(self):
        source = _read_source(CREW_PATH)
        assert "from .flows import run_full_report" in source

    def test_initialize_uses_agent_pool(self):
        source = _read_source(CREW_PATH)
        assert "from .flows import get_agent_pool" in source

    def test_run_agent_still_exists(self):
        """_run_agent is kept for backward compat (cto_generate_proposal)."""
        from src.crew import AICorporation
        assert hasattr(AICorporation, "_run_agent")

    def test_cto_generate_proposal_still_uses_run_agent(self):
        source = _read_source(CREW_PATH)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "cto_generate_proposal":
                func_source = "\n".join(
                    source.splitlines()[node.lineno - 1: node.end_lineno]
                )
                assert "self._run_agent" in func_source
                return
        pytest.fail("cto_generate_proposal not found")

    def test_convenience_methods_still_call_execute_task(self):
        """financial_report, api_budget_check etc should still call self.execute_task."""
        source = _read_source(CREW_PATH)
        for method in ["financial_report", "api_budget_check", "system_health_check"]:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == method:
                    func_source = "\n".join(
                        source.splitlines()[node.lineno - 1: node.end_lineno]
                    )
                    assert "self.execute_task" in func_source, (
                        f"{method} should delegate to self.execute_task"
                    )

    def test_delegation_rules_moved_to_flows(self):
        """Delegation rules should NOT be in crew.py anymore."""
        source = _read_source(CREW_PATH)
        assert "_DELEGATION_RULES" not in source
        assert "_detect_delegation_need" not in source

    def test_delegation_rules_exist_in_flows(self):
        flows_source = _read_source(FLOWS_PATH)
        assert "_DELEGATION_RULES" in flows_source
        assert "detect_delegation" in flows_source


# ── Flow state types ─────────────────────────────────────

class TestFlowTypes:
    def test_single_flow_type(self):
        source = _read_source(FLOWS_PATH)
        assert '"single"' in source

    def test_delegated_flow_type(self):
        source = _read_source(FLOWS_PATH)
        assert '"delegated"' in source

    def test_strategic_review_flow_type(self):
        source = _read_source(FLOWS_PATH)
        assert '"strategic_review"' in source

    def test_full_report_flow_type(self):
        source = _read_source(FLOWS_PATH)
        assert '"full_report"' in source

    def test_error_flow_type(self):
        source = _read_source(FLOWS_PATH)
        assert '"error"' in source
