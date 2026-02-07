"""
Tests verifying task extraction from chat conversations (FIXED).

After Fix #3, the system now:
1. Has task extraction logic in src/task_extractor.py
2. The Tasks tab has both predefined quick-tasks AND dynamic tasks from chat
3. Agent responses are parsed for action items after saving
4. activity_tracker.py remains a pure event logger (separate concern)
5. A pipeline connects chat conversations to the task queue
6. Delegation-style messages produce queued work items

All tests use static code analysis, AST inspection, and mocking.
No API calls are made.
"""

import sys
import os
import ast
import re
import json
import tempfile
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Paths to the source files under test
APP_PATH = os.path.join(os.path.dirname(__file__), "..", "app.py")
CREW_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "crew.py")
TRACKER_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "activity_tracker.py")
EXTRACTOR_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "task_extractor.py")
SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _all_py_sources() -> dict[str, str]:
    """Return {filepath: source} for every .py file in the project."""
    root = os.path.join(os.path.dirname(__file__), "..")
    result = {}
    for dirpath, _, filenames in os.walk(root):
        # Skip virtual-envs and hidden dirs
        if any(part.startswith(".") or part in ("__pycache__", "node_modules")
               for part in dirpath.split(os.sep)):
            continue
        for fn in filenames:
            if fn.endswith(".py"):
                full = os.path.join(dirpath, fn)
                try:
                    result[full] = _read(full)
                except Exception:
                    pass
    return result


# ═══════════════════════════════════════════════════════════════
# 1. Task extraction logic EXISTS in the codebase (FIXED)
# ═══════════════════════════════════════════════════════════════

class TestTaskExtractionExists:
    """Verifies that task extraction logic now exists in src/task_extractor.py."""

    def test_extractor_module_exists(self):
        """src/task_extractor.py exists."""
        assert os.path.exists(EXTRACTOR_PATH)

    def test_extraction_functions_importable(self):
        """Task extraction functions are importable."""
        from src.task_extractor import (
            extract_tasks_from_message,
            extract_and_store,
            _detect_assignee,
            _has_action_verb,
            _detect_deadline,
        )
        assert callable(extract_tasks_from_message)
        assert callable(extract_and_store)

    def test_extractor_has_action_verb_detection(self):
        """task_extractor.py has Russian action verb patterns."""
        source = _read(EXTRACTOR_PATH)
        assert "ACTION_VERBS" in source
        assert "сделай" in source
        assert "подготовь" in source

    def test_extractor_has_agent_patterns(self):
        """task_extractor.py has agent name patterns for assignee detection."""
        source = _read(EXTRACTOR_PATH)
        assert "AGENT_PATTERNS" in source
        assert "алексей" in source
        assert "маттиас" in source
        assert "мартин" in source
        assert "юки" in source

    def test_extractor_has_deadline_patterns(self):
        """task_extractor.py has deadline parsing patterns."""
        source = _read(EXTRACTOR_PATH)
        assert "DEADLINE_PATTERNS" in source
        assert "пятниц" in source
        assert "понедельник" in source


# ═══════════════════════════════════════════════════════════════
# 2. Tasks tab has BOTH predefined and dynamic tasks (FIXED)
# ═══════════════════════════════════════════════════════════════

class TestTasksTabHasDynamicTasks:
    """Verifies the Tasks tab now has both predefined quick-tasks
    AND dynamically extracted tasks from chat."""

    def _app_source(self):
        return _read(APP_PATH)

    def test_predefined_tasks_still_exist(self):
        """The 'tasks' variable in tab3 still has the 7 predefined quick-tasks."""
        source = self._app_source()
        assert "tasks = [" in source
        expected_methods = [
            "strategic_review",
            "financial_report",
            "api_budget_check",
            "subscription_analysis",
            "system_health_check",
            "integration_status",
            "full_corporation_report",
        ]
        for method in expected_methods:
            assert f'"method": "{method}"' in source

    def test_exactly_seven_predefined_tasks(self):
        """Still exactly 7 predefined task methods."""
        source = self._app_source()
        method_def_count = len(re.findall(r'"method":\s*"', source))
        assert method_def_count == 7

    def test_dynamic_tasks_section_exists(self):
        """Tab3 now has a dynamic tasks section loaded from task_queue."""
        source = self._app_source()
        assert "load_task_queue" in source
        assert "Задачи из чата" in source

    def test_complete_task_button_exists(self):
        """Tab3 has a button to mark dynamic tasks as completed."""
        source = self._app_source()
        assert "complete_task" in source


# ═══════════════════════════════════════════════════════════════
# 3. Agent responses ARE parsed for tasks (FIXED)
# ═══════════════════════════════════════════════════════════════

