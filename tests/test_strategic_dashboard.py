"""Tests for src/pages/strategic_dashboard.py — CEO Strategic Dashboard."""

import sys
import os
import types
from unittest.mock import MagicMock

# Mock streamlit before importing strategic_dashboard
_mock_st = MagicMock()
_mock_st.columns = MagicMock(return_value=[MagicMock() for _ in range(6)])
sys.modules["streamlit"] = _mock_st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.pages.strategic_dashboard import (
    _AGENT_INFO,
    _render_corporation_state,
    render_strategic_dashboard,
)


# ── Agent Info Registry ───────────────────────────────────

class TestAgentInfo:
    def test_six_agents(self):
        assert len(_AGENT_INFO) == 6

    def test_expected_agents(self):
        expected = {"manager", "accountant", "smm", "automator", "designer", "cpo"}
        assert set(_AGENT_INFO.keys()) == expected

    def test_each_has_required_fields(self):
        for key, info in _AGENT_INFO.items():
            assert "name" in info, f"{key} missing name"
            assert "emoji" in info, f"{key} missing emoji"
            assert "color" in info, f"{key} missing color"
            assert "title" in info, f"{key} missing title"

    def test_cpo_info(self):
        cpo = _AGENT_INFO["cpo"]
        assert cpo["name"] == "Софи"
        assert cpo["emoji"] == "📋"
        assert cpo["title"] == "CPO"

    def test_manager_info(self):
        mgr = _AGENT_INFO["manager"]
        assert mgr["name"] == "Алексей"
        assert mgr["emoji"] == "👑"
        assert mgr["title"] == "CEO"

    def test_colors_are_hex(self):
        for key, info in _AGENT_INFO.items():
            assert info["color"].startswith("#"), f"{key} color not hex"
            assert len(info["color"]) == 7, f"{key} color not 7 chars"

    def test_all_names_russian(self):
        for key, info in _AGENT_INFO.items():
            if key == "cpo":
                continue  # Софи — Danish name but written in Russian
            name = info["name"]
            assert any(ord(c) > 127 for c in name), f"{key} name '{name}' not Russian"

    def test_all_unique_colors(self):
        colors = [info["color"] for info in _AGENT_INFO.values()]
        assert len(colors) == len(set(colors)), "Duplicate colors found"

    def test_all_unique_emojis(self):
        emojis = [info["emoji"] for info in _AGENT_INFO.values()]
        assert len(emojis) == len(set(emojis)), "Duplicate emojis found"


# ── Functions Exist ───────────────────────────────────────

class TestFunctionsExist:
    def test_render_corporation_state_callable(self):
        assert callable(_render_corporation_state)

    def test_render_strategic_dashboard_callable(self):
        assert callable(render_strategic_dashboard)

    def test_module_has_all_sections(self):
        import src.pages.strategic_dashboard as mod
        assert hasattr(mod, "render_strategic_dashboard")
        assert hasattr(mod, "_render_kpi_row")
        assert hasattr(mod, "_render_quality_section")
        assert hasattr(mod, "_render_quality_chart")
        assert hasattr(mod, "_render_scores_table")
        assert hasattr(mod, "_render_agent_status")
        assert hasattr(mod, "_render_quick_actions")
        assert hasattr(mod, "_render_corporation_state")


# ── Corporation State Imports ─────────────────────────────

class TestCorporationStateImports:
    def test_shared_state_importable(self):
        from src.models.corporation_state import SharedCorporationState
        state = SharedCorporationState()
        assert state.version == 1

    def test_load_shared_state_importable(self):
        from src.models.corporation_state import load_shared_state
        assert callable(load_shared_state)

    def test_get_active_alerts_importable(self):
        from src.models.corporation_state import get_active_alerts
        assert callable(get_active_alerts)

    def test_get_corporation_summary_importable(self):
        from src.models.corporation_state import get_corporation_summary
        assert callable(get_corporation_summary)
