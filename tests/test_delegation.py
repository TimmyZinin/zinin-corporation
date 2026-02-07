"""
🧪 Group 1: Auto-delegation tests

Tests that agents can delegate tasks to each other in chat.
When CEO Alexey says "поручаю Маттиасу подготовить бюджет",
Matthias should automatically respond in the chat.
"""

import pytest
import sys
import os
import re
from unittest.mock import MagicMock, patch, call
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from src.delegation_parser import (
    parse_delegations,
    _detect_target_agent,
    _has_delegation_verb,
)


# ──────────────────────────────────────────────────────────
# parse_delegations() — basic detection
# ──────────────────────────────────────────────────────────

class TestParseDelegations:
    """Tests for parse_delegations() — detecting delegation patterns."""

    def test_detects_poruchayu_mattiasu(self):
        """Detects 'поручаю Маттиасу' pattern."""
        text = "Поручаю Маттиасу подготовить финансовый отчёт за неделю."
        result = parse_delegations(text, source_agent="manager")
        assert len(result) == 1
        assert result[0]["agent_key"] == "accountant"
        assert "подготовить финансовый отчёт" in result[0]["task_description"]

    def test_detects_delegiruyu_martinu(self):
        """Detects 'делегирую Мартину' pattern."""
        text = "Делегирую Мартину настройку API интеграции с CRM системой."
        result = parse_delegations(text, source_agent="manager")
        assert len(result) == 1
        assert result[0]["agent_key"] == "automator"

    def test_detects_at_mention(self):
        """Detects '@Маттиас' mention pattern."""
        text = "@Маттиас, подготовь отчёт о расходах за январь."
        result = parse_delegations(text, source_agent="manager")
        assert len(result) == 1
        assert result[0]["agent_key"] == "accountant"

    def test_detects_dolzhen_pattern(self):
        """Detects 'Маттиас должен подготовить' pattern."""
        text = "Маттиас должен подготовить анализ затрат на API."
        result = parse_delegations(text, source_agent="manager")
        assert len(result) == 1
        assert result[0]["agent_key"] == "accountant"

    def test_detects_proshu_pattern(self):
        """Detects 'Прошу Мартина сделать' pattern."""
        text = "Прошу Мартина сделать деплой новой версии."
        result = parse_delegations(text, source_agent="manager")
        assert len(result) == 1
        assert result[0]["agent_key"] == "automator"

    def test_detects_neobkhodimo_pattern(self):
        """Detects 'необходимо ... подготовить ... Маттиас' pattern."""
        text = "Маттиасу необходимо подготовить P&L отчёт."
        result = parse_delegations(text, source_agent="manager")
        assert len(result) == 1
        assert result[0]["agent_key"] == "accountant"

    def test_detects_multiple_delegations(self):
        """Detects delegations to multiple agents."""
        text = """Вот мой план:
1. Поручаю Маттиасу подготовить финансовый отчёт
2. Делегирую Мартину настройку webhook интеграции
3. Юки должна подготовить контент-план на неделю"""
        result = parse_delegations(text, source_agent="manager")
        assert len(result) == 3
        agents = {d["agent_key"] for d in result}
        assert agents == {"accountant", "automator", "smm"}

    def test_detects_yuki_delegation(self):
        """Detects delegation to Yuki."""
        text = "Поручаю Юки написать пост для LinkedIn о наших достижениях."
        result = parse_delegations(text, source_agent="manager")
        assert len(result) == 1
        assert result[0]["agent_key"] == "smm"


# ──────────────────────────────────────────────────────────
# parse_delegations() — filtering
# ──────────────────────────────────────────────────────────

class TestDelegationFiltering:
    """Tests for filtering out invalid delegations."""

    def test_filters_self_delegation(self):
        """Does NOT return delegation when agent delegates to itself."""
        text = "Я, Алексей, должен подготовить стратегический план."
        result = parse_delegations(text, source_agent="manager")
        assert len(result) == 0

    def test_filters_self_delegation_accountant(self):
        """Accountant mentioning himself is not a delegation."""
        text = "Я, Маттиас, подготовлю отчёт к понедельнику."
        result = parse_delegations(text, source_agent="accountant")
        assert len(result) == 0

    def test_empty_text_returns_empty(self):
        """Empty text returns empty list."""
        assert parse_delegations("", source_agent="manager") == []
        assert parse_delegations("   ", source_agent="manager") == []

    def test_no_delegation_verbs(self):
        """Text with agent name but no delegation verb returns empty."""
        text = "Маттиас работает в финансовом отделе нашей компании."
        result = parse_delegations(text, source_agent="manager")
        assert len(result) == 0

    def test_short_lines_ignored(self):
        """Lines shorter than 10 chars are ignored."""
        text = "Маттиас\nподготовь"
        result = parse_delegations(text, source_agent="manager")
        assert len(result) == 0

    def test_deduplicates_same_agent(self):
        """Multiple delegations to same agent are deduplicated."""
        text = """Поручаю Маттиасу подготовить бюджет.
Также поручаю Маттиасу проанализировать расходы."""
        result = parse_delegations(text, source_agent="manager")
        assert len(result) == 1
        assert result[0]["agent_key"] == "accountant"

    def test_unknown_agent_ignored(self):
        """Unknown agent names don't create delegations."""
        text = "Поручаю Ивану подготовить отчёт."
        result = parse_delegations(text, source_agent="manager")
        assert len(result) == 0


