"""
Tests for CPO agent (Софи Андерсен) — task #46

Tests cover:
- Agent YAML config loading
- CPO tools: FeatureHealthChecker, SprintTracker, BacklogAnalyzer, ProgressReporter
- Agent creation factory
- Integration points (delegation detection, output models, activity tracker)
"""

import json
import os
import pytest
import tempfile
from unittest.mock import patch, MagicMock

from src.tools.cpo_tools import (
    FeatureHealthChecker,
    SprintTracker,
    BacklogAnalyzer,
    ProgressReporter,
    _product_dir,
    _load_json,
    _save_json,
)


# ──────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────

@pytest.fixture
def temp_product_dir(tmp_path):
    """Override product dir to use temp directory."""
    product_dir = str(tmp_path / "product")
    os.makedirs(product_dir, exist_ok=True)
    with patch("src.tools.cpo_tools._product_dir", return_value=product_dir):
        yield product_dir


@pytest.fixture
def feature_checker(temp_product_dir):
    return FeatureHealthChecker()


@pytest.fixture
def sprint_tracker(temp_product_dir):
    return SprintTracker()


@pytest.fixture
def backlog_analyzer(temp_product_dir):
    return BacklogAnalyzer()


@pytest.fixture
def progress_reporter(temp_product_dir):
    return ProgressReporter()


@pytest.fixture
def sample_features(temp_product_dir):
    """Pre-populate features for testing."""
    data = {
        "features": {
            "auth_system": {
                "name": "Auth System",
                "description": "User authentication",
                "priority": "critical",
                "status": "done",
                "added": "2026-01-01",
                "updated": "2026-02-01",
            },
            "dashboard": {
                "name": "Dashboard",
                "description": "Main dashboard",
                "priority": "high",
                "status": "in_progress",
                "added": "2026-01-15",
                "updated": "2026-02-08",
            },
            "notifications": {
                "name": "Notifications",
                "description": "Push notifications",
                "priority": "medium",
                "status": "todo",
                "added": "2026-01-20",
                "updated": "2026-01-20",
            },
            "dark_mode": {
                "name": "Dark Mode",
                "description": "Theme switcher",
                "priority": "low",
                "status": "blocked",
                "added": "2026-01-25",
                "updated": "2026-01-25",
            },
        }
    }
    path = os.path.join(temp_product_dir, "features.json")
    with open(path, "w") as f:
        json.dump(data, f)
    return data


@pytest.fixture
def sample_sprint(temp_product_dir):
    """Pre-populate sprint for testing."""
    data = {
        "current_sprint": {
            "name": "Sprint 3",
            "started": "2026-02-01",
            "tasks": {
                "task_a": {"name": "Task A", "done": True, "completed_at": "2026-02-03 10:00"},
                "task_b": {"name": "Task B", "done": False},
                "task_c": {"name": "Task C", "done": True, "completed_at": "2026-02-05 14:00"},
            },
        },
        "sprints": [
            {
                "name": "Sprint 1",
                "started": "2026-01-01",
                "closed": "2026-01-14",
                "tasks": {
                    "s1_t1": {"name": "S1 Task 1", "done": True},
                    "s1_t2": {"name": "S1 Task 2", "done": True},
                    "s1_t3": {"name": "S1 Task 3", "done": False},
                },
            },
            {
                "name": "Sprint 2",
                "started": "2026-01-15",
                "closed": "2026-01-28",
                "tasks": {
                    "s2_t1": {"name": "S2 Task 1", "done": True},
                    "s2_t2": {"name": "S2 Task 2", "done": True},
                },
            },
        ],
    }
    path = os.path.join(temp_product_dir, "sprints.json")
    with open(path, "w") as f:
        json.dump(data, f)
    return data


# ──────────────────────────────────────────────────────────
# YAML Config Tests
# ──────────────────────────────────────────────────────────

