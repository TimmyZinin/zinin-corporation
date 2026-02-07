"""Tests for app.py — Streamlit app structure and imports."""

import sys
import os
import ast

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

APP_PATH = os.path.join(os.path.dirname(__file__), "..", "app.py")


# ── Syntax & Structure ──────────────────────────────────

class TestAppStructure:
    def test_app_file_exists(self):
        assert os.path.exists(APP_PATH)

    def test_valid_python_syntax(self):
        with open(APP_PATH, "r", encoding="utf-8") as f:
            source = f.read()
        ast.parse(source)  # raises SyntaxError if invalid

    def test_has_main_function(self):
        with open(APP_PATH, "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        func_names = [
            node.name for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
        ]
        assert "main" in func_names

    def test_main_guard(self):
        with open(APP_PATH, "r", encoding="utf-8") as f:
            source = f.read()
        assert 'if __name__ == "__main__"' in source


# ── Tabs ─────────────────────────────────────────────────

class TestTabs:
    def _read_app(self):
        with open(APP_PATH, "r", encoding="utf-8") as f:
            return f.read()

    def test_has_seven_tabs(self):
        source = self._read_app()
        assert "st.tabs(" in source
        # Should have 7 tab names in the tabs call
        expected_tabs = [
            "Чат", "Агенты", "Задачи", "Контент",
            "Мониторинг", "Дашборд", "Статистика",
        ]
        for tab in expected_tabs:
            assert tab in source, f"Tab '{tab}' not found in app.py"

    def test_dashboard_tab_exists(self):
        source = self._read_app()
        assert "🎮 Дашборд" in source

    def test_dashboard_imports_module(self):
        source = self._read_app()
        assert "from src.dashboard import generate_dashboard_html" in source

    def test_dashboard_uses_components_html(self):
        source = self._read_app()
        assert "st_components.html(dash_html" in source

    def test_chat_tab(self):
        source = self._read_app()
        assert "💬 Чат" in source

    def test_monitoring_tab(self):
        source = self._read_app()
        assert "📡 Мониторинг" in source


# ── Agent Registry ───────────────────────────────────────

class TestAppAgents:
    def _read_app(self):
        with open(APP_PATH, "r", encoding="utf-8") as f:
            return f.read()

    def test_agents_dict(self):
        source = self._read_app()
        assert "AGENTS = {" in source

    def test_all_agents_in_registry(self):
        source = self._read_app()
        for key in ["manager", "accountant", "smm", "automator"]:
            assert f'"{key}"' in source

    def test_agent_colors(self):
        source = self._read_app()
        assert "AGENT_COLORS" in source


# ── Imports ──────────────────────────────────────────────

class TestImports:
    def _read_app(self):
        with open(APP_PATH, "r", encoding="utf-8") as f:
            return f.read()

    def test_streamlit_import(self):
        source = self._read_app()
        assert "import streamlit as st" in source

    def test_components_import(self):
        source = self._read_app()
        assert "streamlit.components.v1" in source

    def test_yaml_import(self):
        source = self._read_app()
        assert "import yaml" in source


# ── Dashboard Module ─────────────────────────────────────

class TestDashboardModule:
    def test_dashboard_module_importable(self):
        from src.dashboard import generate_dashboard_html
        assert callable(generate_dashboard_html)

    def test_activity_tracker_importable(self):
        from src.activity_tracker import get_all_statuses
        assert callable(get_all_statuses)