# ──────────────────────────────────────────────────────────
# _detect_target_agent()
# ──────────────────────────────────────────────────────────

class TestDetectTargetAgent:
    """Tests for _detect_target_agent helper."""

    def test_detects_all_manager_forms(self):
        for form in ["алексей", "алексею", "алексея", "алексеем"]:
            assert _detect_target_agent(f"Поручаю {form}") == "manager"

    def test_detects_all_accountant_forms(self):
        for form in ["маттиас", "маттиасу", "маттиаса", "маттиасом"]:
            assert _detect_target_agent(f"Поручаю {form}") == "accountant"

    def test_detects_all_automator_forms(self):
        for form in ["мартин", "мартину", "мартина", "мартином"]:
            assert _detect_target_agent(f"Поручаю {form}") == "automator"

    def test_detects_smm(self):
        assert _detect_target_agent("Поручаю юки") == "smm"

    def test_returns_empty_for_unknown(self):
        assert _detect_target_agent("Поручаю Ивану") == ""

    def test_case_insensitive(self):
        assert _detect_target_agent("МАТТИАСУ подготовить") == "accountant"


# ──────────────────────────────────────────────────────────
# _has_delegation_verb()
# ──────────────────────────────────────────────────────────

class TestHasDelegationVerb:
    """Tests for _has_delegation_verb helper."""

    def test_poruchayu(self):
        assert _has_delegation_verb("поручаю подготовить") is True

    def test_delegiruyu(self):
        assert _has_delegation_verb("делегирую задачу") is True

    def test_dolzhen_podgotovit(self):
        assert _has_delegation_verb("должен подготовить") is True

    def test_proshu_sdelat(self):
        assert _has_delegation_verb("прошу сделать") is True

    def test_neobkhodimo_podgotovit(self):
        assert _has_delegation_verb("необходимо подготовить") is True

    def test_at_mention(self):
        assert _has_delegation_verb("@маттиас") is True

    def test_no_verb(self):
        assert _has_delegation_verb("работает в офисе") is False


# ──────────────────────────────────────────────────────────
# process_delegations() integration
# ──────────────────────────────────────────────────────────

