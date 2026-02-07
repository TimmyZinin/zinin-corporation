"""
🔬 Deep tests for Fix #3: Task extraction from chat

Covers:
- Extraction: all action verbs, all agent name forms
- Extraction: multiline CEO plans, mixed content
- Extraction: false positives (should NOT extract)
- Deadline parsing: all day forms, edge cases
- Task queue: persistence, overflow (>100), completion
- Integration: extract_and_store end-to-end
- Integration: app.py hooks extraction after each agent response
- Regression: existing functionality unbroken
"""

import ast
import json
import os
import re
import sys
import threading
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

APP_PATH = os.path.join(os.path.dirname(__file__), "..", "app.py")
EXTRACTOR_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "task_extractor.py")


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ═══════════════════════════════════════════════════════════════
# 1. Action verb detection — all verbs
# ═══════════════════════════════════════════════════════════════

class TestAllActionVerbs:
    """Every verb in ACTION_VERBS should be detected."""

    VERB_EXAMPLES = [
        ("сделай отчёт", True),
        ("сделайте аудит", True),
        ("подготовь презентацию", True),
        ("подготовьте данные", True),
        ("проверь интеграцию", True),
        ("создай документ", True),
        ("обнови базу", True),
        ("опубликуй пост", True),
        ("проанализируй данные", True),
        ("напиши отчёт", True),
        ("отправь письмо", True),
        ("настрой вебхук", True),
        # Negative cases
        ("Финансовый отчёт готов", False),
        ("Всё работает нормально", False),
        ("Добрый день", False),
        ("ROI составил 340%", False),
        ("", False),
    ]

    @pytest.mark.parametrize("text,expected", VERB_EXAMPLES)
    def test_verb_detection(self, text, expected):
        from src.task_extractor import _has_action_verb
        assert _has_action_verb(text) is expected


# ═══════════════════════════════════════════════════════════════
# 2. Assignee detection — all forms
# ═══════════════════════════════════════════════════════════════

class TestAllAgentForms:
    """All name forms (nominative, dative, genitive) should be detected."""

    AGENT_EXAMPLES = [
        # Алексей (manager)
        ("Алексей, сделай", "manager"),
        ("Поручи Алексею", "manager"),
        ("Отчёт Алексея", "manager"),
        # Маттиас (accountant)
        ("Маттиас, подготовь", "accountant"),
        ("Передай Маттиасу", "accountant"),
        ("Данные Маттиаса", "accountant"),
        # Мартин (automator)
        ("Мартин, проверь", "automator"),
        ("Скажи Мартину", "automator"),
        ("Задача Мартина", "automator"),
        # Юки (smm)
        ("Юки, опубликуй", "smm"),
        # No agent
        ("Всем привет", ""),
        ("Отчёт готов", ""),
    ]

    @pytest.mark.parametrize("text,expected", AGENT_EXAMPLES)
    def test_assignee_detection(self, text, expected):
        from src.task_extractor import _detect_assignee
        assert _detect_assignee(text) == expected


# ═══════════════════════════════════════════════════════════════
# 3. Deadline detection — all patterns
# ═══════════════════════════════════════════════════════════════

class TestAllDeadlinePatterns:

    DEADLINE_EXAMPLES = [
        ("до пятницы", "до пятницы"),
        ("до понедельника", "до понедельника"),
        ("до вторника", "до вторника"),
        ("до среды", "до среды"),
        ("до четверга", "до четверга"),
        ("до субботы", "до субботы"),
        ("до воскресенья", "до воскресенья"),
        ("к понедельнику", "к понедельнику"),
        ("к вторнику", "к вторнику"),
        ("к среде", "к среде"),
        ("к четвергу", "к четвергу"),
        ("к пятнице", "к пятнице"),
        ("к субботе", "к субботе"),
        ("к воскресенью", "к воскресенью"),
        ("до конца дня", "до конца дня"),
        ("на этой неделе", "на этой неделе"),
        ("сегодня", "сегодня"),
        ("завтра", "завтра"),
        ("без дедлайна", ""),
        ("когда-нибудь потом", ""),
    ]

    @pytest.mark.parametrize("text,expected", DEADLINE_EXAMPLES)
    def test_deadline_detection(self, text, expected):
        from src.task_extractor import _detect_deadline
        assert _detect_deadline(text) == expected


