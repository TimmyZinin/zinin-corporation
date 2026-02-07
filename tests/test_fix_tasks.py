"""
🧪 Tests for Fix #3: Task extraction from chat conversations

Verifies:
1. task_extractor module exists with extraction + storage
2. Action verb detection works for Russian imperative forms
3. Agent assignee detection works
4. Deadline detection works
5. Task queue persistence (save/load round-trip)
6. Integration with app.py chat flow
7. Dynamic tasks shown in Tasks tab
8. Regression: nothing broken
"""

import ast
import json
import os
import re
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

APP_PATH = os.path.join(os.path.dirname(__file__), "..", "app.py")
EXTRACTOR_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "task_extractor.py")


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ──────────────────────────────────────────────────────────
# 1. Module structure
# ──────────────────────────────────────────────────────────

class TestTaskExtractorModule:
    """Verify the task_extractor module exists and has correct structure."""

    def test_module_exists(self):
        assert os.path.exists(EXTRACTOR_PATH)

    def test_importable(self):
        from src.task_extractor import (
            extract_tasks_from_message,
            extract_and_store,
            load_task_queue,
            save_task_queue,
            add_tasks,
            complete_task,
            get_pending_tasks,
        )
        assert callable(extract_tasks_from_message)
        assert callable(extract_and_store)
        assert callable(load_task_queue)

    def test_has_agent_patterns(self):
        from src.task_extractor import AGENT_PATTERNS
        assert "manager" in AGENT_PATTERNS
        assert "accountant" in AGENT_PATTERNS
        assert "automator" in AGENT_PATTERNS
        assert "smm" in AGENT_PATTERNS

    def test_has_action_verbs(self):
        from src.task_extractor import ACTION_VERBS
        assert len(ACTION_VERBS) >= 5

    def test_has_deadline_patterns(self):
        from src.task_extractor import DEADLINE_PATTERNS
        assert len(DEADLINE_PATTERNS) >= 3

    def test_valid_python(self):
        source = _read(EXTRACTOR_PATH)
        ast.parse(source)


# ──────────────────────────────────────────────────────────
# 2. Extraction: action verb detection
# ──────────────────────────────────────────────────────────

class TestActionVerbDetection:
    """Verify Russian action verb detection works."""

    def test_detects_сделай(self):
        from src.task_extractor import _has_action_verb
        assert _has_action_verb("Мартин, сделай аудит API") is True

    def test_detects_подготовь(self):
        from src.task_extractor import _has_action_verb
        assert _has_action_verb("подготовь финансовый отчёт") is True

    def test_detects_проверь(self):
        from src.task_extractor import _has_action_verb
        assert _has_action_verb("проверь интеграцию с Telegram") is True

    def test_detects_опубликуй(self):
        from src.task_extractor import _has_action_verb
        assert _has_action_verb("опубликуй пост в LinkedIn") is True

    def test_no_action_in_statement(self):
        from src.task_extractor import _has_action_verb
        assert _has_action_verb("Финансовый отчёт за Q4 показал рост") is False

    def test_no_action_in_greeting(self):
        from src.task_extractor import _has_action_verb
        assert _has_action_verb("Добрый день, коллеги") is False


# ──────────────────────────────────────────────────────────
# 3. Extraction: assignee detection
# ──────────────────────────────────────────────────────────

class TestAssigneeDetection:
    """Verify agent name detection for task assignment."""

    def test_detects_martin(self):
        from src.task_extractor import _detect_assignee
        assert _detect_assignee("Мартин, сделай аудит") == "automator"

    def test_detects_matthias(self):
        from src.task_extractor import _detect_assignee
        assert _detect_assignee("Маттиас, подготовь отчёт") == "accountant"

    def test_detects_yuki(self):
        from src.task_extractor import _detect_assignee
        assert _detect_assignee("Юки, опубликуй пост") == "smm"

    def test_detects_aleksey(self):
        from src.task_extractor import _detect_assignee
        assert _detect_assignee("Алексей, проверь стратегию") == "manager"

    def test_dative_case_martinu(self):
        from src.task_extractor import _detect_assignee
        assert _detect_assignee("поручи Мартину проверить") == "automator"

    def test_no_agent_mentioned(self):
        from src.task_extractor import _detect_assignee
        assert _detect_assignee("проверь интеграцию") == ""


# ──────────────────────────────────────────────────────────
# 4. Extraction: deadline detection
# ──────────────────────────────────────────────────────────

class TestDeadlineDetection:
    """Verify deadline extraction from text."""

    def test_до_пятницы(self):
        from src.task_extractor import _detect_deadline
        assert _detect_deadline("сделай аудит до пятницы") == "до пятницы"

    def test_к_понедельнику(self):
        from src.task_extractor import _detect_deadline
        assert _detect_deadline("подготовь отчёт к понедельнику") == "к понедельнику"

    def test_сегодня(self):
        from src.task_extractor import _detect_deadline
        assert _detect_deadline("опубликуй пост сегодня") == "сегодня"

    def test_завтра(self):
        from src.task_extractor import _detect_deadline
        assert _detect_deadline("отправь отчёт завтра") == "завтра"

    def test_до_конца_дня(self):
        from src.task_extractor import _detect_deadline
        assert _detect_deadline("проверь до конца дня") == "до конца дня"

    def test_no_deadline(self):
        from src.task_extractor import _detect_deadline
        assert _detect_deadline("сделай аудит API") == ""


