"""Tests for the real-time monitoring dashboard."""

import sys
import os
import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── HTML Template Tests ──────────────────────────────────


class TestDashboardHtml:
    """Test the HTML template generation."""

    def test_returns_string(self):
        from src.monitor.dashboard_html import render_dashboard_html

        result = render_dashboard_html()
        assert isinstance(result, str)

    def test_valid_html_structure(self):
        from src.monitor.dashboard_html import render_dashboard_html

        html = render_dashboard_html()
        assert "<!DOCTYPE html>" in html
        assert "</html>" in html
        assert "<head>" in html
        assert "<body>" in html

    def test_all_six_agents_present(self):
        from src.monitor.dashboard_html import render_dashboard_html

        html = render_dashboard_html()
        for name in ["Алексей", "Маттиас", "Мартин", "Юки", "Райан", "Софи"]:
            assert name in html, f"Agent {name} not found in HTML"

    def test_all_agent_roles_present(self):
        from src.monitor.dashboard_html import render_dashboard_html

        html = render_dashboard_html()
        for role in ["CEO", "CFO", "CTO", "SMM", "Design", "CPO"]:
            assert role in html, f"Role {role} not found in HTML"

    def test_sse_connection_code(self):
        from src.monitor.dashboard_html import render_dashboard_html

        html = render_dashboard_html()
        assert "EventSource" in html
        assert "/api/stream" in html

    def test_snapshot_fetch_code(self):
        from src.monitor.dashboard_html import render_dashboard_html

        html = render_dashboard_html()
        assert "/api/snapshot" in html

    def test_has_agent_grid(self):
        from src.monitor.dashboard_html import render_dashboard_html

        html = render_dashboard_html()
        assert "agents-grid" in html

    def test_has_feed_section(self):
        from src.monitor.dashboard_html import render_dashboard_html

        html = render_dashboard_html()
        assert "feed-list" in html
        assert "Live Activity Feed" in html

    def test_has_panel_sections(self):
        from src.monitor.dashboard_html import render_dashboard_html

        html = render_dashboard_html()
        assert "Task Pool" in html
        assert "API Usage" in html
        assert "Quality" in html


# ── Server Tests ─────────────────────────────────────────


MOCK_STATUSES = {
    "manager": {"status": "idle", "task": "", "started_at": ""},
    "smm": {"status": "working", "task": "LinkedIn post", "started_at": "2026-02-13T10:00:00"},
}

MOCK_EVENTS = [
    {
        "type": "task_start",
        "agent": "smm",
        "task": "LinkedIn post",
        "timestamp": "2026-02-13T10:00:00",
    }
]


def _apply_all_mocks():
    """Return a dict of patches for all data source functions."""
    return {
        "src.monitor.server.get_all_statuses": MagicMock(return_value=MOCK_STATUSES),
        "src.monitor.server.get_recent_events": MagicMock(return_value=MOCK_EVENTS),
        "src.monitor.server.get_quality_summary": MagicMock(
            return_value={"count": 5, "avg": 0.85, "passed_pct": 80}
        ),
        "src.monitor.server.get_all_usage": MagicMock(
            return_value={"openrouter": {"count": 42, "avg_latency_ms": 120}}
        ),
        "src.monitor.server.get_rate_alerts": MagicMock(return_value=[]),
        "src.monitor.server.get_pool_summary": MagicMock(
            return_value={"total": 10, "TODO": 3, "DONE": 5, "IN_PROGRESS": 2}
        ),
        "src.monitor.server.get_all_tasks": MagicMock(return_value=[]),
        "src.monitor.server.get_task_progress": MagicMock(return_value=None),
        "src.monitor.server.AGENT_NAMES": {
            "manager": "Алексей",
            "smm": "Юки",
        },
        "src.monitor.server.AGENT_EMOJI": {
            "manager": "👑",
            "smm": "📱",
        },
    }