class TestCPOConfig:
    def test_cpo_yaml_exists(self):
        assert os.path.exists("agents/cpo.yaml"), "cpo.yaml not found"

    def test_cpo_yaml_loads(self):
        from src.agents import load_agent_config
        config = load_agent_config("cpo")
        assert config, "cpo.yaml is empty or failed to load"

    def test_cpo_yaml_has_required_fields(self):
        from src.agents import load_agent_config
        config = load_agent_config("cpo")
        assert "role" in config
        assert "goal" in config
        assert "backstory" in config
        assert "llm" in config
        assert config["role"] == "CPO Софи Андерсен"

    def test_cpo_yaml_has_anti_fabrication(self):
        from src.agents import load_agent_config
        config = load_agent_config("cpo")
        backstory = config.get("backstory", "")
        assert "АБСОЛЮТНЫЙ ЗАПРЕТ НА ВЫДУМКИ" in backstory

    def test_cpo_yaml_has_team_section(self):
        from src.agents import load_agent_config
        config = load_agent_config("cpo")
        backstory = config.get("backstory", "")
        assert "ТВОЯ КОМАНДА" in backstory

    def test_cpo_yaml_has_no_intro_rule(self):
        from src.agents import load_agent_config
        config = load_agent_config("cpo")
        backstory = config.get("backstory", "")
        assert "НИКОГДА НЕ ПРЕДСТАВЛЯЙСЯ" in backstory

    def test_cpo_yaml_uses_haiku(self):
        from src.agents import load_agent_config
        config = load_agent_config("cpo")
        assert "haiku" in config.get("llm", "")

    def test_cpo_yaml_has_memory_enabled(self):
        from src.agents import load_agent_config
        config = load_agent_config("cpo")
        assert config.get("memory") is True


# ──────────────────────────────────────────────────────────
# Feature Health Checker Tests
# ──────────────────────────────────────────────────────────

class TestFeatureHealthChecker:
    def test_status_empty(self, feature_checker):
        result = feature_checker._run(action="status")
        assert "No features tracked" in result

    def test_status_with_features(self, feature_checker, sample_features):
        result = feature_checker._run(action="status")
        assert "PRODUCT HEALTH" in result
        assert "Done: 1" in result
        assert "In Progress: 1" in result
        assert "Blocked: 1" in result

    def test_features_list(self, feature_checker, sample_features):
        result = feature_checker._run(action="features")
        assert "ALL FEATURES" in result
        assert "Auth System" in result
        assert "Dashboard" in result
        assert "CRITICAL" in result

    def test_add_feature(self, feature_checker):
        result = feature_checker._run(
            action="add_feature",
            name="New Feature",
            description="Something new",
            priority="high",
        )
        assert "Feature added" in result
        assert "New Feature" in result

        # Verify persisted
        result2 = feature_checker._run(action="features")
        assert "New Feature" in result2

    def test_add_feature_no_name(self, feature_checker):
        result = feature_checker._run(action="add_feature")
        assert "Error" in result

    def test_update_feature(self, feature_checker, sample_features):
        result = feature_checker._run(
            action="update_feature",
            name="dashboard",
            new_status="done",
        )
        assert "updated" in result

    def test_update_feature_not_found(self, feature_checker, sample_features):
        result = feature_checker._run(
            action="update_feature",
            name="nonexistent",
            new_status="done",
        )
        assert "not found" in result

    def test_blockers(self, feature_checker, sample_features):
        result = feature_checker._run(action="blockers")
        assert "BLOCKED" in result
        assert "Dark Mode" in result

    def test_blockers_none(self, feature_checker):
        # Add only non-blocked features
        feature_checker._run(action="add_feature", name="OK Feature", priority="high")
        result = feature_checker._run(action="blockers")
        assert "No blocked" in result

    def test_unknown_action(self, feature_checker):
        result = feature_checker._run(action="invalid")
        assert "Unknown action" in result


# ──────────────────────────────────────────────────────────
# Sprint Tracker Tests
# ──────────────────────────────────────────────────────────

