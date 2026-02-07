"""
🧪 Group 3: Dashboard progress tests

Tests that the dashboard shows real progress, queued tasks,
and delegation events instead of "Ожидает задач" for all agents.
"""

import pytest
import sys
import os
import json
import re
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from src.dashboard import generate_dashboard_html


# ──────────────────────────────────────────────────────────
# STATUS_CFG contains queued status
# ──────────────────────────────────────────────────────────

class TestStatusCfg:
    """Tests that STATUS_CFG in dashboard JS has queued status."""

    def test_status_cfg_has_queued(self):
        """STATUS_CFG must include 'queued' status."""
        html = generate_dashboard_html()
        assert "queued" in html, "STATUS_CFG must have 'queued' status"

    def test_queued_has_label(self):
        """Queued status must have a Russian label."""
        html = generate_dashboard_html()
        # Look for queued config with label
        match = re.search(r'queued\s*:\s*\{[^}]*label\s*:\s*"([^"]+)"', html)
        assert match, "queued status must have a label"
        label = match.group(1)
        # Label should be in Russian
        assert any(c in label for c in "абвгдежзиклмнопрстуфхцчшщэюя"), \
            f"Label '{label}' should be in Russian"

    def test_queued_has_color(self):
        """Queued status must have a color."""
        html = generate_dashboard_html()
        match = re.search(r'queued\s*:\s*\{[^}]*color\s*:\s*"([^"]+)"', html)
        assert match, "queued status must have a color"

    def test_queued_has_pulse(self):
        """Queued status must have pulse animation."""
        html = generate_dashboard_html()
        match = re.search(r'queued\s*:\s*\{[^}]*pulse\s*:\s*(true|false)', html)
        assert match, "queued status must have pulse property"


# ──────────────────────────────────────────────────────────
# loadRealData handles queued_tasks
# ──────────────────────────────────────────────────────────

class TestLoadRealDataQueued:
    """Tests that loadRealData() handles queued_tasks from agent statuses."""

    def test_loadrealdata_checks_queued_tasks(self):
        """loadRealData should check for queued_tasks in agent status."""
        html = generate_dashboard_html()
        assert "queued_tasks" in html, \
            "loadRealData must reference queued_tasks from agent status"

    def test_dashboard_with_queued_agent(self):
        """Dashboard renders correctly when an agent has queued_tasks > 0."""
        statuses = {
            "accountant": {
                "status": "idle",
                "task": None,
                "started_at": None,
                "communicating_with": None,
                "queued_tasks": 2,
            }
        }
        html = generate_dashboard_html(agent_statuses=statuses)
        # Should contain the queued data in INITIAL
        assert '"queued_tasks": 2' in html or '"queued_tasks":2' in html, \
            "Dashboard INITIAL data must include queued_tasks"

    def test_dashboard_with_no_queued(self):
        """Dashboard renders correctly when no agents have queued tasks."""
        statuses = {
            "manager": {
                "status": "idle",
                "task": None,
                "started_at": None,
                "communicating_with": None,
                "queued_tasks": 0,
            }
        }
        html = generate_dashboard_html(agent_statuses=statuses)
        assert html  # Should not crash


# ──────────────────────────────────────────────────────────
# Sidebar shows task count
# ──────────────────────────────────────────────────────────

class TestSidebarTaskCount:
    """Tests that sidebar shows task count for agents."""

    def test_sidebar_not_always_ozhidaet(self):
        """Sidebar info should show task info when queued_tasks > 0, not 'Ожидает задач'."""
        html = generate_dashboard_html()
        # The JS code should have logic to show queued task info
        # Check that there's a condition for queued_tasks in updateSidebar or loadRealData
        assert "queued_tasks" in html

    def test_sidebar_shows_queued_count(self):
        """Sidebar should show count of queued tasks (e.g., 'В очереди: 2')."""
        html = generate_dashboard_html()
        # Check for queue-related text in sidebar update logic
        assert re.search(r"очеред|queue", html, re.IGNORECASE), \
            "Sidebar should show queue info for agents with queued tasks"


# ──────────────────────────────────────────────────────────
# generate_dashboard_html passes data correctly
# ──────────────────────────────────────────────────────────

class TestGenerateDashboardHtml:
    """Tests for generate_dashboard_html() data passing."""

    def test_passes_queued_tasks_in_initial(self):
        """generate_dashboard_html passes queued_tasks in INITIAL data."""
        statuses = {
            "accountant": {
                "status": "idle",
                "task": None,
                "started_at": None,
                "communicating_with": None,
                "queued_tasks": 3,
            },
            "manager": {
                "status": "working",
                "task": "Стратегический обзор",
                "started_at": "2026-02-07T19:00:00",
                "communicating_with": None,
                "queued_tasks": 0,
            },
        }
        html = generate_dashboard_html(agent_statuses=statuses)
        # Parse out INITIAL data (const INITIAL = {...};)
        match = re.search(r"(?:var|const|let)\s+INITIAL\s*=\s*({.*?});", html, re.DOTALL)
        assert match, "INITIAL data must be present in dashboard"
        data = json.loads(match.group(1))
        assert data["agentStatuses"]["accountant"]["queued_tasks"] == 3

    def test_passes_delegation_events(self):
        """generate_dashboard_html includes delegation events."""
        events = [
            {
                "type": "delegation",
                "from_agent": "manager",
                "to_agent": "accountant",
                "description": "Подготовить бюджет",
                "timestamp": "2026-02-07T19:00:00",
            }
        ]
        html = generate_dashboard_html(recent_events=events)
        assert "delegation" in html

    def test_html_is_valid(self):
        """Generated HTML is valid (has DOCTYPE, html, head, body)."""
        html = generate_dashboard_html()
        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "<head>" in html
        assert "<body>" in html

    def test_dashboard_handles_delegation_event_in_log(self):
        """Dashboard JS should handle delegation events in the event log."""
        html = generate_dashboard_html()
        # Check that the event log rendering handles "delegation" type
        assert re.search(r'evt\.type\s*===?\s*"delegation"', html), \
            "Dashboard JS must handle delegation events in log rendering"


# ──────────────────────────────────────────────────────────
# Integration: dashboard with real activity tracker data
# ──────────────────────────────────────────────────────────

class TestDashboardIntegration:
    """Integration tests for dashboard with activity tracker data."""

    def test_dashboard_with_delegation_shows_activity(self):
        """Dashboard should show real activity when there are delegations."""
        statuses = {
            "accountant": {
                "status": "idle",
                "task": None,
                "started_at": None,
                "communicating_with": "manager",
                "queued_tasks": 1,
            },
        }
        events = [
            {
                "type": "delegation",
                "from_agent": "manager",
                "to_agent": "accountant",
                "description": "Финансовый отчёт",
                "timestamp": "2026-02-07T19:15:00",
            },
            {
                "type": "communication",
                "from_agent": "manager",
                "to_agent": "accountant",
                "description": "Делегация задачи",
                "timestamp": "2026-02-07T19:15:00",
            },
        ]
        html = generate_dashboard_html(
            completed_count=1,
            agent_statuses=statuses,
            recent_events=events,
        )
        # Should contain the delegation data
        assert "Финансовый отчёт" in html
        assert "queued_tasks" in html