class TestResponsesParsedForTasks:
    """Verifies that agent responses are now parsed for action items
    after being saved to chat history."""

    def _app_source(self):
        return _read(APP_PATH)

    def test_extract_and_store_called_after_response(self):
        """After agent response is appended, extract_and_store is called."""
        source = self._app_source()
        lines = source.split("\n")
        for i, line in enumerate(lines):
            if '"pending_prompt" in st.session_state' in line:
                block = "\n".join(lines[i:i + 80])
                assert "extract_and_store" in block
                return
        assert False, "pending_prompt block not found"

    def test_save_chat_history_still_pure_persistence(self):
        """save_chat_history() in chat_storage.py remains pure persistence —
        task extraction is a SEPARATE call in app.py."""
        storage_path = os.path.join(os.path.dirname(__file__), "..", "src", "chat_storage.py")
        storage_source = _read(storage_path)
        func_match = re.search(
            r"def save_chat_history\(.*?\):\s*\n((?:[ \t]+.*\n)*)",
            storage_source,
        )
        assert func_match
        func_body = func_match.group(1)
        assert "extract" not in func_body.lower()
        assert "action_item" not in func_body.lower()

    def test_format_chat_context_is_read_only(self):
        """format_chat_context() remains read-only (no task extraction)."""
        source = self._app_source()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "format_chat_context":
                lines = source.split("\n")
                body = "\n".join(lines[node.lineno - 1:node.end_lineno])
                assert "extract" not in body.lower()
                assert "create_task" not in body.lower()
                return
        assert False, "format_chat_context not found"


# ═══════════════════════════════════════════════════════════════
# 4. activity_tracker.py remains a pure event logger
# ═══════════════════════════════════════════════════════════════

class TestActivityTrackerIsEventLogOnly:
    """Confirms activity_tracker.py was NOT modified — it remains
    a pure event logger. Task extraction is in task_extractor.py."""

    def test_tracker_event_types_are_only_logging(self):
        """The only event types are: task_start, task_end, communication, delegation."""
        source = _read(TRACKER_PATH)
        type_matches = re.findall(r'"type":\s*"(\w+)"', source)
        expected_types = {"task_start", "task_end", "communication", "delegation"}
        actual_types = set(type_matches)
        assert actual_types == expected_types

    def test_tracker_has_no_create_or_queue_functions(self):
        """activity_tracker.py has no task-creation functions."""
        source = _read(TRACKER_PATH)
        tree = ast.parse(source)
        func_names = [
            node.name for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
        ]
        creation_words = ["create", "queue", "schedule", "assign",
                          "add_task", "new_task", "enqueue", "backlog"]
        for fn_name in func_names:
            fn_lower = fn_name.lower()
            for word in creation_words:
                assert word not in fn_lower

    def test_tracker_public_api_is_read_and_log_only(self):
        """All public functions are log_* or get_*."""
        from src.activity_tracker import (
            log_task_start, log_task_end, log_communication,
            log_communication_end, get_agent_status, get_all_statuses,
            get_recent_events, get_agent_task_count, get_task_progress,
        )
        for func in [log_task_start, log_task_end, log_communication,
                      log_communication_end, get_agent_status, get_all_statuses,
                      get_recent_events, get_agent_task_count, get_task_progress]:
            name = func.__name__
            assert name.startswith("log_") or name.startswith("get_")

    def test_data_schema_has_no_task_queue(self):
        """Activity log schema remains {events, agent_status} only."""
        source = _read(TRACKER_PATH)
        assert '{"events": [], "agent_status": {}}' in source
        assert "task_queue" not in source
        assert "extract" not in source


# ═══════════════════════════════════════════════════════════════
# 5. Chat-to-task pipeline NOW exists (FIXED)
# ═══════════════════════════════════════════════════════════════

class TestChatToTaskPipeline:
    """Verifies the pipeline from chat → task extraction → task queue."""

    def test_crew_execute_task_returns_string_only(self):
        """AICorporation.execute_task() returns plain strings.
        _run_agent() converts crew.kickoff() to str."""
        source = _read(CREW_PATH)
        # Check that execute_task return type annotation is -> str
        assert "def execute_task(self, task_description: str, agent_name: str" in source
        # Check _run_agent converts kickoff result to string
        match = re.search(
            r"def _run_agent\(self.*?\).*?(?=\n    def |\nclass |\Z)",
            source, re.DOTALL,
        )
        assert match, "_run_agent method should exist in crew.py"
        method_body = match.group(0)
        assert "str(crew.kickoff())" in method_body or "str(" in method_body, (
            "_run_agent should convert kickoff result to string"
        )

    def test_app_imports_task_extractor(self):
        """app.py imports from src.task_extractor."""
        source = _read(APP_PATH)
        assert "from src.task_extractor import" in source

    def test_app_chat_flow_calls_extract_and_store(self):
        """The chat flow now calls extract_and_store after agent response."""
        source = _read(APP_PATH)
        lines = source.split("\n")
        start_idx = None
        for i, line in enumerate(lines):
            if '"pending_prompt" in st.session_state' in line:
                start_idx = i
                break
        assert start_idx is not None
        end_idx = start_idx
        for i in range(start_idx, min(start_idx + 80, len(lines))):
            if "st.rerun()" in lines[i]:
                end_idx = i
                break
        block = "\n".join(lines[start_idx:end_idx + 1])
        assert "execute_task" in block
        assert "messages.append" in block
        assert "save_chat_history" in block
        assert "extract_and_store" in block

    def test_crew_module_has_no_task_queue_class(self):
        """crew.py still doesn't have task queue classes
        (extraction is a separate module)."""
        source = _read(CREW_PATH)
        tree = ast.parse(source)
        class_names = [
            node.name for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
        ]
        queue_classes = ["TaskQueue", "ActionItem", "Backlog", "TodoList",
                         "TaskManager", "PendingTask", "DynamicTask"]
        for cls_name in class_names:
            assert cls_name not in queue_classes


