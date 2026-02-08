"""
🧪 Tests for DelegateTaskTool — the manager's delegation instrument

Verifies that:
1. Tool exists and has correct interface
2. Tool validates agent names
3. Tool calls execute_task on the corporation
4. Manager agent has the delegation tool
5. Manager YAML instructs delegation
"""

import pytest
import sys
import os
import re
import yaml
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ──────────────────────────────────────────────────────────
# Tool existence and interface
# ──────────────────────────────────────────────────────────

class TestDelegateTaskToolInterface:
    """Tests that DelegateTaskTool has correct interface."""

    def test_tool_importable(self):
        """DelegateTaskTool can be imported."""
        from src.tools.delegation_tool import DelegateTaskTool
        tool = DelegateTaskTool()
        assert tool is not None

    def test_tool_has_name(self):
        """Tool has a name."""
        from src.tools.delegation_tool import DelegateTaskTool
        tool = DelegateTaskTool()
        assert tool.name == "Delegate Task"

    def test_tool_has_description(self):
        """Tool has a description mentioning available agents."""
        from src.tools.delegation_tool import DelegateTaskTool
        tool = DelegateTaskTool()
        assert "accountant" in tool.description
        assert "smm" in tool.description
        assert "automator" in tool.description

    def test_tool_has_args_schema(self):
        """Tool has args_schema with agent_name and task_description."""
        from src.tools.delegation_tool import DelegateTaskTool
        tool = DelegateTaskTool()
        schema = tool.args_schema
        fields = schema.model_fields
        assert "agent_name" in fields
        assert "task_description" in fields

    def test_delegatable_agents_correct(self):
        """DELEGATABLE_AGENTS has correct keys."""
        from src.tools.delegation_tool import DELEGATABLE_AGENTS
        assert set(DELEGATABLE_AGENTS.keys()) == {"accountant", "smm", "automator", "designer"}
        # Manager should NOT be delegatable (prevents self-delegation loops)
        assert "manager" not in DELEGATABLE_AGENTS


# ──────────────────────────────────────────────────────────
# Tool validation
# ──────────────────────────────────────────────────────────

class TestDelegateTaskToolValidation:
    """Tests that tool validates inputs correctly."""

    def test_rejects_unknown_agent(self):
        """Tool returns error for unknown agent names."""
        from src.tools.delegation_tool import DelegateTaskTool
        tool = DelegateTaskTool()
        result = tool._run(agent_name="janitor", task_description="Убери офис")
        assert "не найден" in result or "не найден" in result.lower()

    def test_rejects_manager_self_delegation(self):
        """Tool cannot delegate to manager (prevent recursion)."""
        from src.tools.delegation_tool import DelegateTaskTool
        tool = DelegateTaskTool()
        result = tool._run(agent_name="manager", task_description="Подготовь план")
        assert "не найден" in result

    def test_accepts_valid_agent_names(self):
        """Tool accepts valid agent names (accountant, smm, automator)."""
        from src.tools.delegation_tool import DelegateTaskTool
        tool = DelegateTaskTool()

        # Mock the corporation to avoid actual API calls
        mock_corp = MagicMock()
        mock_corp.is_ready = True
        mock_corp.execute_task.return_value = "Отчёт готов"

        with patch("src.crew.get_corporation", return_value=mock_corp):
            for agent in ["accountant", "smm", "automator", "designer"]:
                result = tool._run(agent_name=agent, task_description="Test task")
                assert "Ответ от" in result or "Отчёт готов" in result


# ──────────────────────────────────────────────────────────
# Tool execution
# ──────────────────────────────────────────────────────────

