"""Tests for src/models/corporation_state.py — Shared Corporation State."""

import sys
import os
import json
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.models.corporation_state import (
    SharedCorporationState,
    FinancialSnapshot,
    TechSnapshot,
    ContentSnapshot,
    ProductSnapshot,
    DecisionRecord,
    AlertRecord,
    load_shared_state,
    save_shared_state,
    update_financial,
    update_tech,
    update_content,
    update_product,
    add_decision,
    add_alert,
    resolve_alerts,
    get_active_alerts,
    get_corporation_summary,
)


def _tmp_state_path():
    """Create a temp file for state persistence."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    f.close()
    return f.name


# ── Model Defaults ────────────────────────────────────────

class TestModelDefaults:
    def test_financial_snapshot_defaults(self):
        s = FinancialSnapshot()
        assert s.bank_balance_rub == 0
        assert s.crypto_portfolio_usd == 0
        assert s.total_revenue_rub == 0
        assert s.total_expenses_rub == 0
        assert s.api_costs_usd == 0
        assert s.mrr_rub == 0
        assert s.updated_at == ""

    def test_tech_snapshot_defaults(self):
        s = TechSnapshot()
        assert s.overall_status == "unknown"
        assert s.services_up == 0
        assert s.services_total == 0
        assert s.errors_count == 0

    def test_content_snapshot_defaults(self):
        s = ContentSnapshot()
        assert s.posts_generated == 0
        assert s.linkedin_status == "unknown"

    def test_product_snapshot_defaults(self):
        s = ProductSnapshot()
        assert s.features_total == 0
        assert s.features_done == 0
        assert s.current_sprint == ""

    def test_decision_record(self):
        d = DecisionRecord(decision="Test decision")
        assert d.decision == "Test decision"
        assert d.reason == ""
        assert d.agent == "manager"

    def test_alert_record(self):
        a = AlertRecord(message="Test alert")
        assert a.severity == "info"
        assert a.resolved is False

    def test_shared_state_defaults(self):
        state = SharedCorporationState()
        assert state.version == 1
        assert state.decisions == []
        assert state.alerts == []
        assert state.last_strategic_review == ""
        assert state.last_full_report == ""
        assert state.financial.bank_balance_rub == 0
        assert state.tech.overall_status == "unknown"
        assert state.content.posts_generated == 0
        assert state.product.features_total == 0

    def test_shared_state_created_at(self):
        state = SharedCorporationState()
        assert state.created_at != ""
        assert "T" in state.created_at  # ISO format


# ── Persistence ───────────────────────────────────────────

class TestPersistence:
    def test_save_and_load(self):
        path = _tmp_state_path()
        with patch("src.models.corporation_state._state_path", return_value=path):
            state = SharedCorporationState()
            state.financial.bank_balance_rub = 100000
            state.tech.overall_status = "healthy"
            save_shared_state(state)

            loaded = load_shared_state()
            assert loaded.financial.bank_balance_rub == 100000
            assert loaded.tech.overall_status == "healthy"
            assert loaded.updated_at != ""
        os.unlink(path)

    def test_load_missing_file(self):
        path = "/tmp/nonexistent_state_12345.json"
        with patch("src.models.corporation_state._state_path", return_value=path):
            state = load_shared_state()
            assert isinstance(state, SharedCorporationState)
            assert state.version == 1

    def test_load_corrupted_file(self):
        path = _tmp_state_path()
        with open(path, "w") as f:
            f.write("{broken json!!!")
        with patch("src.models.corporation_state._state_path", return_value=path):
            state = load_shared_state()
            assert isinstance(state, SharedCorporationState)
        os.unlink(path)

    def test_save_creates_directory(self):
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "sub", "state.json")
        with patch("src.models.corporation_state._state_path", return_value=path):
            state = SharedCorporationState()
            save_shared_state(state)
            assert os.path.exists(path)
        os.unlink(path)
        os.rmdir(os.path.join(tmpdir, "sub"))
        os.rmdir(tmpdir)

    def test_roundtrip_preserves_data(self):
        path = _tmp_state_path()
        with patch("src.models.corporation_state._state_path", return_value=path):
            state = SharedCorporationState()
            state.financial = FinancialSnapshot(
                bank_balance_rub=500000,
                crypto_portfolio_usd=12000,
                api_costs_usd=42.5,
                mrr_rub=15000,
            )
            state.tech = TechSnapshot(
                overall_status="healthy",
                services_up=5,
                services_total=5,
            )
            state.content = ContentSnapshot(
                posts_generated=10,
                posts_published=8,
                linkedin_status="connected",
            )
            state.product = ProductSnapshot(
                features_total=20,
                features_done=12,
                features_in_progress=3,
                current_sprint="Sprint 3",
            )
            save_shared_state(state)

            loaded = load_shared_state()
            assert loaded.financial.bank_balance_rub == 500000
            assert loaded.financial.crypto_portfolio_usd == 12000
            assert loaded.tech.services_up == 5
            assert loaded.content.posts_published == 8
            assert loaded.product.current_sprint == "Sprint 3"
        os.unlink(path)


# ── Update Functions ──────────────────────────────────────

class TestUpdateFunctions:
    def test_update_financial(self):
        path = _tmp_state_path()
        with patch("src.models.corporation_state._state_path", return_value=path):
            update_financial(FinancialSnapshot(bank_balance_rub=250000, api_costs_usd=30))
            state = load_shared_state()
            assert state.financial.bank_balance_rub == 250000
            assert state.financial.api_costs_usd == 30
            assert state.financial.updated_at != ""
        os.unlink(path)

    def test_update_tech(self):
        path = _tmp_state_path()
        with patch("src.models.corporation_state._state_path", return_value=path):
            update_tech(TechSnapshot(overall_status="degraded", services_down=1, services_total=5))
            state = load_shared_state()
            assert state.tech.overall_status == "degraded"
            assert state.tech.services_down == 1
            assert state.tech.updated_at != ""
        os.unlink(path)

    def test_update_content(self):
        path = _tmp_state_path()
        with patch("src.models.corporation_state._state_path", return_value=path):
            update_content(ContentSnapshot(posts_generated=5, linkedin_status="connected"))
            state = load_shared_state()
            assert state.content.posts_generated == 5
            assert state.content.linkedin_status == "connected"
            assert state.content.updated_at != ""
        os.unlink(path)

    def test_update_product(self):
        path = _tmp_state_path()
        with patch("src.models.corporation_state._state_path", return_value=path):
            update_product(ProductSnapshot(
                features_total=15, features_done=8,
                current_sprint="Sprint 2", sprint_progress_pct=60,
            ))
            state = load_shared_state()
            assert state.product.features_total == 15
            assert state.product.sprint_progress_pct == 60
            assert state.product.updated_at != ""
        os.unlink(path)

    def test_updates_dont_overwrite_other_departments(self):
        path = _tmp_state_path()
        with patch("src.models.corporation_state._state_path", return_value=path):
            update_financial(FinancialSnapshot(bank_balance_rub=100000))
            update_tech(TechSnapshot(overall_status="healthy"))
            state = load_shared_state()
            assert state.financial.bank_balance_rub == 100000
            assert state.tech.overall_status == "healthy"
        os.unlink(path)


# ── Decisions ─────────────────────────────────────────────

class TestDecisions:
    def test_add_decision(self):
        path = _tmp_state_path()
        with patch("src.models.corporation_state._state_path", return_value=path):
            add_decision("Launch project X", reason="Market timing", agent="manager")
            state = load_shared_state()
            assert len(state.decisions) == 1
            assert state.decisions[0].decision == "Launch project X"
            assert state.decisions[0].reason == "Market timing"
            assert state.decisions[0].agent == "manager"
            assert state.decisions[0].timestamp != ""
        os.unlink(path)

    def test_multiple_decisions(self):
        path = _tmp_state_path()
        with patch("src.models.corporation_state._state_path", return_value=path):
            add_decision("Decision 1")
            add_decision("Decision 2")
            add_decision("Decision 3")
            state = load_shared_state()
            assert len(state.decisions) == 3
        os.unlink(path)

    def test_decisions_capped_at_50(self):
        path = _tmp_state_path()
        with patch("src.models.corporation_state._state_path", return_value=path):
            for i in range(55):
                add_decision(f"Decision {i}")
            state = load_shared_state()
            assert len(state.decisions) == 50
            assert state.decisions[0].decision == "Decision 5"
            assert state.decisions[-1].decision == "Decision 54"
        os.unlink(path)


# ── Alerts ────────────────────────────────────────────────

class TestAlerts:
    def test_add_alert(self):
        path = _tmp_state_path()
        with patch("src.models.corporation_state._state_path", return_value=path):
            add_alert("Server down", severity="critical", source="automator")
            state = load_shared_state()
            assert len(state.alerts) == 1
            assert state.alerts[0].message == "Server down"
            assert state.alerts[0].severity == "critical"
            assert state.alerts[0].source == "automator"
            assert state.alerts[0].resolved is False
        os.unlink(path)

    def test_get_active_alerts(self):
        path = _tmp_state_path()
        with patch("src.models.corporation_state._state_path", return_value=path):
            add_alert("Alert 1", source="test")
            add_alert("Alert 2", source="test")
            active = get_active_alerts()
            assert len(active) == 2
        os.unlink(path)

    def test_resolve_alerts_by_source(self):
        path = _tmp_state_path()
        with patch("src.models.corporation_state._state_path", return_value=path):
            add_alert("Alert A", source="automator")
            add_alert("Alert B", source="accountant")
            resolve_alerts(source="automator")
            active = get_active_alerts()
            assert len(active) == 1
            assert active[0].message == "Alert B"
        os.unlink(path)

    def test_resolve_all_alerts(self):
        path = _tmp_state_path()
        with patch("src.models.corporation_state._state_path", return_value=path):
            add_alert("Alert 1")
            add_alert("Alert 2")
            resolve_alerts()
            active = get_active_alerts()
            assert len(active) == 0
        os.unlink(path)

    def test_alerts_capped_at_100(self):
        path = _tmp_state_path()
        with patch("src.models.corporation_state._state_path", return_value=path):
            for i in range(110):
                add_alert(f"Alert {i}")
            state = load_shared_state()
            assert len(state.alerts) == 100
            assert state.alerts[0].message == "Alert 10"
        os.unlink(path)


# ── Corporation Summary ───────────────────────────────────

class TestCorporationSummary:
    def test_empty_summary(self):
        path = _tmp_state_path()
        with patch("src.models.corporation_state._state_path", return_value=path):
            summary = get_corporation_summary()
            assert "CORPORATION STATE" in summary
            assert "нет данных" in summary

    def test_summary_with_financial_data(self):
        path = _tmp_state_path()
        with patch("src.models.corporation_state._state_path", return_value=path):
            update_financial(FinancialSnapshot(
                bank_balance_rub=500000,
                crypto_portfolio_usd=10000,
                api_costs_usd=50,
            ))
            summary = get_corporation_summary()
            assert "500,000" in summary
            assert "$10,000" in summary
        os.unlink(path)

    def test_summary_with_tech_data(self):
        path = _tmp_state_path()
        with patch("src.models.corporation_state._state_path", return_value=path):
            update_tech(TechSnapshot(
                overall_status="healthy",
                services_up=5,
                services_total=5,
            ))
            summary = get_corporation_summary()
            assert "healthy" in summary
            assert "5/5" in summary
        os.unlink(path)

    def test_summary_with_alerts(self):
        path = _tmp_state_path()
        with patch("src.models.corporation_state._state_path", return_value=path):
            add_alert("API rate limit exceeded", severity="warning")
            summary = get_corporation_summary()
            assert "Алерты" in summary
            assert "API rate limit exceeded" in summary
        os.unlink(path)

    def test_summary_with_decisions(self):
        path = _tmp_state_path()
        with patch("src.models.corporation_state._state_path", return_value=path):
            add_decision("Focus on crypto project")
            summary = get_corporation_summary()
            assert "решения" in summary.lower()
            assert "Focus on crypto project" in summary
        os.unlink(path)

    def test_summary_with_content_data(self):
        path = _tmp_state_path()
        with patch("src.models.corporation_state._state_path", return_value=path):
            update_content(ContentSnapshot(
                posts_generated=10,
                posts_published=7,
                linkedin_status="connected",
                avg_quality_score=4.2,
            ))
            summary = get_corporation_summary()
            assert "10" in summary
            assert "connected" in summary
        os.unlink(path)

    def test_summary_with_product_data(self):
        path = _tmp_state_path()
        with patch("src.models.corporation_state._state_path", return_value=path):
            update_product(ProductSnapshot(
                features_total=20,
                features_done=12,
                features_blocked=2,
                current_sprint="Sprint 3",
                sprint_progress_pct=45,
            ))
            summary = get_corporation_summary()
            assert "12/20" in summary
            assert "Sprint 3" in summary
            assert "45%" in summary
        os.unlink(path)


# ── Flows Integration ─────────────────────────────────────

class TestFlowsIntegration:
    def test_update_shared_state_review(self):
        path = _tmp_state_path()
        with patch("src.models.corporation_state._state_path", return_value=path):
            from src.flows import _update_shared_state_review
            _update_shared_state_review()
            state = load_shared_state()
            assert state.last_strategic_review != ""
            assert "T" in state.last_strategic_review
        os.unlink(path)

    def test_update_shared_state_report(self):
        path = _tmp_state_path()
        with patch("src.models.corporation_state._state_path", return_value=path):
            from src.flows import _update_shared_state_report
            _update_shared_state_report()
            state = load_shared_state()
            assert state.last_full_report != ""
            assert "T" in state.last_full_report
        os.unlink(path)

    def test_both_timestamps_independent(self):
        path = _tmp_state_path()
        with patch("src.models.corporation_state._state_path", return_value=path):
            from src.flows import _update_shared_state_review, _update_shared_state_report
            _update_shared_state_review()
            state = load_shared_state()
            assert state.last_strategic_review != ""
            assert state.last_full_report == ""

            _update_shared_state_report()
            state = load_shared_state()
            assert state.last_strategic_review != ""
            assert state.last_full_report != ""
        os.unlink(path)