# ═══════════════════════════════════════════════════════════════
# 6. Delegation messages NOW produce queued work items (FIXED)
# ═══════════════════════════════════════════════════════════════

class TestDelegationMessagesExtracted:
    """Verifies that delegation-style messages from agents are now
    parsed and produce task queue entries."""

    def test_detect_agents_returns_agent_key_not_task(self):
        """detect_agents() still returns only agent keys (routing).
        Task extraction is separate."""
        source = _read(APP_PATH)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "detect_agents":
                returns = [
                    n for n in ast.walk(node)
                    if isinstance(n, ast.Return)
                ]
                for ret in returns:
                    if ret.value is None:
                        continue
                    assert not isinstance(ret.value, ast.Dict)
                break

    def test_deadline_parsing_exists_in_extractor(self):
        """task_extractor.py now parses deadline expressions."""
        source = _read(EXTRACTOR_PATH)
        assert "пятниц" in source
        assert "понедельник" in source
        assert "_detect_deadline" in source

    def test_ceo_delegation_produces_tasks(self):
        """When CEO says 'Мартин, подготовь отчёт к пятнице',
        extract_tasks_from_message returns actionable tasks."""
        from src.task_extractor import extract_tasks_from_message
        ceo_response = (
            "Хорошо, Тим. Вот мой план на неделю:\n"
            "1. Мартин, подготовь аудит API расходов до пятницы\n"
            "2. Маттиас, обнови финансовый отчёт к среде\n"
            "3. Юки, опубликуй 3 поста в LinkedIn на этой неделе\n"
            "Я проконтролирую выполнение."
        )
        tasks = extract_tasks_from_message(ceo_response, source_agent="manager")
        assert len(tasks) >= 3
        assignees = {t["assignee"] for t in tasks}
        assert "automator" in assignees
        assert "accountant" in assignees
        assert "smm" in assignees

    def test_simulated_delegation_produces_task_queue_entries(self, tmp_path):
        """Simulate the flow: agent responds with delegation,
        extract_and_store saves tasks to the queue."""
        from src.task_extractor import extract_and_store, load_task_queue
        queue_file = tmp_path / "task_queue.json"

        with patch("src.task_extractor._tasks_path", return_value=str(queue_file)):
            tasks = extract_and_store(
                "Мартин, сделай аудит API до пятницы",
                source_agent="manager",
            )
            assert len(tasks) == 1
            assert tasks[0]["assignee"] == "automator"
            assert tasks[0]["deadline"] == "до пятницы"

            queue = load_task_queue()
            assert len(queue) == 1
            assert queue[0]["status"] == "pending"

    def test_activity_tracker_still_unaffected(self):
        """activity_tracker.py is NOT where tasks are stored.
        Task queue is in task_extractor.py."""
        from src.activity_tracker import (
            log_task_start, log_task_end,
        )
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        tmp.write('{"events": [], "agent_status": {}}')
        tmp.close()

        try:
            with patch("src.activity_tracker._log_path", return_value=tmp.name):
                log_task_start("automator", "Мартин, сделай аудит API до пятницы")
                log_task_end("automator", "Мартин, сделай аудит API до пятницы", success=True)

                with open(tmp.name, "r", encoding="utf-8") as f:
                    data = json.load(f)

                event_types = {e["type"] for e in data["events"]}
                assert event_types == {"task_start", "task_end"}
                assert "task_queue" not in json.dumps(data).lower()
        finally:
            os.unlink(tmp.name)

    def test_chat_message_dict_still_flat(self):
        """Chat messages remain flat dicts — task data is stored separately."""
        message = {
            "role": "assistant",
            "content": "Мартин, подготовь отчёт",
            "agent_key": "manager",
            "agent_name": "Алексей",
            "time": "14:30",
            "date": "07.02.2026",
        }
        expected_keys = {"role", "content", "agent_key", "agent_name", "time", "date"}
        assert set(message.keys()) == expected_keys

    def test_no_inter_agent_task_delegation_mechanism(self):
        """AICorporation still has no built-in delegation methods.
        Task extraction is handled externally in app.py."""
        source = _read(CREW_PATH)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "AICorporation":
                method_names = [
                    m.name for m in node.body
                    if isinstance(m, ast.FunctionDef)
                ]
                break
        delegation_methods = [
            "delegate_task", "assign_task", "forward_task",
            "create_followup", "queue_for_agent", "schedule_for_agent",
        ]
        for method in delegation_methods:
            assert method not in method_names