class TestProcessDelegations:
    """Tests for process_delegations() wired into app.py broadcast loop."""

    def _build_process_delegations(self):
        """Extract process_delegations from app.py source."""
        app_path = os.path.join(os.path.dirname(__file__), "..", "app.py")
        with open(app_path, "r", encoding="utf-8") as f:
            source = f.read()

        # Find process_delegations function
        match = re.search(
            r"(def process_delegations\(.*?\n(?:(?:    |\n).*\n)*)",
            source,
        )
        if not match:
            pytest.skip("process_delegations not yet implemented in app.py")

        func_code = match.group(1)
        ns = {
            "datetime": datetime,
            "logging": __import__("logging"),
            "logger": __import__("logging").getLogger("test"),
        }

        # Import modules that process_delegations may use
        try:
            from src import activity_tracker
            ns["log_communication"] = activity_tracker.log_communication
            ns["log_delegation"] = activity_tracker.log_delegation
        except (ImportError, AttributeError):
            ns["log_communication"] = MagicMock()
            ns["log_delegation"] = MagicMock()

        # Get AGENTS dict
        agents_match = re.search(r"(AGENTS\s*=\s*\{.*?\n\})", source, re.DOTALL)
        if agents_match:
            exec(agents_match.group(1), ns)

        exec(func_code, ns)
        return ns["process_delegations"]

    def test_process_delegations_exists_in_app(self):
        """Verify process_delegations function exists in app.py."""
        app_path = os.path.join(os.path.dirname(__file__), "..", "app.py")
        with open(app_path, "r", encoding="utf-8") as f:
            source = f.read()
        assert "def process_delegations(" in source, \
            "process_delegations() must be defined in app.py"

    def test_process_delegations_called_in_broadcast_loop(self):
        """Verify process_delegations is called after extract_and_store in broadcast loop."""
        app_path = os.path.join(os.path.dirname(__file__), "..", "app.py")
        with open(app_path, "r", encoding="utf-8") as f:
            source = f.read()

        # Find the broadcast loop section (extract_and_store followed by process_delegations)
        idx_extract = source.find("extract_and_store(response")
        assert idx_extract > 0, "extract_and_store() call not found in app.py"

        # process_delegations should appear AFTER extract_and_store
        idx_process = source.find("process_delegations(", idx_extract)
        assert idx_process > idx_extract, \
            "process_delegations() must be called after extract_and_store() in broadcast loop"

    def test_process_delegations_adds_messages(self):
        """process_delegations should add delegated agent responses to session messages."""
        try:
            func = self._build_process_delegations()
        except Exception:
            pytest.skip("process_delegations not yet extractable")

        mock_corp = MagicMock()
        mock_corp.execute_task.return_value = "Отчёт подготовлен: расходы $500."
        mock_corp.is_ready = True

        mock_session = {"messages": []}

        delegations = [
            {"agent_key": "accountant", "task_description": "Подготовить бюджет"},
        ]

        func(delegations, mock_corp, mock_session)

        # Should have called execute_task
        mock_corp.execute_task.assert_called_once()

        # Should have added response to messages
        assert len(mock_session["messages"]) >= 1
        msg = mock_session["messages"][-1]
        assert msg["agent_key"] == "accountant"
        assert msg["role"] == "assistant"

    def test_process_delegations_limits_to_3(self):
        """process_delegations should limit max 3 delegations per response."""
        try:
            func = self._build_process_delegations()
        except Exception:
            pytest.skip("process_delegations not yet extractable")

        mock_corp = MagicMock()
        mock_corp.execute_task.return_value = "Done."
        mock_corp.is_ready = True

        mock_session = {"messages": []}

        delegations = [
            {"agent_key": "accountant", "task_description": "Task 1"},
            {"agent_key": "automator", "task_description": "Task 2"},
            {"agent_key": "smm", "task_description": "Task 3"},
            {"agent_key": "manager", "task_description": "Task 4"},
        ]

        func(delegations, mock_corp, mock_session)

        # Should be capped at 3
        assert mock_corp.execute_task.call_count <= 3

    def test_process_delegations_handles_empty(self):
        """process_delegations with empty list does nothing."""
        try:
            func = self._build_process_delegations()
        except Exception:
            pytest.skip("process_delegations not yet extractable")

        mock_corp = MagicMock()
        mock_session = {"messages": []}

        func([], mock_corp, mock_session)

        mock_corp.execute_task.assert_not_called()
        assert len(mock_session["messages"]) == 0

    def test_process_delegations_handles_error(self):
        """process_delegations handles execute_task errors gracefully."""
        try:
            func = self._build_process_delegations()
        except Exception:
            pytest.skip("process_delegations not yet extractable")

        mock_corp = MagicMock()
        mock_corp.execute_task.side_effect = Exception("API timeout")
        mock_corp.is_ready = True

        mock_session = {"messages": []}

        delegations = [
            {"agent_key": "accountant", "task_description": "Task 1"},
        ]

        # Should not raise
        func(delegations, mock_corp, mock_session)

        # Should still have a message (error message)
        assert len(mock_session["messages"]) >= 1


# ──────────────────────────────────────────────────────────
# Integration: delegation flow end-to-end
# ──────────────────────────────────────────────────────────

class TestDelegationIntegration:
    """Integration tests for the full delegation flow."""

    def test_alexey_response_triggers_matthias(self):
        """When Alexey's response contains delegation to Matthias,
        parse_delegations returns the delegation."""
        alexey_response = """
Отличный вопрос, Тим! Вот мой план действий:

1. **Финансовый анализ**: Поручаю Маттиасу подготовить детальный отчёт о текущих расходах и доходах
2. **Техническая оценка**: Мартин должен подготовить обзор API интеграций
3. Я координирую общую стратегию

Жду отчёты к концу дня.
"""
        delegations = parse_delegations(alexey_response, source_agent="manager")
        assert len(delegations) == 2
        agent_keys = [d["agent_key"] for d in delegations]
        assert "accountant" in agent_keys
        assert "automator" in agent_keys

    def test_accountant_response_no_self_delegation(self):
        """Accountant mentioning himself doesn't create delegation."""
        matthias_response = """
Вот финансовый отчёт, который я, Маттиас, подготовил:
- Расходы: $1,200
- Доходы: $3,500
- Прибыль: $2,300
"""
        delegations = parse_delegations(matthias_response, source_agent="accountant")
        assert len(delegations) == 0

    def test_no_delegation_in_simple_response(self):
        """Simple response without delegation patterns returns empty."""
        response = """
Текущий бюджет составляет $5,000 в месяц.
Основные статьи расходов: API ($800), хостинг ($200), зарплаты ($4,000).
"""
        delegations = parse_delegations(response, source_agent="manager")
        assert len(delegations) == 0