class TestBuildSnapshot:
    """Test the snapshot aggregation function."""

    def test_snapshot_has_all_keys(self):
        with patch.multiple("src.monitor.server", **{
            k.split(".")[-1]: v for k, v in _apply_all_mocks().items()
        }):
            from src.monitor.server import _build_snapshot

            snapshot = _build_snapshot()
            assert "timestamp" in snapshot
            assert "agents" in snapshot
            assert "events" in snapshot
            assert "quality" in snapshot
            assert "api_usage" in snapshot
            assert "task_pool" in snapshot
            assert "active_tasks" in snapshot
            assert "alerts" in snapshot

    def test_snapshot_agents_enriched(self):
        with patch.multiple("src.monitor.server", **{
            k.split(".")[-1]: v for k, v in _apply_all_mocks().items()
        }):
            from src.monitor.server import _build_snapshot

            snapshot = _build_snapshot()
            agents = snapshot["agents"]
            assert "manager" in agents
            assert "progress" in agents["manager"]

    def test_snapshot_handles_exceptions_gracefully(self):
        mocks = {k.split(".")[-1]: v for k, v in _apply_all_mocks().items()}
        mocks["get_all_usage"] = MagicMock(side_effect=Exception("API error"))
        mocks["get_pool_summary"] = MagicMock(side_effect=Exception("Pool error"))

        with patch.multiple("src.monitor.server", **mocks):
            from src.monitor.server import _build_snapshot

            snapshot = _build_snapshot()
            assert snapshot["api_usage"] == {}
            assert snapshot["task_pool"] == {}


class TestHashSnapshot:
    """Test the snapshot hash function."""

    def test_same_data_same_hash(self):
        from src.monitor.server import _hash_snapshot

        data = {"agents": {"a": 1}, "events": []}
        assert _hash_snapshot(data) == _hash_snapshot(data)

    def test_different_data_different_hash(self):
        from src.monitor.server import _hash_snapshot

        d1 = {"agents": {"a": 1}}
        d2 = {"agents": {"a": 2}}
        assert _hash_snapshot(d1) != _hash_snapshot(d2)

    def test_handles_datetime(self):
        from src.monitor.server import _hash_snapshot

        data = {"ts": datetime(2026, 1, 1)}
        result = _hash_snapshot(data)
        assert isinstance(result, str)
        assert len(result) == 32  # MD5 hex length


class TestCreateApp:
    """Test the Starlette app factory."""

    def test_creates_starlette_app(self):
        from src.monitor.server import create_app
        from starlette.applications import Starlette

        app = create_app()
        assert isinstance(app, Starlette)

    def test_has_required_routes(self):
        from src.monitor.server import create_app

        app = create_app()
        paths = [r.path for r in app.routes]
        assert "/" in paths
        assert "/api/snapshot" in paths
        assert "/api/agents" in paths
        assert "/api/events" in paths
        assert "/api/stream" in paths

    def test_has_five_routes(self):
        from src.monitor.server import create_app

        app = create_app()
        assert len(app.routes) == 5


class TestEndpoints:
    """Test HTTP endpoints with Starlette test client."""

    @pytest.fixture
    def client(self):
        from starlette.testclient import TestClient
        from src.monitor.server import create_app

        return TestClient(create_app())

    def test_index_returns_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Zinin Corp" in resp.text.upper() or "ZININ CORP" in resp.text

    def test_snapshot_returns_json(self, client):
        with patch.multiple("src.monitor.server", **{
            k.split(".")[-1]: v for k, v in _apply_all_mocks().items()
        }):
            resp = client.get("/api/snapshot")
            assert resp.status_code == 200
            data = resp.json()
            assert "agents" in data
            assert "events" in data

    def test_agents_returns_json(self, client):
        with patch.multiple("src.monitor.server", **{
            k.split(".")[-1]: v for k, v in _apply_all_mocks().items()
        }):
            resp = client.get("/api/agents")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, dict)

    def test_events_returns_json(self, client):
        with patch.multiple("src.monitor.server", **{
            k.split(".")[-1]: v for k, v in _apply_all_mocks().items()
        }):
            resp = client.get("/api/events")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)

    def test_events_query_params(self, client):
        with patch.multiple("src.monitor.server", **{
            k.split(".")[-1]: v for k, v in _apply_all_mocks().items()
        }):
            resp = client.get("/api/events?hours=1&limit=10")
            assert resp.status_code == 200