# ──────────────────────────────────────────────────────────
# 5. Full extraction pipeline
# ──────────────────────────────────────────────────────────

class TestFullExtraction:
    """Test end-to-end extraction from realistic messages."""

    def test_ceo_delegation_message(self):
        from src.task_extractor import extract_tasks_from_message
        message = (
            "Хорошо, Тим. Вот мой план:\n"
            "1. Мартин, сделай аудит API расходов до пятницы\n"
            "2. Маттиас, обнови финансовый отчёт к среде\n"
            "3. Юки, опубликуй 3 поста в LinkedIn на этой неделе\n"
        )
        tasks = extract_tasks_from_message(message, source_agent="manager")
        assert len(tasks) == 3
        assert tasks[0]["assignee"] == "automator"
        assert tasks[0]["deadline"] == "до пятницы"
        assert tasks[1]["assignee"] == "accountant"
        assert tasks[2]["assignee"] == "smm"

    def test_single_delegation(self):
        from src.task_extractor import extract_tasks_from_message
        tasks = extract_tasks_from_message(
            "Мартин, проверь интеграцию с Telegram до конца дня",
            source_agent="manager",
        )
        assert len(tasks) == 1
        assert tasks[0]["assignee"] == "automator"
        assert tasks[0]["deadline"] == "до конца дня"
        assert tasks[0]["source_agent"] == "manager"
        assert tasks[0]["status"] == "pending"

    def test_no_tasks_in_regular_response(self):
        from src.task_extractor import extract_tasks_from_message
        message = (
            "Финансовый отчёт за Q4:\n"
            "- Выручка: 2.4M USD\n"
            "- ROI: 340%\n"
            "- Все показатели в норме."
        )
        tasks = extract_tasks_from_message(message)
        assert tasks == []

    def test_short_lines_ignored(self):
        from src.task_extractor import extract_tasks_from_message
        tasks = extract_tasks_from_message("ОК\nДа\nНет")
        assert tasks == []

    def test_task_fields_complete(self):
        from src.task_extractor import extract_tasks_from_message
        tasks = extract_tasks_from_message(
            "Маттиас, подготовь отчёт к пятнице",
            source_agent="manager",
        )
        assert len(tasks) == 1
        task = tasks[0]
        assert "action" in task
        assert "assignee" in task
        assert "deadline" in task
        assert "source_agent" in task
        assert "created_at" in task
        assert "status" in task


# ──────────────────────────────────────────────────────────
# 6. Task queue storage
# ──────────────────────────────────────────────────────────

class TestTaskQueueStorage:
    """Test task queue persistence."""

    def test_save_and_load_round_trip(self, tmp_path):
        from src.task_extractor import save_task_queue, load_task_queue
        queue_file = tmp_path / "task_queue.json"
        tasks = [
            {"action": "Проверь API", "assignee": "automator", "status": "pending"},
        ]
        with patch("src.task_extractor._tasks_path", return_value=str(queue_file)):
            assert save_task_queue(tasks) is True
            loaded = load_task_queue()
            assert len(loaded) == 1
            assert loaded[0]["action"] == "Проверь API"

    def test_load_missing_file_returns_empty(self, tmp_path):
        from src.task_extractor import load_task_queue
        missing = tmp_path / "nonexistent.json"
        with patch("src.task_extractor._tasks_path", return_value=str(missing)):
            assert load_task_queue() == []

    def test_add_tasks_appends(self, tmp_path):
        from src.task_extractor import add_tasks, load_task_queue
        queue_file = tmp_path / "task_queue.json"
        with patch("src.task_extractor._tasks_path", return_value=str(queue_file)):
            add_tasks([{"action": "Task 1", "status": "pending"}])
            add_tasks([{"action": "Task 2", "status": "pending"}])
            queue = load_task_queue()
            assert len(queue) == 2

    def test_complete_task_marks_completed(self, tmp_path):
        from src.task_extractor import save_task_queue, complete_task, load_task_queue
        queue_file = tmp_path / "task_queue.json"
        tasks = [{"action": "Do X", "status": "pending"}]
        with patch("src.task_extractor._tasks_path", return_value=str(queue_file)):
            save_task_queue(tasks)
            assert complete_task(0) is True
            queue = load_task_queue()
            assert queue[0]["status"] == "completed"
            assert "completed_at" in queue[0]

    def test_get_pending_filters_completed(self, tmp_path):
        from src.task_extractor import save_task_queue, get_pending_tasks
        queue_file = tmp_path / "task_queue.json"
        tasks = [
            {"action": "Done", "status": "completed"},
            {"action": "Open", "status": "pending"},
        ]
        with patch("src.task_extractor._tasks_path", return_value=str(queue_file)):
            save_task_queue(tasks)
            pending = get_pending_tasks()
            assert len(pending) == 1
            assert pending[0]["action"] == "Open"

    def test_cyrillic_preserved(self, tmp_path):
        from src.task_extractor import save_task_queue, load_task_queue
        queue_file = tmp_path / "task_queue.json"
        tasks = [{"action": "Подготовь финансовый отчёт", "status": "pending"}]
        with patch("src.task_extractor._tasks_path", return_value=str(queue_file)):
            save_task_queue(tasks)
            raw = queue_file.read_text(encoding="utf-8")
            assert "Подготовь" in raw  # ensure_ascii=False
            loaded = load_task_queue()
            assert loaded[0]["action"] == "Подготовь финансовый отчёт"


