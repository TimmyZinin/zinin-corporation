"""
Tests for Knowledge Sources (#11) — business documents for RAG.
"""

import os
import pytest


KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), "..", "knowledge")


# ── Knowledge files exist ────────────────────────────────

class TestKnowledgeFiles:
    def test_knowledge_dir_exists(self):
        assert os.path.isdir(KNOWLEDGE_DIR), "knowledge/ directory not found"

    def test_company_md_exists(self):
        assert os.path.isfile(os.path.join(KNOWLEDGE_DIR, "company.md"))

    def test_team_md_exists(self):
        assert os.path.isfile(os.path.join(KNOWLEDGE_DIR, "team.md"))

    def test_content_guidelines_md_exists(self):
        assert os.path.isfile(os.path.join(KNOWLEDGE_DIR, "content_guidelines.md"))

    def test_at_least_3_files(self):
        files = [f for f in os.listdir(KNOWLEDGE_DIR) if f.endswith((".md", ".txt"))]
        assert len(files) >= 3, f"Expected 3+ knowledge files, got {len(files)}"


# ── Knowledge file content ───────────────────────────────

class TestKnowledgeContent:
    def _read(self, name):
        with open(os.path.join(KNOWLEDGE_DIR, name), "r", encoding="utf-8") as f:
            return f.read()

    def test_company_has_projects(self):
        content = self._read("company.md")
        assert "Крипто маркетологи" in content
        assert "Сборка" in content

    def test_company_has_tech_stack(self):
        content = self._read("company.md")
        assert "CrewAI" in content
        assert "Railway" in content

    def test_team_has_all_agents(self):
        content = self._read("team.md")
        assert "Алексей" in content
        assert "Маттиас" in content
        assert "Мартин" in content
        assert "Юки" in content
        assert "Райан" in content

    def test_team_has_roles(self):
        content = self._read("team.md")
        assert "CEO" in content
        assert "CFO" in content
        assert "CTO" in content
        assert "SMM" in content

    def test_guidelines_has_rules(self):
        content = self._read("content_guidelines.md")
        assert "LinkedIn" in content
        assert "Telegram" in content
        assert "антифабрикац" in content.lower() or "НИКОГДА" in content


# ── Knowledge loader function ────────────────────────────

class TestKnowledgeLoader:
    def test_load_function_exists(self):
        from src.crew import _load_knowledge_sources
        assert callable(_load_knowledge_sources)

    def test_load_returns_list(self):
        from src.crew import _load_knowledge_sources
        result = _load_knowledge_sources()
        assert isinstance(result, list)

    def test_knowledge_sources_global(self):
        from src.crew import KNOWLEDGE_SOURCES
        assert isinstance(KNOWLEDGE_SOURCES, list)

    def test_crew_module_has_knowledge_in_run_agent(self):
        """_run_agent should pass knowledge_sources to Crew when available."""
        import inspect
        from src.crew import AICorporation
        src = inspect.getsource(AICorporation._run_agent)
        assert "KNOWLEDGE_SOURCES" in src or "knowledge_sources" in src