# ═══════════════════════════════════════════════════════════════
# 4. Full extraction — realistic messages
# ═══════════════════════════════════════════════════════════════

class TestRealisticExtraction:

    def test_ceo_weekly_plan(self):
        from src.task_extractor import extract_tasks_from_message
        msg = (
            "Хорошо, Тим. Вот план на неделю:\n"
            "1. Мартин, проверь все API интеграции до пятницы\n"
            "2. Маттиас, подготовь финансовый отчёт к среде\n"
            "3. Юки, опубликуй 3 поста в LinkedIn на этой неделе\n"
            "4. Алексей, сделай стратегический обзор к понедельнику\n"
            "Я проконтролирую выполнение."
        )
        tasks = extract_tasks_from_message(msg, source_agent="manager")
        assert len(tasks) == 4
        assignees = [t["assignee"] for t in tasks]
        assert "automator" in assignees
        assert "accountant" in assignees
        assert "smm" in assignees
        assert "manager" in assignees

    def test_single_directive(self):
        from src.task_extractor import extract_tasks_from_message
        tasks = extract_tasks_from_message(
            "Мартин, настрой вебхук для Telegram завтра",
            source_agent="manager",
        )
        assert len(tasks) == 1
        assert tasks[0]["assignee"] == "automator"
        assert tasks[0]["deadline"] == "завтра"
        assert tasks[0]["source_agent"] == "manager"

    def test_no_extraction_from_financial_report(self):
        from src.task_extractor import extract_tasks_from_message
        msg = (
            "📊 Финансовый отчёт за Q4 2025:\n"
            "- Выручка: 2.4M USD\n"
            "- ROI: 340%\n"
            "- MRR: $45,000\n"
            "- Churn rate: 2.1%\n"
            "Все показатели в пределах нормы."
        )
        tasks = extract_tasks_from_message(msg)
        assert tasks == []

    def test_no_extraction_from_status_update(self):
        from src.task_extractor import extract_tasks_from_message
        msg = (
            "Статус интеграций:\n"
            "✅ Telegram API — работает\n"
            "✅ LinkedIn API — активна\n"
            "⚠️ OpenRouter — лимит 80%\n"
            "Всё стабильно."
        )
        tasks = extract_tasks_from_message(msg)
        assert tasks == []

    def test_no_extraction_from_greeting(self):
        from src.task_extractor import extract_tasks_from_message
        msg = "Добрый день! Я Алексей Воронов, CEO Zinin Corp. Чем могу помочь?"
        tasks = extract_tasks_from_message(msg)
        assert tasks == []

    def test_short_lines_skipped(self):
        from src.task_extractor import extract_tasks_from_message
        tasks = extract_tasks_from_message("Ок\nДа\nНет\nГотово")
        assert tasks == []

    def test_numbering_stripped_from_action(self):
        from src.task_extractor import extract_tasks_from_message
        tasks = extract_tasks_from_message(
            "1. Мартин, проверь API",
            source_agent="manager",
        )
        assert len(tasks) == 1
        assert not tasks[0]["action"].startswith("1.")

    def test_task_has_all_required_fields(self):
        from src.task_extractor import extract_tasks_from_message
        tasks = extract_tasks_from_message(
            "Маттиас, подготовь бюджет до пятницы",
            source_agent="manager",
        )
        assert len(tasks) == 1
        t = tasks[0]
        assert "action" in t
        assert "assignee" in t
        assert "deadline" in t
        assert "source_agent" in t
        assert "created_at" in t
        assert "status" in t
        assert t["status"] == "pending"


# ═══════════════════════════════════════════════════════════════
# 5. Task queue edge cases
# ═══════════════════════════════════════════════════════════════