class TestSprintTracker:
    def test_current_no_sprint(self, sprint_tracker):
        result = sprint_tracker._run(action="current")
        assert "No active sprint" in result

    def test_current_with_sprint(self, sprint_tracker, sample_sprint):
        result = sprint_tracker._run(action="current")
        assert "Sprint 3" in result
        assert "2/3" in result
        assert "Task A" in result

    def test_create_sprint(self, sprint_tracker):
        result = sprint_tracker._run(
            action="create",
            name="New Sprint",
            tasks='["Task 1", "Task 2", "Task 3"]',
        )
        assert "created" in result
        assert "3 tasks" in result

        # Verify sprint exists
        result2 = sprint_tracker._run(action="current")
        assert "New Sprint" in result2

    def test_create_sprint_csv_tasks(self, sprint_tracker):
        result = sprint_tracker._run(
            action="create",
            name="CSV Sprint",
            tasks="Task A, Task B",
        )
        assert "created" in result
        assert "2 tasks" in result

    def test_complete_task(self, sprint_tracker, sample_sprint):
        result = sprint_tracker._run(action="complete_task", name="task_b")
        assert "marked as done" in result

        # Verify all done
        result2 = sprint_tracker._run(action="current")
        assert "3/3" in result2

    def test_complete_task_not_found(self, sprint_tracker, sample_sprint):
        result = sprint_tracker._run(action="complete_task", name="nonexistent")
        assert "not found" in result

    def test_close_sprint(self, sprint_tracker, sample_sprint):
        result = sprint_tracker._run(action="close")
        assert "closed" in result
        assert "2/3" in result

    def test_close_no_sprint(self, sprint_tracker):
        result = sprint_tracker._run(action="close")
        assert "No active sprint" in result

    def test_history(self, sprint_tracker, sample_sprint):
        result = sprint_tracker._run(action="history")
        assert "SPRINT HISTORY" in result
        assert "Sprint 1" in result
        assert "Sprint 2" in result

    def test_history_empty(self, sprint_tracker):
        result = sprint_tracker._run(action="history")
        assert "No completed sprints" in result


# ──────────────────────────────────────────────────────────
# Backlog Analyzer Tests
# ──────────────────────────────────────────────────────────

class TestBacklogAnalyzer:
    def test_summary_empty(self, backlog_analyzer):
        result = backlog_analyzer._run(action="summary")
        assert "empty" in result.lower()

    def test_summary_with_features(self, backlog_analyzer, sample_features):
        result = backlog_analyzer._run(action="summary")
        assert "BACKLOG SUMMARY" in result
        assert "CRITICAL" in result or "HIGH" in result

    def test_stale_features(self, backlog_analyzer, sample_features):
        result = backlog_analyzer._run(action="stale")
        # Notifications and Dark Mode have old update dates
        assert "STALE" in result or "No stale" in result

    def test_suggest_sprint(self, backlog_analyzer, sample_features):
        result = backlog_analyzer._run(action="suggest_sprint", sprint_size=3)
        assert "SUGGESTED SPRINT" in result

    def test_suggest_sprint_empty(self, backlog_analyzer):
        result = backlog_analyzer._run(action="suggest_sprint")
        assert "No open tasks" in result

    def test_metrics(self, backlog_analyzer, sample_features, sample_sprint):
        result = backlog_analyzer._run(action="metrics")
        assert "PRODUCT METRICS" in result
        assert "Total features: 4" in result
        assert "Done: 1" in result


# ──────────────────────────────────────────────────────────
# Progress Reporter Tests
# ──────────────────────────────────────────────────────────

class TestProgressReporter:
    def test_log_note(self, progress_reporter):
        result = progress_reporter._run(action="log", note="Test note")
        assert "Note logged" in result

    def test_log_no_note(self, progress_reporter):
        result = progress_reporter._run(action="log")
        assert "Error" in result

    def test_notes_empty(self, progress_reporter):
        result = progress_reporter._run(action="notes")
        assert "No progress notes" in result

    def test_notes_after_log(self, progress_reporter):
        progress_reporter._run(action="log", note="First note")
        progress_reporter._run(action="log", note="Second note")
        result = progress_reporter._run(action="notes")
        assert "RECENT NOTES" in result
        assert "First note" in result
        assert "Second note" in result

    def test_daily_report(self, progress_reporter, sample_features, sample_sprint):
        result = progress_reporter._run(action="daily")
        assert "DAILY" in result
        assert "Features:" in result

    def test_weekly_report(self, progress_reporter, sample_features, sample_sprint):
        result = progress_reporter._run(action="weekly")
        assert "WEEKLY" in result
        assert "Features:" in result


