"""
🧪 Tests for Fix #1: Agent inter-communication in broadcast loop

Verifies:
1. Context is re-computed inside the loop (each agent sees previous responses)
2. Truncation increased from 300→800 chars
3. Max messages increased from 10→20
4. Existing behavior is not broken
"""

import ast
import os
import sys
import re
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

APP_PATH = os.path.join(os.path.dirname(__file__), "..", "app.py")


def _read_app_source():
    with open(APP_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _extract_function(source, func_name):
    """Extract a function from source using AST."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            return ast.get_source_segment(source, node)
    return None


def _make_format_chat_context():
    """Extract and compile format_chat_context from app.py without Streamlit."""
    source = _read_app_source()
    func_src = _extract_function(source, "format_chat_context")
    assert func_src is not None, "format_chat_context not found"
    ns = {}
    exec(func_src, ns)
    return ns["format_chat_context"]


# ──────────────────────────────────────────────────────────
# 1. Context is re-computed inside the loop
# ──────────────────────────────────────────────────────────

class TestContextRecomputedInsideLoop:
    """Verify that format_chat_context is called inside the for loop, not before it."""

    def test_context_computed_inside_for_loop(self):
        """format_chat_context must be called INSIDE the 'for target_key in targets' loop."""
        source = _read_app_source()
        # Find the pending_prompt block
        lines = source.split("\n")
        in_pending_block = False
        for_loop_line = None
        context_line = None
        for i, line in enumerate(lines):
            stripped = line.strip()
            if '"pending_prompt" in st.session_state' in stripped:
                in_pending_block = True
            if in_pending_block and "for target_key in targets:" in stripped:
                for_loop_line = i
            if in_pending_block and for_loop_line is not None:
                if "format_chat_context" in stripped:
                    context_line = i
                    break
        assert for_loop_line is not None, "for loop not found"
        assert context_line is not None, "format_chat_context call not found after loop"
        assert context_line > for_loop_line, \
            f"format_chat_context (line {context_line}) must be AFTER for loop (line {for_loop_line})"

    def test_no_context_computation_before_loop(self):
        """No format_chat_context call between 'corp.is_ready' and 'for target_key'."""
        source = _read_app_source()
        lines = source.split("\n")
        in_pending_block = False
        is_ready_line = None
        for_loop_line = None
        for i, line in enumerate(lines):
            stripped = line.strip()
            if '"pending_prompt" in st.session_state' in stripped:
                in_pending_block = True
            if in_pending_block and "corp.is_ready" in stripped:
                is_ready_line = i
            if in_pending_block and "for target_key in targets:" in stripped:
                for_loop_line = i
                break

        assert is_ready_line is not None
        assert for_loop_line is not None
        # Check no format_chat_context between is_ready and for loop
        between = lines[is_ready_line:for_loop_line]
        for line in between:
            assert "format_chat_context" not in line, \
                "format_chat_context should NOT be called before the for loop"

    def test_broadcast_gives_different_context_to_subsequent_agents(self):
        """Simulate broadcast: agent #2 should see agent #1's response in context."""
        format_ctx = _make_format_chat_context()

        messages = [
            {"role": "user", "content": "Привет всем"},
        ]

        # Simulate agent #1 (Алексей) responding
        context_for_agent1 = format_ctx(messages)
        # Agent 1 gets no previous assistant messages (only user message)

        # Agent 1 responds
        messages.append({
            "role": "assistant",
            "content": "Добрый день! Я подготовил стратегический обзор.",
            "agent_name": "Алексей",
        })

        # Re-compute context for agent #2
        context_for_agent2 = format_ctx(messages)
        assert "Алексей: Добрый день" in context_for_agent2, \
            "Agent #2 must see Agent #1's response"
        assert "стратегический обзор" in context_for_agent2

    def test_three_agent_chain_each_sees_previous(self):
        """In a 3-agent broadcast, agent #3 sees both #1 and #2 responses."""
        format_ctx = _make_format_chat_context()

        messages = [{"role": "user", "content": "Отчёт от каждого"}]

        # Agent 1 responds
        messages.append({
            "role": "assistant",
            "content": "Финансовые показатели: MRR $500, расходы $200",
            "agent_name": "Маттиас",
        })

        # Agent 2 gets context with agent 1
        ctx2 = format_ctx(messages)
        assert "Маттиас" in ctx2
        assert "MRR" in ctx2

        # Agent 2 responds
        messages.append({
            "role": "assistant",
            "content": "Все системы работают стабильно, uptime 99.9%",
            "agent_name": "Мартин",
        })

        # Agent 3 gets context with both agent 1 and 2
        ctx3 = format_ctx(messages)
        assert "Маттиас" in ctx3
        assert "MRR" in ctx3
        assert "Мартин" in ctx3
        assert "uptime" in ctx3


# ──────────────────────────────────────────────────────────
# 2. Truncation increased to 800 chars
# ──────────────────────────────────────────────────────────

class TestTruncationIncreased:
    """Verify truncation limit is now 800 chars instead of 300."""

    def test_truncation_is_800(self):
        """format_chat_context uses [:800] for assistant messages."""
        source = _read_app_source()
        func = _extract_function(source, "format_chat_context")
        assert func is not None
        assert "[:800]" in func, f"Expected [:800] truncation, got: {func}"

    def test_no_300_truncation(self):
        """The old 300-char truncation should be gone."""
        source = _read_app_source()
        func = _extract_function(source, "format_chat_context")
        assert "[:300]" not in func

    def test_800_char_message_preserved(self):
        """An 800-char message is fully preserved in context."""
        format_ctx = _make_format_chat_context()
        long_msg = "A" * 800
        messages = [
            {"role": "user", "content": "test"},
            {"role": "assistant", "content": long_msg, "agent_name": "Алексей"},
        ]
        ctx = format_ctx(messages)
        assert long_msg in ctx

    def test_900_char_message_truncated_to_800(self):
        """A 900-char message is truncated to 800 chars."""
        format_ctx = _make_format_chat_context()
        long_msg = "B" * 900
        messages = [
            {"role": "user", "content": "test"},
            {"role": "assistant", "content": long_msg, "agent_name": "Алексей"},
        ]
        ctx = format_ctx(messages)
        # The context should contain exactly 800 B's
        assert "B" * 800 in ctx
        assert "B" * 801 not in ctx

    def test_realistic_report_preserved(self):
        """A realistic 600-char financial report is fully preserved."""
        format_ctx = _make_format_chat_context()
        report = (
            "Финансовая сводка Zinin Corp:\n"
            "1. MRR: $500 (рост 15% за месяц)\n"
            "2. Расходы на API: $45.20 (OpenRouter)\n"
            "3. Подписки: Railway $5, GitHub Pro $4\n"
            "4. P&L: +$445.80 чистая прибыль\n"
            "5. ROI маркетинга: 320% за последний квартал\n"
            "6. Прогноз: выход на $1000 MRR через 2 месяца при текущем росте\n"
            "Рекомендация: увеличить бюджет на контент-маркетинг."
        )
        assert len(report) < 800
        messages = [
            {"role": "user", "content": "Финансовый отчёт"},
            {"role": "assistant", "content": report, "agent_name": "Маттиас"},
        ]
        ctx = format_ctx(messages)
        assert "ROI" in ctx
        assert "Рекомендация" in ctx
        assert "$1000 MRR" in ctx


# ──────────────────────────────────────────────────────────
# 3. Max messages increased to 20
# ──────────────────────────────────────────────────────────

class TestMaxMessagesIncreased:
    """Verify max_messages default is now 20."""

    def test_default_max_messages_is_20(self):
        """format_chat_context default parameter is max_messages=20."""
        source = _read_app_source()
        func = _extract_function(source, "format_chat_context")
        assert "max_messages: int = 20" in func or "max_messages=20" in func

    def test_15_messages_all_included(self):
        """15 messages in history should all appear in context (was lost with limit 10)."""
        format_ctx = _make_format_chat_context()
        messages = []
        for i in range(15):
            messages.append({"role": "user", "content": f"Сообщение #{i+1}"})
            messages.append({
                "role": "assistant",
                "content": f"Ответ #{i+1}",
                "agent_name": "Алексей",
            })
        # Add current message (excluded from context)
        messages.append({"role": "user", "content": "Текущее"})
        ctx = format_ctx(messages)
        # With max_messages=20, we should see the last 20 messages (messages[-21:-1])
        # That covers messages 11-30 (0-indexed: 10-29) out of 31 total
        # We should see at least messages #11-#15
        for i in range(11, 16):
            assert f"#{i}" in ctx, f"Message #{i} should be in context"

    def test_old_limit_10_is_gone(self):
        """The old max_messages=10 default should not be in the signature."""
        source = _read_app_source()
        func = _extract_function(source, "format_chat_context")
        assert "max_messages: int = 10" not in func


# ──────────────────────────────────────────────────────────
# 4. Regression: existing behavior preserved
# ──────────────────────────────────────────────────────────

class TestRegressionExistingBehavior:
    """Verify nothing is broken by the changes."""

    def test_empty_messages_returns_empty_string(self):
        """Empty messages list returns empty context."""
        format_ctx = _make_format_chat_context()
        assert format_ctx([]) == ""

    def test_single_user_message_included_in_context(self):
        """Single user message is now included in context (visible to agents)."""
        format_ctx = _make_format_chat_context()
        messages = [{"role": "user", "content": "Hello"}]
        ctx = format_ctx(messages)
        assert "Тим: Hello" in ctx

    def test_user_messages_not_truncated(self):
        """User messages are still not truncated."""
        format_ctx = _make_format_chat_context()
        long_user_msg = "X" * 2000
        messages = [
            {"role": "user", "content": long_user_msg},
            {"role": "user", "content": "Current"},
        ]
        ctx = format_ctx(messages)
        assert "X" * 2000 in ctx

    def test_context_header_present(self):
        """Context still starts with the expected header."""
        format_ctx = _make_format_chat_context()
        messages = [
            {"role": "user", "content": "Привет"},
            {"role": "assistant", "content": "Добрый день", "agent_name": "Алексей"},
            {"role": "user", "content": "Текущее"},
        ]
        ctx = format_ctx(messages)
        assert ctx.startswith("Контекст предыдущей переписки в корпоративном чате:")

    def test_agent_name_in_context(self):
        """Agent name is prefixed before their message."""
        format_ctx = _make_format_chat_context()
        messages = [
            {"role": "user", "content": "Привет"},
            {"role": "assistant", "content": "Ответ от Юки", "agent_name": "Юки"},
            {"role": "user", "content": "Текущее"},
        ]
        ctx = format_ctx(messages)
        assert "Юки: Ответ от Юки" in ctx

    def test_default_agent_name_is_aleksey(self):
        """Missing agent_name defaults to Алексей."""
        format_ctx = _make_format_chat_context()
        messages = [
            {"role": "user", "content": "Привет"},
            {"role": "assistant", "content": "Ответ"},
            {"role": "user", "content": "Текущее"},
        ]
        ctx = format_ctx(messages)
        assert "Алексей: Ответ" in ctx

    def test_pending_prompt_block_still_has_save_and_rerun(self):
        """The pending_prompt block still calls save_chat_history and st.rerun."""
        source = _read_app_source()
        lines = source.split("\n")
        in_pending = False
        has_save = False
        has_rerun = False
        for line in lines:
            if '"pending_prompt" in st.session_state' in line:
                in_pending = True
            if in_pending:
                if "save_chat_history" in line:
                    has_save = True
                if "st.rerun()" in line:
                    has_rerun = True
                    break
        assert has_save, "save_chat_history must still be called"
        assert has_rerun, "st.rerun must still be called"

    def test_messages_still_appended_with_correct_fields(self):
        """Messages appended in the loop still have all required fields."""
        source = _read_app_source()
        # Find the append block inside the for loop
        assert '"role": "assistant"' in source
        assert '"agent_key": target_key' in source
        assert '"agent_name": AGENTS[target_key]["name"]' in source

    def test_app_file_valid_python(self):
        """app.py is still valid Python after changes."""
        source = _read_app_source()
        try:
            ast.parse(source)
        except SyntaxError as e:
            pytest.fail(f"app.py has syntax error: {e}")
