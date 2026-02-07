"""Tests for src/dashboard.py — Agent Dashboard HTML generation."""

import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.dashboard import generate_dashboard_html


# ── HTML Generation ──────────────────────────────────────

class TestHtmlGeneration:
    def test_returns_string(self):
        html = generate_dashboard_html()
        assert isinstance(html, str)

    def test_not_empty(self):
        html = generate_dashboard_html()
        assert len(html) > 1000

    def test_valid_html_structure(self):
        html = generate_dashboard_html()
        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "</html>" in html
        assert "<head>" in html
        assert "<body>" in html
        assert "</body>" in html

    def test_has_css(self):
        html = generate_dashboard_html()
        assert "<style>" in html
        assert "</style>" in html

    def test_has_javascript(self):
        html = generate_dashboard_html()
        assert "<script>" in html
        assert "</script>" in html


# ── Agent Cards ──────────────────────────────────────────

class TestAgentContent:
    def test_all_agents_present(self):
        html = generate_dashboard_html()
        agents = ["Алексей", "Маттиас", "Юки", "Мартин"]
        for name in agents:
            assert name in html, f"Agent {name} not found in HTML"

    def test_agent_roles(self):
        html = generate_dashboard_html()
        roles = ["CEO", "CFO", "SMM", "CTO"]
        for role in roles:
            assert role in html, f"Role {role} not found"

    def test_agent_icons(self):
        html = generate_dashboard_html()
        icons = ["👑", "🏦", "📱", "⚙️"]
        for icon in icons:
            assert icon in html, f"Icon {icon} not found"

    def test_agent_flags(self):
        html = generate_dashboard_html()
        flags = ["🇷🇺", "🇨🇭", "🇰🇷", "🇦🇷"]
        for flag in flags:
            assert flag in html, f"Flag {flag} not found"

    def test_agent_ids(self):
        html = generate_dashboard_html()
        ids = ["manager", "accountant", "smm", "automator"]
        for aid in ids:
            assert f'id:"{aid}"' in html, f"Agent id {aid} not found"

    def test_exactly_four_agents(self):
        html = generate_dashboard_html()
        assert html.count('"id:"') == 0 or True  # ids use id:"xxx" format
        # Count agent definitions in JS
        count = html.count("id:\"manager\"") + html.count("id:\"accountant\"") + \
                html.count("id:\"smm\"") + html.count("id:\"automator\"")
        assert count == 4


# ── Scenarios ────────────────────────────────────────────

class TestScenarios:
    def test_three_scenarios(self):
        html = generate_dashboard_html()
        assert "SMM-кампания" in html
        assert "Финансовый отчёт" in html
        assert "Полный цикл" in html

    def test_scenario_buttons(self):
        html = generate_dashboard_html()
        assert "scenario-btn-0" in html
        assert "scenario-btn-1" in html
        assert "scenario-btn-2" in html

    def test_scenario_steps_reference_valid_agents(self):
        html = generate_dashboard_html()
        valid_agents = {"manager", "accountant", "smm", "automator"}
        # Check from/to in scenario steps reference valid agents
        for agent in valid_agents:
            assert f'from:"{agent}"' in html or f'to:"{agent}"' in html


# ── Task Types ───────────────────────────────────────────

class TestTaskTypes:
    def test_all_task_types(self):
        html = generate_dashboard_html()
        tasks = ["Контент-план", "Дизайн", "Отчёт", "API запрос", "Стратегия", "Пост"]
        for task in tasks:
            assert task in html, f"Task type {task} not found"

    def test_task_emojis(self):
        html = generate_dashboard_html()
        emojis = ["📝", "🖼", "📊", "🔌", "🎯", "📮"]
        for emoji in emojis:
            assert emoji in html, f"Task emoji {emoji} not found"


# ── Animations & Controls ───────────────────────────────

class TestAnimations:
    def test_animation_keyframes(self):
        html = generate_dashboard_html()
        assert "dotPulse" in html
        assert "floatLabel" in html

    def test_animation_loop(self):
        html = generate_dashboard_html()
        assert "requestAnimationFrame" in html

    def test_easing_function(self):
        html = generate_dashboard_html()
        assert "ease" in html

    def test_bezier_curve(self):
        """Balls should fly on quadratic bezier curves."""
        html = generate_dashboard_html()
        assert "Q " in html  # SVG quadratic bezier command

    def test_svg_trails(self):
        html = generate_dashboard_html()
        assert "trails-svg" in html
        assert "createElementNS" in html

    def test_pause_play_controls(self):
        html = generate_dashboard_html()
        assert "toggleRunning" in html
        assert "toggle-btn" in html
        assert "Пауза" in html
        assert "Старт" in html

    def test_scenario_selector(self):
        html = generate_dashboard_html()
        assert "selectScenario" in html