# ──────────────────────────────────────────────────────────
# Agent Creation Tests
# ──────────────────────────────────────────────────────────

class TestCPOAgentCreation:
    def test_create_cpo_agent_no_api_key(self):
        """CPO agent creates with empty API key (won't work but shouldn't crash)."""
        from src.agents import create_cpo_agent
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}, clear=False):
            agent = create_cpo_agent()
            # Should create successfully
            assert agent is not None
            assert "Софи" in agent.role

    def test_cpo_agent_has_tools(self):
        """CPO agent should have 4 tools."""
        from src.agents import create_cpo_agent
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}, clear=False):
            agent = create_cpo_agent()
            assert agent is not None
            assert len(agent.tools) == 4

    def test_cpo_agent_tool_names(self):
        """Verify tool names match expected."""
        from src.agents import create_cpo_agent
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}, clear=False):
            agent = create_cpo_agent()
            tool_names = {t.name for t in agent.tools}
            assert "Feature Health Checker" in tool_names
            assert "Sprint Tracker" in tool_names
            assert "Backlog Analyzer" in tool_names
            assert "Progress Reporter" in tool_names


# ──────────────────────────────────────────────────────────
# Integration Tests
# ──────────────────────────────────────────────────────────

class TestCPOIntegration:
    def test_delegation_detection_cpo(self):
        """CPO keywords should trigger delegation to cpo agent."""
        from src.flows import detect_delegation
        assert detect_delegation("покажи бэклог фич") == "cpo"
        assert detect_delegation("статус спринта") == "cpo"
        assert detect_delegation("прогресс разработки") == "cpo"
        assert detect_delegation("product health") == "cpo"

    def test_output_model_registered(self):
        """CPO should have ProductReport in REPORT_OUTPUT_MODELS."""
        from src.models.outputs import REPORT_OUTPUT_MODELS, ProductReport
        assert "cpo" in REPORT_OUTPUT_MODELS
        assert REPORT_OUTPUT_MODELS["cpo"] is ProductReport

    def test_get_output_model_cpo_report(self):
        """get_output_model should return ProductReport for cpo reports."""
        from src.models.outputs import get_output_model, ProductReport
        model = get_output_model("cpo", "report")
        assert model is ProductReport

    def test_get_output_model_cpo_chat(self):
        """get_output_model should return None for cpo chat."""
        from src.models.outputs import get_output_model
        model = get_output_model("cpo", "chat")
        assert model is None

    def test_agent_labels_has_cpo(self):
        """AGENT_LABELS should include CPO."""
        from src.crew import AGENT_LABELS
        assert "cpo" in AGENT_LABELS
        assert "Софи" in AGENT_LABELS["cpo"]

    def test_agent_names_has_cpo(self):
        """AGENT_NAMES should include CPO."""
        from src.activity_tracker import AGENT_NAMES, AGENT_EMOJI
        assert "cpo" in AGENT_NAMES
        assert AGENT_NAMES["cpo"] == "Софи"
        assert "cpo" in AGENT_EMOJI
        assert AGENT_EMOJI["cpo"] == "📋"

    def test_product_report_model(self):
        """ProductReport Pydantic model should validate correctly."""
        from src.models.outputs import ProductReport
        report = ProductReport(
            overall_health="healthy",
            features_total=10,
            features_done=5,
            features_in_progress=3,
            features_blocked=0,
            current_sprint="Sprint 3",
            sprint_progress_pct=67,
            blockers=[],
            priorities=["Finish auth", "Start dashboard"],
            recommendations=["Increase velocity"],
        )
        assert report.overall_health == "healthy"
        assert report.features_total == 10
        assert report.sprint_progress_pct == 67

    def test_corporation_yaml_includes_cpo(self):
        """corporation.yaml should list cpo agent."""
        import yaml
        with open("crews/corporation.yaml", "r") as f:
            config = yaml.safe_load(f)
        assert "cpo" in config.get("agents", [])

    def test_manager_yaml_mentions_cpo(self):
        """Manager YAML should mention Софи in team section."""
        import yaml
        with open("agents/manager.yaml", "r") as f:
            config = yaml.safe_load(f)
        backstory = config.get("backstory", "")
        assert "Софи" in backstory