class TestDelegateTaskToolExecution:
    """Tests that tool correctly calls execute_task."""

    def test_calls_execute_task(self):
        """Tool calls corp.execute_task with correct arguments."""
        from src.tools.delegation_tool import DelegateTaskTool
        tool = DelegateTaskTool()

        mock_corp = MagicMock()
        mock_corp.is_ready = True
        mock_corp.execute_task.return_value = "Контент-план готов"

        with patch("src.crew.get_corporation", return_value=mock_corp):
            result = tool._run(
                agent_name="smm",
                task_description="Подготовь контент-план для LinkedIn"
            )

        mock_corp.execute_task.assert_called_once_with(
            "Подготовь контент-план для LinkedIn", "smm"
        )
        assert "Контент-план готов" in result

    def test_returns_agent_name_in_result(self):
        """Result mentions agent name for clarity."""
        from src.tools.delegation_tool import DelegateTaskTool
        tool = DelegateTaskTool()

        mock_corp = MagicMock()
        mock_corp.is_ready = True
        mock_corp.execute_task.return_value = "Бюджет: $5000"

        with patch("src.crew.get_corporation", return_value=mock_corp):
            result = tool._run(
                agent_name="accountant",
                task_description="Подготовь бюджет"
            )

        assert "Маттиас" in result

    def test_handles_execution_error(self):
        """Tool handles execute_task errors gracefully."""
        from src.tools.delegation_tool import DelegateTaskTool
        tool = DelegateTaskTool()

        mock_corp = MagicMock()
        mock_corp.is_ready = True
        mock_corp.execute_task.side_effect = Exception("API timeout")

        with patch("src.crew.get_corporation", return_value=mock_corp):
            result = tool._run(
                agent_name="smm",
                task_description="Напиши пост"
            )

        assert "Ошибка" in result
        assert "Юки" in result

    def test_handles_uninitialized_corporation(self):
        """Tool handles case when corporation is not ready."""
        from src.tools.delegation_tool import DelegateTaskTool
        tool = DelegateTaskTool()

        mock_corp = MagicMock()
        mock_corp.is_ready = False

        with patch("src.crew.get_corporation", return_value=mock_corp):
            result = tool._run(
                agent_name="smm",
                task_description="Напиши пост"
            )

        assert "не инициализирована" in result


# ──────────────────────────────────────────────────────────
# Manager agent configuration
# ──────────────────────────────────────────────────────────

class TestManagerHasDelegationTool:
    """Tests that manager agent is configured with DelegateTaskTool."""

    def test_agents_py_loads_delegation_tool(self):
        """agents.py has _load_delegation_tool function."""
        agents_path = os.path.join(os.path.dirname(__file__), "..", "src", "agents.py")
        with open(agents_path, "r", encoding="utf-8") as f:
            source = f.read()
        assert "_load_delegation_tool" in source

    def test_manager_tools_include_delegation(self):
        """Manager agent creation includes delegation tool in tools list."""
        agents_path = os.path.join(os.path.dirname(__file__), "..", "src", "agents.py")
        with open(agents_path, "r", encoding="utf-8") as f:
            source = f.read()

        # Find the create_manager_agent function
        assert "_load_delegation_tool()" in source, \
            "create_manager_agent must call _load_delegation_tool()"


# ──────────────────────────────────────────────────────────
# Manager YAML delegation rules
# ──────────────────────────────────────────────────────────

class TestManagerYamlDelegation:
    """Tests that manager YAML has explicit delegation rules."""

    def _load_manager_yaml(self):
        paths = [
            os.path.join(os.path.dirname(__file__), "..", "agents", "manager.yaml"),
        ]
        for p in paths:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f)
        pytest.skip("manager.yaml not found")

    def test_yaml_mentions_delegate_task(self):
        """Manager YAML mentions Delegate Task tool."""
        config = self._load_manager_yaml()
        backstory = config.get("backstory", "")
        assert "Delegate Task" in backstory, \
            "Manager backstory must mention Delegate Task tool"

    def test_yaml_has_delegation_rules(self):
        """Manager YAML has rules for when to delegate to each agent."""
        config = self._load_manager_yaml()
        backstory = config.get("backstory", "")
        assert "smm" in backstory.lower() or "юки" in backstory.lower()
        assert "accountant" in backstory.lower() or "маттиас" in backstory.lower()
        assert "automator" in backstory.lower() or "мартин" in backstory.lower()

    def test_yaml_instructs_not_to_do_specialist_work(self):
        """Manager YAML says CEO should NOT do specialist work himself."""
        config = self._load_manager_yaml()
        backstory = config.get("backstory", "")
        # Check for anti-pattern instruction
        assert "НИКОГДА не пытайся сам" in backstory or "НЕ выполняешь" in backstory, \
            "Manager must be told NOT to do specialist work"

    def test_yaml_maps_content_to_yuki(self):
        """YAML explicitly maps content/SMM tasks to Yuki."""
        config = self._load_manager_yaml()
        backstory = config.get("backstory", "")
        # Check that content/SMM is mapped to smm/Юки
        assert re.search(r"контент.*smm|smm.*юки|контент.*юки", backstory, re.IGNORECASE), \
            "YAML must map content tasks to Юки (smm)"

    def test_yaml_maps_finance_to_matthias(self):
        """YAML explicitly maps finance tasks to Matthias."""
        config = self._load_manager_yaml()
        backstory = config.get("backstory", "")
        assert re.search(r"финанс.*accountant|accountant.*маттиас|финанс.*маттиас", backstory, re.IGNORECASE), \
            "YAML must map finance tasks to Маттиас (accountant)"