# ──────────────────────────────────────────────────────────
# 7. extract_and_store integration
# ──────────────────────────────────────────────────────────

class TestExtractAndStore:
    """Test extract_and_store() combines extraction + storage."""

    def test_extracts_and_saves(self, tmp_path):
        from src.task_extractor import extract_and_store, load_task_queue
        queue_file = tmp_path / "task_queue.json"
        with patch("src.task_extractor._tasks_path", return_value=str(queue_file)):
            tasks = extract_and_store(
                "Мартин, проверь API до пятницы",
                source_agent="manager",
            )
            assert len(tasks) == 1
            queue = load_task_queue()
            assert len(queue) == 1
            assert queue[0]["assignee"] == "automator"

    def test_no_tasks_nothing_saved(self, tmp_path):
        from src.task_extractor import extract_and_store, load_task_queue
        queue_file = tmp_path / "task_queue.json"
        with patch("src.task_extractor._tasks_path", return_value=str(queue_file)):
            tasks = extract_and_store("Всё хорошо, продолжаем работу.")
            assert tasks == []
            queue = load_task_queue()
            assert queue == []


# ──────────────────────────────────────────────────────────
# 8. app.py integration
# ──────────────────────────────────────────────────────────

class TestAppIntegration:
    """Verify app.py uses the task_extractor module."""

    def test_app_imports_task_extractor(self):
        source = _read(APP_PATH)
        assert "from src.task_extractor import" in source

    def test_app_imports_extract_and_store(self):
        source = _read(APP_PATH)
        assert "extract_and_store" in source

    def test_app_imports_load_task_queue(self):
        source = _read(APP_PATH)
        assert "load_task_queue" in source

    def test_extract_called_after_response(self):
        """extract_and_store is called in the chat flow after agent response."""
        source = _read(APP_PATH)
        lines = source.split("\n")
        # Find the pending_prompt processing block
        for i, line in enumerate(lines):
            if '"pending_prompt" in st.session_state' in line:
                block = "\n".join(lines[i:i + 80])
                assert "extract_and_store" in block, (
                    "extract_and_store should be called in the chat flow"
                )
                return
        pytest.fail("pending_prompt block not found")

    def test_dynamic_tasks_section_in_tab3(self):
        """Tab3 has a section for dynamically extracted tasks."""
        source = _read(APP_PATH)
        assert "load_task_queue" in source
        assert "Задачи из чата" in source

    def test_complete_task_in_app(self):
        """app.py imports complete_task for marking tasks done."""
        source = _read(APP_PATH)
        assert "complete_task" in source

    def test_app_valid_python(self):
        source = _read(APP_PATH)
        ast.parse(source)


# ──────────────────────────────────────────────────────────
# 9. Regression: existing features still work
# ──────────────────────────────────────────────────────────

class TestRegression:
    """Verify existing functionality is not broken."""

    def test_predefined_tasks_still_exist(self):
        """The 7 predefined quick-tasks are still in tab3."""
        source = _read(APP_PATH)
        expected = [
            "strategic_review",
            "financial_report",
            "api_budget_check",
            "subscription_analysis",
            "system_health_check",
            "integration_status",
            "full_corporation_report",
        ]
        for method in expected:
            assert f'"method": "{method}"' in source

    def test_format_chat_context_still_exists(self):
        source = _read(APP_PATH)
        assert "def format_chat_context" in source

    def test_detect_agents_still_exists(self):
        source = _read(APP_PATH)
        assert "def detect_agents" in source

    def test_save_chat_history_still_called(self):
        source = _read(APP_PATH)
        assert "save_chat_history" in source

    def test_activity_tracker_not_modified(self):
        """activity_tracker.py should NOT be modified by this fix."""
        tracker_path = os.path.join(os.path.dirname(__file__), "..", "src", "activity_tracker.py")
        source = _read(tracker_path)
        # Still only has log/get functions
        assert "task_queue" not in source
        assert "extract" not in source
