"""Tests for agent YAML configs and crew config validity."""

import sys
import os

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

AGENTS_DIR = os.path.join(os.path.dirname(__file__), "..", "agents")
CREWS_DIR = os.path.join(os.path.dirname(__file__), "..", "crews")

EXPECTED_AGENTS = ["manager", "accountant", "automator", "yuki"]


# ── Agent Configs ────────────────────────────────────────

class TestAgentConfigs:
    def _load(self, name):
        path = os.path.join(AGENTS_DIR, f"{name}.yaml")
        assert os.path.exists(path), f"Config {name}.yaml not found"
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_all_agent_files_exist(self):
        for name in EXPECTED_AGENTS:
            path = os.path.join(AGENTS_DIR, f"{name}.yaml")
            assert os.path.exists(path), f"Missing {name}.yaml"

    def test_agent_configs_are_valid_yaml(self):
        for name in EXPECTED_AGENTS:
            cfg = self._load(name)
            assert isinstance(cfg, dict), f"{name}.yaml is not a dict"

    def test_agent_has_role(self):
        for name in EXPECTED_AGENTS:
            cfg = self._load(name)
            assert "role" in cfg, f"{name}.yaml missing 'role'"
            assert len(cfg["role"]) > 5

    def test_agent_has_goal(self):
        for name in EXPECTED_AGENTS:
            cfg = self._load(name)
            assert "goal" in cfg, f"{name}.yaml missing 'goal'"
            assert len(cfg["goal"]) > 10

    def test_agent_has_backstory(self):
        for name in EXPECTED_AGENTS:
            cfg = self._load(name)
            assert "backstory" in cfg, f"{name}.yaml missing 'backstory'"
            assert len(cfg["backstory"]) > 50

    def test_agent_has_llm(self):
        for name in EXPECTED_AGENTS:
            cfg = self._load(name)
            assert "llm" in cfg, f"{name}.yaml missing 'llm'"
            assert "openrouter/" in cfg["llm"] or "claude" in cfg["llm"]

    def test_no_fabrication_rule(self):
        """All agents should have anti-fabrication instructions."""
        for name in EXPECTED_AGENTS:
            cfg = self._load(name)
            backstory = cfg.get("backstory", "").lower()
            goal = cfg.get("goal", "").lower()
            combined = backstory + " " + goal
            has_rule = any(kw in combined for kw in [
                "запрет", "выдум", "fabricat", "не придумывай",
                "реальн", "факт", "подтвержд",
            ])
            assert has_rule, f"{name}.yaml missing anti-fabrication rule"


# ── Crew Config ──────────────────────────────────────────

class TestCrewConfig:
    def _load_crew(self):
        path = os.path.join(CREWS_DIR, "corporation.yaml")
        assert os.path.exists(path), "corporation.yaml not found"
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_crew_config_exists(self):
        path = os.path.join(CREWS_DIR, "corporation.yaml")
        assert os.path.exists(path)

    def test_crew_has_name(self):
        cfg = self._load_crew()
        assert "name" in cfg
        assert "Zinin Corp" in cfg["name"]

    def test_crew_has_agents(self):
        cfg = self._load_crew()
        assert "agents" in cfg
        assert isinstance(cfg["agents"], list)
        assert len(cfg["agents"]) >= 3

    def test_crew_manager_is_manager(self):
        cfg = self._load_crew()
        assert cfg.get("manager_agent") == "manager"

    def test_crew_memory_enabled(self):
        cfg = self._load_crew()
        assert cfg.get("memory") is True

    def test_crew_has_embedder(self):
        cfg = self._load_crew()
        assert "embedder" in cfg