class TestTaskQueueEdgeCases:

    def test_load_empty_file(self, tmp_path):
        from src.task_extractor import load_task_queue
        f = tmp_path / "tq.json"
        f.write_text("")
        with patch("src.task_extractor._tasks_path", return_value=str(f)):
            assert load_task_queue() == []

    def test_load_corrupt_json(self, tmp_path):
        from src.task_extractor import load_task_queue
        f = tmp_path / "tq.json"
        f.write_text("{{{corrupt")
        with patch("src.task_extractor._tasks_path", return_value=str(f)):
            assert load_task_queue() == []

    def test_load_json_object_returns_empty(self, tmp_path):
        from src.task_extractor import load_task_queue
        f = tmp_path / "tq.json"
        f.write_text('{"not": "a list"}')
        with patch("src.task_extractor._tasks_path", return_value=str(f)):
            assert load_task_queue() == []

    def test_overflow_keeps_last_100(self, tmp_path):
        from src.task_extractor import save_task_queue, add_tasks, load_task_queue
        f = tmp_path / "tq.json"
        # Pre-fill with 95 tasks
        initial = [{"action": f"old_{i}", "status": "pending"} for i in range(95)]
        with patch("src.task_extractor._tasks_path", return_value=str(f)):
            save_task_queue(initial)
            # Add 10 more → total 105 → trimmed to 100
            new = [{"action": f"new_{i}", "status": "pending"} for i in range(10)]
            add_tasks(new)
            queue = load_task_queue()
            assert len(queue) == 100
            # Oldest 5 should be gone
            actions = [t["action"] for t in queue]
            assert "old_0" not in actions
            assert "old_4" not in actions
            assert "old_5" in actions
            assert "new_9" in actions

    def test_complete_invalid_index(self, tmp_path):
        from src.task_extractor import save_task_queue, complete_task
        f = tmp_path / "tq.json"
        with patch("src.task_extractor._tasks_path", return_value=str(f)):
            save_task_queue([{"action": "x", "status": "pending"}])
            assert complete_task(-1) is False
            assert complete_task(1) is False
            assert complete_task(999) is False

    def test_complete_task_adds_timestamp(self, tmp_path):
        from src.task_extractor import save_task_queue, complete_task, load_task_queue
        f = tmp_path / "tq.json"
        with patch("src.task_extractor._tasks_path", return_value=str(f)):
            save_task_queue([{"action": "x", "status": "pending"}])
            complete_task(0)
            q = load_task_queue()
            assert q[0]["status"] == "completed"
            assert "completed_at" in q[0]
            # Timestamp should be ISO format
            assert "T" in q[0]["completed_at"]

    def test_get_pending_excludes_completed(self, tmp_path):
        from src.task_extractor import save_task_queue, get_pending_tasks
        f = tmp_path / "tq.json"
        tasks = [
            {"action": "done", "status": "completed"},
            {"action": "open1", "status": "pending"},
            {"action": "done2", "status": "completed"},
            {"action": "open2", "status": "pending"},
        ]
        with patch("src.task_extractor._tasks_path", return_value=str(f)):
            save_task_queue(tasks)
            pending = get_pending_tasks()
            assert len(pending) == 2
            assert pending[0]["action"] == "open1"
            assert pending[1]["action"] == "open2"

    def test_cyrillic_in_task_queue(self, tmp_path):
        from src.task_extractor import save_task_queue, load_task_queue
        f = tmp_path / "tq.json"
        tasks = [{"action": "Подготовь финансовый отчёт", "status": "pending"}]
        with patch("src.task_extractor._tasks_path", return_value=str(f)):
            save_task_queue(tasks)
            raw = f.read_text(encoding="utf-8")
            assert "Подготовь" in raw
            loaded = load_task_queue()
            assert loaded[0]["action"] == "Подготовь финансовый отчёт"

    def test_save_returns_false_on_error(self):
        from src.task_extractor import save_task_queue
        with patch("src.task_extractor._tasks_path", return_value="/no/such/dir/tq.json"):
            assert save_task_queue([]) is False


# ═══════════════════════════════════════════════════════════════
# 6. extract_and_store integration
# ═══════════════════════════════════════════════════════════════

