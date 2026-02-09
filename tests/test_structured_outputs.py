"""
Tests for Structured Outputs (#4) — Pydantic output models for agent responses.
"""

import os
import inspect
import pytest
from pydantic import BaseModel


# ── Output models exist ──────────────────────────────────

class TestOutputModels:
    def test_models_module_exists(self):
        from src.models import outputs
        assert outputs is not None

    def test_financial_report_model(self):
        from src.models.outputs import FinancialReport
        assert issubclass(FinancialReport, BaseModel)
        r = FinancialReport(summary="Test")
        assert r.summary == "Test"
        assert r.total_revenue_rub == 0
        assert r.recommendations == []

    def test_financial_report_fields(self):
        from src.models.outputs import FinancialReport
        fields = FinancialReport.model_fields
        assert "summary" in fields
        assert "total_revenue_rub" in fields
        assert "total_expenses_rub" in fields
        assert "net_profit_rub" in fields
        assert "mrr_rub" in fields
        assert "api_costs_usd" in fields
        assert "crypto_portfolio_usd" in fields
        assert "recommendations" in fields
        assert "data_sources" in fields

    def test_health_check_report_model(self):
        from src.models.outputs import HealthCheckReport
        assert issubclass(HealthCheckReport, BaseModel)
        r = HealthCheckReport(overall_status="healthy")
        assert r.overall_status == "healthy"
        assert r.services_up == 0

    def test_health_check_report_fields(self):
        from src.models.outputs import HealthCheckReport
        fields = HealthCheckReport.model_fields
        assert "overall_status" in fields
        assert "services_up" in fields
        assert "services_down" in fields
        assert "services_total" in fields
        assert "errors" in fields
        assert "recommendations" in fields

    def test_tech_report_model(self):
        from src.models.outputs import TechReport
        assert issubclass(TechReport, BaseModel)
        r = TechReport(overall_status="degraded")
        assert r.api_health == []
        assert r.errors_count == 0

    def test_api_health_detail_model(self):
        from src.models.outputs import APIHealthDetail
        d = APIHealthDetail(name="OpenRouter", status="up", latency_ms=150)
        assert d.name == "OpenRouter"
        assert d.status == "up"
        assert d.latency_ms == 150

    def test_content_report_model(self):
        from src.models.outputs import ContentReport
        r = ContentReport()
        assert r.posts_generated == 0
        assert r.linkedin_status == "unknown"

    def test_strategic_review_report_model(self):
        from src.models.outputs import StrategicReviewReport
        r = StrategicReviewReport(executive_summary="All good")
        assert r.executive_summary == "All good"
        assert r.priorities == []
        assert r.risks == []

    def test_budget_alert_model(self):
        from src.models.outputs import BudgetAlert
        a = BudgetAlert(category="API")
        assert a.category == "API"
        assert a.overspend_percent == 0

    def test_agent_response_model(self):
        from src.models.outputs import AgentResponse
        r = AgentResponse(answer="Test answer")
        assert r.answer == "Test answer"
        assert r.key_facts == []


# ── Model registry ───────────────────────────────────────

class TestModelRegistry:
    def test_report_output_models_dict(self):
        from src.models.outputs import REPORT_OUTPUT_MODELS
        assert "accountant" in REPORT_OUTPUT_MODELS
        assert "automator" in REPORT_OUTPUT_MODELS
        assert "smm" in REPORT_OUTPUT_MODELS
        assert "manager" in REPORT_OUTPUT_MODELS

    def test_get_output_model_report(self):
        from src.models.outputs import get_output_model, FinancialReport
        model = get_output_model("accountant", "report")
        assert model is FinancialReport

    def test_get_output_model_chat(self):
        from src.models.outputs import get_output_model
        model = get_output_model("accountant", "chat")
        assert model is None

    def test_get_output_model_unknown_agent(self):
        from src.models.outputs import get_output_model
        model = get_output_model("unknown_agent", "report")
        assert model is None


# ── Backward compat: crew.py re-exports ──────────────────

class TestCrewReExports:
    def test_crew_exports_financial_report(self):
        from src.crew import FinancialReport
        assert issubclass(FinancialReport, BaseModel)

    def test_crew_exports_health_check_report(self):
        from src.crew import HealthCheckReport
        assert issubclass(HealthCheckReport, BaseModel)

    def test_same_class_as_models(self):
        from src.crew import FinancialReport as FR1
        from src.models.outputs import FinancialReport as FR2
        assert FR1 is FR2


# ── Integration with flows ───────────────────────────────

class TestFlowsIntegration:
    def test_run_agent_crew_accepts_output_pydantic(self):
        from src.flows import _run_agent_crew
        sig = inspect.signature(_run_agent_crew)
        assert "output_pydantic" in sig.parameters

    def test_run_task_accepts_task_type(self):
        from src.flows import run_task
        sig = inspect.signature(run_task)
        assert "task_type" in sig.parameters

    def test_corporation_state_has_task_type(self):
        from src.flows import CorporationState
        state = CorporationState()
        assert hasattr(state, "task_type")
        assert state.task_type == "chat"

    def test_execute_task_accepts_task_type(self):
        from src.crew import AICorporation
        sig = inspect.signature(AICorporation.execute_task)
        assert "task_type" in sig.parameters

    def test_flow_single_agent_uses_output_model(self):
        """run_single_agent should call get_output_model."""
        from src.flows import CorporationFlow
        src = inspect.getsource(CorporationFlow.run_single_agent)
        assert "get_output_model" in src
        assert "output_pydantic" in src


# ── Report methods use task_type="report" ────────────────

class TestReportMethodsUseStructured:
    def _get_method_source(self, method_name):
        from src.crew import AICorporation
        method = getattr(AICorporation, method_name)
        return inspect.getsource(method)

    def test_financial_report_uses_report_type(self):
        src = self._get_method_source("financial_report")
        assert 'task_type="report"' in src

    def test_api_budget_check_uses_report_type(self):
        src = self._get_method_source("api_budget_check")
        assert 'task_type="report"' in src

    def test_system_health_check_uses_report_type(self):
        src = self._get_method_source("system_health_check")
        assert 'task_type="report"' in src

    def test_api_health_report_uses_report_type(self):
        src = self._get_method_source("api_health_report")
        assert 'task_type="report"' in src

    def test_subscription_analysis_uses_report_type(self):
        src = self._get_method_source("subscription_analysis")
        assert 'task_type="report"' in src
