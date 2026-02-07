"""
Tests proving that task/action-item extraction from chat conversations
is completely missing in the AI Corporation codebase.

When agents discuss things in chat (e.g., CEO says "Martin, do X by Friday"),
no follow-up tasks are created, queued, or tracked. This test suite
demonstrates every gap in the pipeline:

1. No task extraction logic exists anywhere in the codebase.
2. The Tasks tab only has predefined quick-tasks, no dynamic creation.
3. Agent responses are saved to chat history but never parsed.
4. activity_tracker.py only logs events -- it never CREATES new tasks.
5. No mechanism connects chat conversations to any task system.
6. Delegation-style messages produce zero queued work items.

All tests use static code analysis, AST inspection, and mocking.
No API calls are made.
"""

import sys
import os
import ast
import inspect
import re
import json
import tempfile
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Paths to the source files under test
APP_PATH = os.path.join(os.path.dirname(__file__), "..", "app.py")
CREW_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "crew.py")
TRACKER_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "activity_tracker.py")
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
# 1. No task-extraction logic exists in the entire codebase
# ═══════════════════════════════════════════════════════════════

class TestNoTaskExtractionLogic:
    """Proves there is zero code that extracts action items from text."""

    EXTRACTION_KEYWORDS = [
        "extract_task",
        "extract_action",
        "parse_action",
        "action_item",
        "action_items",
        "find_tasks",
        "find_action",
        "detect_task",
        "detect_action",
        "create_action_item",
        "queue_task",
        "add_to_backlog",
        "todo_from",
        "followup",
        "follow_up_task",
    ]

    def test_no_extraction_functions_in_any_file(self):
        """No function in any .py file is named like an extraction routine
        (extract_task, parse_action, detect_action, etc.)."""
        sources = _all_py_sources()
        for path, source in sources.items():
            tree = ast.parse(source, filename=path)
            func_names = [
                node.name for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            for fn_name in func_names:
                fn_lower = fn_name.lower()
                for kw in self.EXTRACTION_KEYWORDS:
                    assert kw not in fn_lower, (
                        f"Found extraction-like function '{fn_name}' in {path}"
                    )

    def test_no_extraction_keywords_in_source_strings(self):
        """The keywords 'action_item', 'extract_task', 'todo_from', etc.
        do not appear as identifiers or string literals in any source file."""
        sources = _all_py_sources()
        for path, source in sources.items():
            source_lower = source.lower()
            for kw in self.EXTRACTION_KEYWORDS:
                assert kw not in source_lower, (
                    f"Keyword '{kw}' found in {path}"
                )

    def test_no_nlp_or_regex_task_parsing(self):
        """No file contains regex patterns that look for delegation phrases
        like 'сделай', 'подготовь ... до', 'deadline', etc. combined with
        a task-creation call."""
        delegation_patterns = [
            r"re\.\w+\(.*(сделай|подготовь|deadline|до пятницы|к понедельнику)",
            r"re\.\w+\(.*(assign|delegate|задач)",
        ]
        sources = _all_py_sources()
        for path, source in sources.items():
            for pattern in delegation_patterns:
                matches = re.findall(pattern, source, re.IGNORECASE)
                assert not matches, (
                    f"Delegation-parsing regex found in {path}: {matches}"
                )


# ═══════════════════════════════════════════════════════════════
# 2. Tasks tab contains ONLY predefined quick-tasks
# ═══════════════════════════════════════════════════════════════

class TestTasksTabIsStatic:
    """Proves the Tasks tab (tab3) in app.py has only a hardcoded list of
    quick-tasks with no mechanism for dynamically adding new ones."""

    def _app_source(self):
        return _read(APP_PATH)

    def test_tasks_list_is_hardcoded(self):
        """The 'tasks' variable in tab3 is a list literal -- not loaded from
        a database, file, or session state."""
        source = self._app_source()
        # Find the tasks = [ ... ] block inside 'with tab3:'
        # The list is assigned as a Python list literal directly in the source.
        assert "tasks = [" in source, "Expected hardcoded tasks list"
        # There should be no session_state-based dynamic task list
        assert "st.session_state.tasks" not in source
        assert "st.session_state[\"tasks\"]" not in source
        assert "st.session_state['tasks']" not in source
        assert "load_tasks(" not in source

    def test_exactly_seven_predefined_tasks(self):
        """There are exactly 7 predefined quick-tasks (strategic_review,
        financial_report, api_budget_check, subscription_analysis,
        system_health_check, integration_status, full_corporation_report)."""
        source = self._app_source()
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
            assert f'"method": "{method}"' in source or f"'method': '{method}'" in source, (
                f"Predefined task method '{method}' not found"
            )

        # Count the number of task dict definitions -- each has '"method": "xxx"'
        # (exclude references like task["method"] which are not definitions)
        method_def_count = len(re.findall(r'"method":\s*"', source))
        assert method_def_count == 7, (
            f"Expected exactly 7 predefined task methods, found {method_def_count}"
        )

    def test_no_add_task_ui_element(self):
        """No st.text_input, st.button, or st.form in tab3 allows the user
        to dynamically create a new task."""
        source = self._app_source()
        # Extract the tab3 block (between 'with tab3:' and the next 'with tab')
        tab3_match = re.search(
            r"with tab3:(.*?)(?:with tab\d:|$)", source, re.DOTALL
        )
        assert tab3_match, "Could not locate 'with tab3:' block"
        tab3_block = tab3_match.group(1)

        # Should NOT contain any "add task" form or input
        assert "add_task" not in tab3_block.lower()
        assert "new_task" not in tab3_block.lower()
        assert "create_task" not in tab3_block.lower()
        # No text_input for creating custom tasks
        assert 'st.text_input' not in tab3_block or 'task' not in tab3_block.lower().split('st.text_input')[0][-100:]

    def test_no_task_storage_or_database(self):
        """No file in the project stores dynamic tasks (no tasks.json,
        tasks.db, task_queue, backlog file, etc.)."""
        root = os.path.join(os.path.dirname(__file__), "..")
        task_file_patterns = [
            "tasks.json", "task_queue.json", "backlog.json",
            "tasks.db", "tasks.sqlite", "action_items.json",
        ]
        for dirpath, _, filenames in os.walk(root):
            if any(p.startswith(".") for p in dirpath.split(os.sep)):
                continue
            for fn in filenames:
                assert fn not in task_file_patterns, (
                    f"Dynamic task storage file '{fn}' found in {dirpath}"
                )


# ═══════════════════════════════════════════════════════════════
# 3. Agent responses saved to chat but never parsed for actions
# ═══════════════════════════════════════════════════════════════

class TestResponsesNotParsed:
    """Proves that after an agent responds, the response text is saved
    to chat history and nothing else happens -- no parsing, no task
    extraction, no follow-up scheduling."""

    def _app_source(self):
        return _read(APP_PATH)

    def test_response_appended_then_saved_no_parsing(self):
        """After 'response = corp.execute_task(...)' the code does exactly:
        1. Append message dict to st.session_state.messages
        2. Call save_chat_history()
        There is no intermediate step that inspects the response content."""
        source = self._app_source()

        # Find all response = corp.execute_task(...) calls
        # and verify the only things that follow are append + save
        lines = source.split("\n")
        for i, line in enumerate(lines):
            if "corp.execute_task(" in line and "response" in line:
                # Look at the next 20 lines for any parsing call
                window = "\n".join(lines[i:i+20])
                assert "extract" not in window.lower(), (
                    f"Found 'extract' near execute_task at line {i+1}"
                )
                assert "parse" not in window.lower() or "parse_mode" in window.lower(), (
                    f"Found 'parse' near execute_task at line {i+1}"
                )
                assert "action_item" not in window.lower(), (
                    f"Found 'action_item' near execute_task at line {i+1}"
                )

    def test_save_chat_history_has_no_task_extraction(self):
        """save_chat_history() delegates to chat_storage module.
        The storage module does pure persistence with no analysis or side-effects."""
        # Check app.py imports save_chat_history (does not define it)
        source = self._app_source()
        assert "from src.chat_storage import" in source
        assert "save_chat_history" in source

        # Check chat_storage.py save functions have no task-related calls
        storage_path = os.path.join(os.path.dirname(__file__), "..", "src", "chat_storage.py")
        storage_source = _read(storage_path)
        # Extract save_chat_history body
        func_match = re.search(
            r"def save_chat_history\(.*?\):\s*\n((?:[ \t]+.*\n)*)",
            storage_source,
        )
        assert func_match, "save_chat_history function not found in chat_storage.py"
        func_body = func_match.group(1)

        # Should NOT contain any task-related calls
        assert "extract" not in func_body.lower()
        assert "action_item" not in func_body.lower()
        assert "parse" not in func_body.lower()

    def test_format_chat_context_is_read_only(self):
        """format_chat_context() only reads messages to build a context string.
        It does not extract tasks, create action items, or modify state."""
        source = self._app_source()
        # Use AST to extract the function body source
        tree = ast.parse(source)
        func_node = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "format_chat_context":
                func_node = node
                break
        assert func_node is not None, "format_chat_context function not found"

        # Get the source lines of the function body
        lines = source.split("\n")
        body_start = func_node.body[0].lineno - 1  # 0-indexed
        body_end = func_node.end_lineno  # exclusive
        func_body = "\n".join(lines[body_start:body_end])

        # Pure read-only: builds lines, returns a joined string
        assert "return" in func_body
        assert "extract" not in func_body.lower()
        # Should not contain task-creation keywords (but "task" alone is fine
        # since the function is about formatting context, not creating tasks)
        assert "create_task" not in func_body.lower()
        assert "action_item" not in func_body.lower()

    def test_chat_flow_has_no_post_processing_hook(self):
        """Between receiving the agent response and calling st.rerun(),
        no callback, hook, or post-processing function is invoked to
        analyze the response. We check the specific chat processing block
        (pending_prompt handler) where responses are saved then rerun."""
        source = self._app_source()
        lines = source.split("\n")

        # Locate the pending_prompt processing block
        start_idx = None
        for i, line in enumerate(lines):
            if '"pending_prompt" in st.session_state' in line:
                start_idx = i
                break
        assert start_idx is not None, "pending_prompt block not found"

        # Find the st.rerun() that ends the block (within ~80 lines)
        end_idx = start_idx
        for i in range(start_idx, min(start_idx + 80, len(lines))):
            if "st.rerun()" in lines[i]:
                end_idx = i
                break

        # Extract only the lines between save_chat_history and st.rerun
        # within this specific block
        save_idx = None
        for i in range(start_idx, end_idx + 1):
            if "save_chat_history" in lines[i]:
                save_idx = i
                break
        assert save_idx is not None, "save_chat_history not found in pending_prompt block"

        between = "\n".join(lines[save_idx:end_idx + 1])
        between_lower = between.lower()

        # Only expect state cleanup (is_thinking = False), no analysis calls
        forbidden = ["parse_response", "create_task", "queue_task",
                     "action_item", "analyze_response", "process_response",
                     "extract_task", "extract_action"]
        for word in forbidden:
            assert word not in between_lower, (
                f"Post-processing keyword '{word}' found between save and rerun"
            )


# ═══════════════════════════════════════════════════════════════
# 4. activity_tracker.py only logs events, never creates tasks
# ═══════════════════════════════════════════════════════════════

class TestActivityTrackerIsEventLogOnly:
    """Proves that activity_tracker.py is purely an event logger.
    It records what happened (task_start, task_end, communication)
    but has no capability to CREATE, QUEUE, or SCHEDULE new tasks."""

    def test_tracker_event_types_are_only_logging(self):
        """The only event types are: task_start, task_end, communication.
        None of these represent *new* task creation."""
        source = _read(TRACKER_PATH)
        # Find all 'type' values in event dicts
        type_matches = re.findall(r'"type":\s*"(\w+)"', source)
        expected_types = {"task_start", "task_end", "communication"}
        actual_types = set(type_matches)
        assert actual_types == expected_types, (
            f"Expected event types {expected_types}, got {actual_types}"
        )

    def test_tracker_has_no_create_or_queue_functions(self):
        """activity_tracker.py exports no function that creates tasks,
        queues work, or schedules future actions."""
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
                assert word not in fn_lower, (
                    f"Tracker has task-creation function: {fn_name}"
                )

    def test_tracker_public_api_is_read_and_log_only(self):
        """All public functions in activity_tracker.py either log events
        (log_*) or query state (get_*). None modify a task queue."""
        from src.activity_tracker import (
            log_task_start,
            log_task_end,
            log_communication,
            log_communication_end,
            get_agent_status,
            get_all_statuses,
            get_recent_events,
            get_agent_task_count,
            get_task_progress,
        )
        public_funcs = [
            log_task_start, log_task_end, log_communication,
            log_communication_end, get_agent_status, get_all_statuses,
            get_recent_events, get_agent_task_count, get_task_progress,
        ]
        for func in public_funcs:
            name = func.__name__
            assert name.startswith("log_") or name.startswith("get_"), (
                f"Unexpected public function: {name}"
            )

    def test_log_task_start_does_not_create_actionable_task(self):
        """log_task_start() records that work BEGAN on something.
        It does not create a NEW task to be done in the future."""
        source = _read(TRACKER_PATH)
        # Use AST to reliably extract the full function body
        tree = ast.parse(source)
        func_node = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "log_task_start":
                func_node = node
                break
        assert func_node is not None, "log_task_start function not found"

        lines = source.split("\n")
        body_start = func_node.lineno - 1  # 0-indexed, include def line
        body_end = func_node.end_lineno
        body = "\n".join(lines[body_start:body_end])

        # It sets status to "working" and appends a "task_start" event
        assert '"working"' in body
        assert '"task_start"' in body
        # No notion of a future task queue
        assert "queue" not in body.lower()
        assert "pending" not in body.lower()
        assert "scheduled" not in body.lower()

    def test_data_schema_has_no_task_queue(self):
        """The activity log JSON schema has only 'events' and 'agent_status'.
        There is no 'task_queue', 'backlog', 'pending_tasks', etc."""
        source = _read(TRACKER_PATH)
        # The default empty structure
        assert '{"events": [], "agent_status": {}}' in source
        # No additional top-level keys
        assert "task_queue" not in source
        assert "pending_tasks" not in source
        assert "backlog" not in source
        assert "action_items" not in source


# ═══════════════════════════════════════════════════════════════
# 5. No mechanism connects chat to a task system
# ═══════════════════════════════════════════════════════════════

class TestNoChatToTaskPipeline:
    """Proves there is no pipeline that takes chat messages and feeds
    them into any task management system."""

    def test_crew_execute_task_returns_string_only(self):
        """AICorporation.execute_task() returns a plain string.
        It does not return structured data with action items."""
        source = _read(CREW_PATH)
        # Find all return statements in execute_task
        match = re.search(
            r"def execute_task\(self.*?\).*?(?=\n    def |\nclass |\Z)",
            source,
            re.DOTALL,
        )
        assert match, "execute_task method not found"
        method_body = match.group(0)
        # All returns are str() or string literals
        returns = re.findall(r"return\s+(.*)", method_body)
        for ret in returns:
            ret_stripped = ret.strip()
            # Each return is either str(result), a string literal, or f-string
            assert (
                ret_stripped.startswith("str(")
                or ret_stripped.startswith('"')
                or ret_stripped.startswith("f\"")
                or ret_stripped.startswith("f'")
                or ret_stripped.startswith("'")
            ), f"execute_task returns non-string: {ret_stripped}"

    def test_app_chat_flow_does_not_call_any_task_creator(self):
        """The chat message processing flow (lines ~914-973 in app.py)
        calls only: execute_task, append to messages, save_chat_history.
        No task-creation or task-queue function is invoked."""
        source = _read(APP_PATH)
        lines = source.split("\n")

        # Locate the pending_prompt processing block
        start_idx = None
        for i, line in enumerate(lines):
            if '"pending_prompt" in st.session_state' in line:
                start_idx = i
                break
        assert start_idx is not None, "pending_prompt block not found"

        # Grab the block up to st.rerun()
        end_idx = start_idx
        for i in range(start_idx, min(start_idx + 80, len(lines))):
            if "st.rerun()" in lines[i]:
                end_idx = i
                break

        block = "\n".join(lines[start_idx:end_idx + 1])
        block_lower = block.lower()

        # Verify ONLY these operations happen:
        assert "execute_task" in block  # agent is called
        assert "messages.append" in block  # response is saved to chat
        assert "save_chat_history" in block  # chat persisted to disk

        # Verify NONE of these happen:
        missing_calls = [
            "create_task", "add_task", "queue_task", "schedule_task",
            "extract_action", "parse_task", "action_item",
            "task_queue", "backlog", "todo",
        ]
        for call in missing_calls:
            assert call not in block_lower, (
                f"Unexpected task-creation call '{call}' found in chat flow"
            )

    def test_no_import_of_task_manager_or_queue(self):
        """app.py does not import any task management module, queue,
        or action-item extractor."""
        source = _read(APP_PATH)
        tree = ast.parse(source)
        imported_names = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.add(alias.name.lower())
            elif isinstance(node, ast.ImportFrom):
                module = (node.module or "").lower()
                imported_names.add(module)
                for alias in node.names:
                    imported_names.add(alias.name.lower())

        task_modules = [
            "task_manager", "task_queue", "action_items",
            "task_extractor", "task_parser", "backlog",
            "celery", "rq", "dramatiq", "huey",
        ]
        for mod in task_modules:
            assert mod not in imported_names, (
                f"app.py imports task management module: {mod}"
            )

    def test_crew_module_has_no_task_queue_class(self):
        """src/crew.py defines AICorporation but no TaskQueue, ActionItem,
        Backlog, or similar class."""
        source = _read(CREW_PATH)
        tree = ast.parse(source)
        class_names = [
            node.name for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
        ]
        queue_classes = ["TaskQueue", "ActionItem", "Backlog", "TodoList",
                         "TaskManager", "PendingTask", "DynamicTask"]
        for cls_name in class_names:
            assert cls_name not in queue_classes, (
                f"Found task-queue class '{cls_name}' in crew.py"
            )


# ═══════════════════════════════════════════════════════════════
# 6. Delegation messages produce zero queued work items
# ═══════════════════════════════════════════════════════════════

class TestDelegationMessagesIgnored:
    """Simulates realistic delegation-style messages from the CEO and
    proves that no task is created, queued, or tracked as a result."""

    DELEGATION_MESSAGES = [
        "Мартин, сделай аудит API до пятницы",
        "Маттиас, подготовь финансовый отчёт к понедельнику",
        "Юки, опубликуй пост в LinkedIn сегодня",
        "Всем: подготовить отчёты к совещанию в 15:00",
        "@Мартин проверь интеграцию с Telegram до конца дня",
        "Алексей, поручи Маттиасу проверить бюджет",
    ]

    def test_detect_agents_returns_agent_key_not_task(self):
        """detect_agents() identifies WHICH agent is being addressed,
        but returns only agent keys -- no task data, no deadline, no
        action description."""
        # We need to mock streamlit session state for detect_agents
        mock_session = MagicMock()
        mock_session.get.return_value = "manager"

        with patch.dict("sys.modules", {"streamlit": MagicMock()}):
            source = _read(APP_PATH)

        # Parse the detect_agents function to verify its return type
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "detect_agents":
                # Check return annotations: should be list[str]
                returns = [
                    n for n in ast.walk(node)
                    if isinstance(n, ast.Return)
                ]
                # All return values are lists of agent keys (strings)
                # No Return contains a dict, tuple with task info, etc.
                for ret in returns:
                    if ret.value is None:
                        continue
                    # Return should not construct a dict or NamedTuple
                    assert not isinstance(ret.value, ast.Dict), (
                        "detect_agents returns a dict (would indicate task data)"
                    )
                break

    def test_no_deadline_parsing_anywhere(self):
        """No code in the project parses date/deadline expressions from
        natural language ('до пятницы', 'к понедельнику', 'today', etc.)."""
        deadline_patterns = [
            r"до\s+(пятниц|понедельник|вторник|сред|четверг|суббот|воскресен)",
            r"к\s+(понедельник|вторник|сред|четверг|пятниц|суббот|воскресен)",
            r"dateparser|dateutil\.parser|parse_date|parse_deadline",
        ]
        sources = _all_py_sources()
        for path, source in sources.items():
            for pattern in deadline_patterns:
                matches = re.findall(pattern, source, re.IGNORECASE)
                assert not matches, (
                    f"Deadline parsing pattern found in {path}: {matches}"
                )

    def test_message_content_not_analyzed_after_send(self):
        """After a user sends a delegation message, the system only:
        1. Detects the target agent(s)
        2. Passes the raw text to execute_task
        3. Appends the response to chat
        It does NOT analyze the user's message for embedded tasks."""
        source = _read(APP_PATH)
        lines = source.split("\n")

        # Find where user input is processed (the chat_input handler)
        input_block_start = None
        for i, line in enumerate(lines):
            if "st.chat_input" in line:
                input_block_start = i
                break

        if input_block_start:
            # Look at the 30 lines after chat_input
            block = "\n".join(lines[input_block_start:input_block_start + 30])
            block_lower = block.lower()
            # The only processing should be detect_agents + setting pending_prompt
            assert "detect_agent" in block_lower or "pending" in block_lower
            # No task extraction
            assert "extract" not in block_lower
            assert "action_item" not in block_lower
            assert "create_task" not in block_lower

    def test_simulated_delegation_produces_no_side_effects(self):
        """Simulate the complete flow: user sends a delegation message,
        agent responds, response is saved. Verify that at no point is
        a task object or queue entry created.

        We trace all calls to activity_tracker functions and verify only
        log_task_start and log_task_end are called -- no task creation."""
        from src.activity_tracker import (
            log_task_start,
            log_task_end,
            log_communication,
        )

        # Create a temp activity log
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        tmp.write('{"events": [], "agent_status": {}}')
        tmp.close()

        try:
            with patch("src.activity_tracker._log_path", return_value=tmp.name):
                # Simulate what execute_task does:
                # 1. log_task_start
                log_task_start("automator", "Мартин, сделай аудит API до пятницы")
                # 2. (agent runs and returns text -- we skip the actual LLM call)
                # 3. log_task_end
                log_task_end("automator", "Мартин, сделай аудит API до пятницы", success=True)

                # Read back the log
                with open(tmp.name, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Only events: task_start, task_end. No "task_created" or "task_queued"
                event_types = {e["type"] for e in data["events"]}
                assert event_types == {"task_start", "task_end"}, (
                    f"Expected only logging events, got: {event_types}"
                )

                # The agent's status is idle -- nothing was queued
                agent_status = data["agent_status"]["automator"]
                assert agent_status["status"] == "idle"
                assert "queue" not in json.dumps(data).lower()
                assert "pending" not in json.dumps(data).lower()
                assert "action_item" not in json.dumps(data).lower()
        finally:
            os.unlink(tmp.name)

    def test_ceo_delegation_to_agent_not_tracked_as_new_task(self):
        """When the CEO agent says 'Мартин, подготовь отчёт к пятнице'
        in its response text, that response is stored as a chat message
        string -- the delegation instruction is never parsed into a
        separate actionable task for Мартин."""
        # Simulate CEO response containing a delegation
        ceo_response = (
            "Хорошо, Тим. Вот мой план на неделю:\n"
            "1. Мартин, подготовь аудит API расходов до пятницы\n"
            "2. Маттиас, обнови финансовый отчёт к среде\n"
            "3. Юки, опубликуй 3 поста в LinkedIn на этой неделе\n"
            "Я проконтролирую выполнение."
        )

        # This is how app.py stores the response (lines 952-959)
        message = {
            "role": "assistant",
            "content": ceo_response,
            "agent_key": "manager",
            "agent_name": "Алексей",
            "time": "14:30",
            "date": "07.02.2026",
        }

        # The message dict has NO task-related keys
        assert "tasks" not in message
        assert "action_items" not in message
        assert "delegations" not in message
        assert "assignments" not in message

        # The message is a flat dict with only chat display fields
        expected_keys = {"role", "content", "agent_key", "agent_name", "time", "date"}
        assert set(message.keys()) == expected_keys

    def test_no_inter_agent_task_delegation_mechanism(self):
        """AICorporation has no method to delegate a task from one agent
        to another based on chat content. The only inter-agent mechanism
        is context passing in predefined multi-agent tasks (strategic_review,
        full_corporation_report)."""
        source = _read(CREW_PATH)
        tree = ast.parse(source)

        # Get all method names of AICorporation
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
            assert method not in method_names, (
                f"AICorporation has delegation method: {method}"
            )