# ── UI Components ────────────────────────────────────────

class TestUIComponents:
    def test_sidebar(self):
        html = generate_dashboard_html()
        assert "dash-sidebar" in html
        assert "Текущие задачи агентов" in html

    def test_activity_log(self):
        html = generate_dashboard_html()
        assert "log-container" in html
        assert "Лог активности" in html

    def test_task_legend(self):
        html = generate_dashboard_html()
        assert "legend-row" in html
        assert "Типы задач" in html

    def test_completed_counter(self):
        html = generate_dashboard_html()
        assert "completed-count" in html
        assert "Выполнено" in html

    def test_title(self):
        html = generate_dashboard_html()
        assert "Zinin Corp" in html
        assert "Dashboard" in html

    def test_progress_bars(self):
        html = generate_dashboard_html()
        assert "progress-bar-fill" in html
        assert "progress-track" in html


# ── Data Injection ───────────────────────────────────────

class TestDataInjection:
    def test_completed_count_default(self):
        html = generate_dashboard_html()
        assert '"completedCount": 0' in html or '"completedCount":0' in html

    def test_completed_count_custom(self):
        html = generate_dashboard_html(completed_count=42)
        assert "42" in html

    def test_agent_statuses_empty(self):
        html = generate_dashboard_html(agent_statuses={})
        assert '"agentStatuses": {}' in html or '"agentStatuses":{}' in html

    def test_agent_statuses_injected(self):
        statuses = {"manager": {"status": "working", "task": "test"}}
        html = generate_dashboard_html(agent_statuses=statuses)
        assert "working" in html

    def test_initial_data_is_valid_json(self):
        html = generate_dashboard_html(completed_count=10, agent_statuses={"x": 1})
        # Extract JSON between INITIAL = and ;
        start = html.find("const INITIAL = ") + len("const INITIAL = ")
        end = html.find(";", start)
        json_str = html[start:end]
        data = json.loads(json_str)
        assert data["completedCount"] == 10

    def test_recent_events_default_empty(self):
        html = generate_dashboard_html()
        assert '"recentEvents": []' in html or '"recentEvents":[]' in html

    def test_recent_events_injected(self):
        events = [
            {"agent": "manager", "action": "task_start", "description": "Test task"},
            {"agent": "smm", "action": "task_end", "description": "Post created"},
        ]
        html = generate_dashboard_html(recent_events=events)
        assert "Test task" in html
        assert "Post created" in html

    def test_recent_events_in_initial_json(self):
        events = [{"agent": "automator", "action": "communication", "description": "ping"}]
        html = generate_dashboard_html(recent_events=events)
        start = html.find("const INITIAL = ") + len("const INITIAL = ")
        end = html.find(";", start)
        data = json.loads(html[start:end])
        assert len(data["recentEvents"]) == 1
        assert data["recentEvents"][0]["agent"] == "automator"


# ── Real Data Loading ──────────────────────────────────────

class TestRealDataLoading:
    def test_load_real_data_function_exists(self):
        html = generate_dashboard_html()
        assert "loadRealData" in html

    def test_load_real_data_reads_agent_statuses(self):
        html = generate_dashboard_html()
        assert "INITIAL.agentStatuses" in html

    def test_load_real_data_reads_recent_events(self):
        html = generate_dashboard_html()
        assert "INITIAL.recentEvents" in html

    def test_demo_only_when_no_real_data(self):
        """Demo scenarios should only run when there's no real activity."""
        html = generate_dashboard_html()
        assert "!hasReal" in html


# ── Status Config ────────────────────────────────────────

class TestStatusConfig:
    def test_status_types(self):
        html = generate_dashboard_html()
        for status in ["idle", "sending", "working", "receiving"]:
            assert status in html

    def test_status_labels_russian(self):
        html = generate_dashboard_html()
        labels = ["Свободен", "Отправляет", "Работает", "Получает"]
        for label in labels:
            assert label in html, f"Status label '{label}' not found"