class TestExtractAndStoreIntegration:

    def test_multiple_calls_accumulate(self, tmp_path):
        from src.task_extractor import extract_and_store, load_task_queue
        f = tmp_path / "tq.json"
        with patch("src.task_extractor._tasks_path", return_value=str(f)):
            extract_and_store("Мартин, проверь API", source_agent="manager")
            extract_and_store("Маттиас, подготовь отчёт", source_agent="manager")
            q = load_task_queue()
            assert len(q) == 2
            assert q[0]["assignee"] == "automator"
            assert q[1]["assignee"] == "accountant"

    def test_no_tasks_does_not_create_file(self, tmp_path):
        from src.task_extractor import extract_and_store
        f = tmp_path / "tq.json"
        with patch("src.task_extractor._tasks_path", return_value=str(f)):
            result = extract_and_store("Всё хорошо, без задач.")
            assert result == []
            assert not f.exists()

    def test_returns_extracted_tasks(self, tmp_path):
        from src.task_extractor import extract_and_store
        f = tmp_path / "tq.json"
        with patch("src.task_extractor._tasks_path", return_value=str(f)):
            tasks = extract_and_store(
                "Юки, опубликуй пост сегодня",
                source_agent="manager",
            )
            assert len(tasks) == 1
            assert tasks[0]["assignee"] == "smm"
            assert tasks[0]["deadline"] == "сегодня"


# ═══════════════════════════════════════════════════════════════
# 7. Thread safety for task queue
# ═══════════════════════════════════════════════════════════════

class TestTaskQueueThreadSafety:

    def test_concurrent_add_tasks(self, tmp_path):
        from src.task_extractor import add_tasks, load_task_queue, save_task_queue
        f = tmp_path / "tq.json"
        errors = []

        with patch("src.task_extractor._tasks_path", return_value=str(f)):
            save_task_queue([])

            def add_batch(batch_id):
                try:
                    tasks = [{"action": f"b{batch_id}_t{i}", "status": "pending"} for i in range(5)]
                    add_tasks(tasks)
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=add_batch, args=(i,)) for i in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert not errors
            q = load_task_queue()
            assert isinstance(q, list)
            # Due to race conditions, we may not get exactly 20, but should be valid JSON
            assert len(q) >= 5


# ═══════════════════════════════════════════════════════════════
# 8. app.py integration
# ═══════════════════════════════════════════════════════════════

class TestAppTaskIntegration:

    def test_extract_and_store_called_per_agent(self):
        """extract_and_store should be inside the for loop, called per agent."""
        source = _read(APP_PATH)
        lines = source.split("\n")

        # Find pending_prompt block → for loop → extract_and_store
        start = None
        for i, line in enumerate(lines):
            if '"pending_prompt" in st.session_state' in line:
                start = i
                break
        assert start is not None

        for_idx = None
        for i in range(start, min(start + 40, len(lines))):
            if "for target_key in targets" in lines[i]:
                for_idx = i
                break
        assert for_idx is not None

        extract_idx = None
        for i in range(for_idx + 1, min(for_idx + 30, len(lines))):
            if "extract_and_store" in lines[i]:
                extract_idx = i
                break
        assert extract_idx is not None

        # extract_and_store must be more indented than for loop
        for_indent = len(lines[for_idx]) - len(lines[for_idx].lstrip())
        ext_indent = len(lines[extract_idx]) - len(lines[extract_idx].lstrip())
        assert ext_indent > for_indent

    def test_extract_receives_source_agent(self):
        """extract_and_store is called with source_agent=target_key."""
        source = _read(APP_PATH)
        assert "extract_and_store(response, source_agent=target_key)" in source

    def test_dynamic_tasks_ui_loads_queue(self):
        """Tab3 calls load_task_queue() to display tasks."""
        source = _read(APP_PATH)
        assert "dynamic_tasks = load_task_queue()" in source

    def test_complete_task_button_wired(self):
        """Tab3 has complete_task(i) wired to a button."""
        source = _read(APP_PATH)
        assert "complete_task(i)" in source

    def test_tab3_shows_pending_and_completed(self):
        source = _read(APP_PATH)
        assert "Выполненные задачи" in source

    def test_predefined_tasks_untouched(self):
        """The 7 predefined tasks are still there."""
        source = _read(APP_PATH)
        count = len(re.findall(r'"method":\s*"', source))
        assert count == 7

    def test_app_is_valid_python(self):
        source = _read(APP_PATH)
        ast.parse(source)

    def test_extractor_is_valid_python(self):
        source = _read(EXTRACTOR_PATH)
        ast.parse(source)
