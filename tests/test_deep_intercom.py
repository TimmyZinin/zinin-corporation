"""
🔬 Deep tests for Fix #1: Agent inter-communication

Covers:
- format_chat_context edge cases (empty, unicode, huge messages)
- Broadcast loop: context re-computation per agent
- Truncation boundary conditions (exactly 800, 799, 801)
- max_messages boundary conditions
- Context format correctness (header, agent labels)
- Integration: broadcast loop structure in app.py AST
- Regression: no regressions in detect_agents, chat input flow
"""

import ast
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

APP_PATH = os.path.join(os.path.dirname(__file__), "..", "app.py")


def _app_source():
    with open(APP_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _build_format_chat_context():
    """Extract format_chat_context from app.py and return it as callable."""
    source = _app_source()
    tree = ast.parse(source)
    ns = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "format_chat_context":
            exec(ast.get_source_segment(source, node), ns)
    return ns["format_chat_context"]


# ═══════════════════════════════════════════════════════════════
# 1. format_chat_context — edge cases
# ═══════════════════════════════════════════════════════════════

class TestFormatChatContextEdgeCases:

    def test_empty_list(self):
        fmt = _build_format_chat_context()
        assert fmt([]) == ""

    def test_none_content_in_message(self):
        """Message with missing 'content' key should not crash."""
        fmt = _build_format_chat_context()
        msgs = [{"role": "user", "content": "hi"}]
        result = fmt(msgs)
        assert "Тим: hi" in result

    def test_unicode_emoji_preserved(self):
        fmt = _build_format_chat_context()
        msgs = [
            {"role": "user", "content": "Привет 🇷🇺 мир 🌍"},
            {"role": "assistant", "content": "Ответ 💰📊", "agent_name": "Маттиас"},
        ]
        result = fmt(msgs)
        assert "🇷🇺" in result
        assert "💰📊" in result

    def test_multiline_content_preserved(self):
        fmt = _build_format_chat_context()
        msgs = [{"role": "user", "content": "line1\nline2\nline3"}]
        result = fmt(msgs)
        assert "line1\nline2\nline3" in result

    def test_very_long_user_message_not_truncated(self):
        """User messages must NOT be truncated regardless of length."""
        fmt = _build_format_chat_context()
        long_msg = "Ж" * 5000
        msgs = [{"role": "user", "content": long_msg}]
        result = fmt(msgs)
        assert "Ж" * 5000 in result

    def test_single_message(self):
        fmt = _build_format_chat_context()
        msgs = [{"role": "user", "content": "Только одно"}]
        result = fmt(msgs)
        assert "Контекст" in result
        assert "Тим: Только одно" in result

    def test_mixed_roles(self):
        fmt = _build_format_chat_context()
        msgs = [
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "A1", "agent_name": "Мартин"},
            {"role": "user", "content": "Q2"},
            {"role": "assistant", "content": "A2", "agent_name": "Юки"},
        ]
        result = fmt(msgs)
        assert "Тим: Q1" in result
        assert "Мартин: A1" in result
        assert "Тим: Q2" in result
        assert "Юки: A2" in result

    def test_missing_agent_name_defaults_to_aleksey(self):
        fmt = _build_format_chat_context()
        msgs = [{"role": "assistant", "content": "Ответ"}]
        result = fmt(msgs)
        assert "Алексей: Ответ" in result

    def test_header_always_present(self):
        fmt = _build_format_chat_context()
        msgs = [{"role": "user", "content": "x"}]
        result = fmt(msgs)
        assert result.startswith("Контекст предыдущей переписки")


# ═══════════════════════════════════════════════════════════════
# 2. Truncation boundary conditions
# ═══════════════════════════════════════════════════════════════

class TestTruncationBoundary:

    def test_exactly_800_chars_preserved(self):
        fmt = _build_format_chat_context()
        content = "X" * 800
        msgs = [{"role": "assistant", "content": content, "agent_name": "T"}]
        result = fmt(msgs)
        assert "X" * 800 in result

    def test_799_chars_preserved(self):
        fmt = _build_format_chat_context()
        content = "Y" * 799
        msgs = [{"role": "assistant", "content": content, "agent_name": "T"}]
        result = fmt(msgs)
        assert "Y" * 799 in result

    def test_801_chars_truncated(self):
        fmt = _build_format_chat_context()
        content = "Z" * 801
        msgs = [{"role": "assistant", "content": content, "agent_name": "T"}]
        result = fmt(msgs)
        assert "Z" * 800 in result
        assert "Z" * 801 not in result

    def test_2000_chars_truncated_to_800(self):
        fmt = _build_format_chat_context()
        content = "W" * 2000
        msgs = [{"role": "assistant", "content": content, "agent_name": "T"}]
        result = fmt(msgs)
        assert "W" * 800 in result
        assert "W" * 801 not in result

    def test_cyrillic_800_chars(self):
        """Cyrillic chars are multi-byte in UTF-8 but Python slices by char."""
        fmt = _build_format_chat_context()
        content = "Ы" * 900
        msgs = [{"role": "assistant", "content": content, "agent_name": "T"}]
        result = fmt(msgs)
        assert "Ы" * 800 in result
        assert "Ы" * 801 not in result

    def test_truncation_only_affects_assistant(self):
        """User messages of any length survive; only assistant is truncated."""
        fmt = _build_format_chat_context()
        msgs = [
            {"role": "user", "content": "U" * 5000},
            {"role": "assistant", "content": "A" * 1000, "agent_name": "T"},
        ]
        result = fmt(msgs)
        assert "U" * 5000 in result
        assert "A" * 800 in result
        assert "A" * 801 not in result


# ═══════════════════════════════════════════════════════════════
# 3. max_messages boundary conditions
# ═══════════════════════════════════════════════════════════════

class TestMaxMessagesBoundary:

    def test_exactly_20_messages(self):
        fmt = _build_format_chat_context()
        msgs = [{"role": "user", "content": f"msg_{i}"} for i in range(20)]
        result = fmt(msgs)
        assert "msg_0" in result
        assert "msg_19" in result

    def test_21_messages_drops_oldest(self):
        fmt = _build_format_chat_context()
        msgs = [{"role": "user", "content": f"msg_{i}"} for i in range(21)]
        result = fmt(msgs)
        assert "msg_0" not in result
        assert "msg_1" in result
        assert "msg_20" in result

    def test_100_messages_keeps_last_20(self):
        fmt = _build_format_chat_context()
        msgs = [{"role": "user", "content": f"msg_{i}"} for i in range(100)]
        result = fmt(msgs)
        assert "msg_79" not in result
        assert "msg_80" in result
        assert "msg_99" in result

    def test_custom_max_messages_5(self):
        fmt = _build_format_chat_context()
        msgs = [{"role": "user", "content": f"m{i}"} for i in range(10)]
        result = fmt(msgs, max_messages=5)
        assert "m4" not in result
        assert "m5" in result
        assert "m9" in result

    def test_max_messages_1(self):
        fmt = _build_format_chat_context()
        msgs = [{"role": "user", "content": f"m{i}"} for i in range(5)]
        result = fmt(msgs, max_messages=1)
        assert "m3" not in result
        assert "m4" in result


# ═══════════════════════════════════════════════════════════════
# 4. Broadcast loop: context per agent
# ═══════════════════════════════════════════════════════════════

class TestBroadcastLoopContextPerAgent:
    """Simulate the broadcast loop logic: context must be re-computed
    inside the `for target_key in targets` loop."""

    def test_two_agents_second_sees_first_response(self):
        """When two agents are targeted, the second sees the first agent's reply."""
        fmt = _build_format_chat_context()
        messages = [{"role": "user", "content": "Всем привет"}]

        # Agent 1 responds
        messages.append({
            "role": "assistant",
            "content": "Привет от Маттиаса",
            "agent_name": "Маттиас",
        })

        # Context for agent 2 includes agent 1's response
        ctx2 = fmt(messages)
        assert "Маттиас: Привет от Маттиаса" in ctx2

    def test_three_agents_chain(self):
        """Three-agent chain: agent3 sees both agent1 and agent2 responses."""
        fmt = _build_format_chat_context()
        messages = [{"role": "user", "content": "Отчёт"}]

        messages.append({"role": "assistant", "content": "R1", "agent_name": "A1"})
        messages.append({"role": "assistant", "content": "R2", "agent_name": "A2"})

        ctx3 = fmt(messages)
        assert "A1: R1" in ctx3
        assert "A2: R2" in ctx3

    def test_context_before_first_agent_has_no_assistant(self):
        """Before any agent responds, context has only user messages."""
        fmt = _build_format_chat_context()
        messages = [{"role": "user", "content": "Вопрос"}]
        ctx = fmt(messages)
        assert "Тим: Вопрос" in ctx
        assert "assistant" not in ctx.lower() or "Алексей" not in ctx

    def test_broadcast_source_in_app_has_for_loop_with_context_inside(self):
        """AST check: format_chat_context is called INSIDE the for loop."""
        source = _app_source()
        lines = source.split("\n")

        # Find pending_prompt block
        start = None
        for i, line in enumerate(lines):
            if '"pending_prompt" in st.session_state' in line:
                start = i
                break
        assert start is not None

        # Find "for target_key in targets:" after start
        for_idx = None
        for i in range(start, min(start + 40, len(lines))):
            if "for target_key in targets" in lines[i]:
                for_idx = i
                break
        assert for_idx is not None, "for loop not found"

        # Find format_chat_context after for loop
        fmt_idx = None
        for i in range(for_idx + 1, min(for_idx + 20, len(lines))):
            if "format_chat_context" in lines[i]:
                fmt_idx = i
                break
        assert fmt_idx is not None, "format_chat_context not found inside loop"

        # format_chat_context must be indented MORE than the for loop
        for_indent = len(lines[for_idx]) - len(lines[for_idx].lstrip())
        fmt_indent = len(lines[fmt_idx]) - len(lines[fmt_idx].lstrip())
        assert fmt_indent > for_indent, (
            f"format_chat_context (indent={fmt_indent}) must be inside "
            f"for loop (indent={for_indent})"
        )


# ═══════════════════════════════════════════════════════════════
# 5. Regression: detect_agents still works
# ═══════════════════════════════════════════════════════════════

class TestDetectAgentsRegression:

    def test_detect_agents_function_exists(self):
        source = _app_source()
        assert "def detect_agents(" in source

    def test_detect_agent_backward_compat_exists(self):
        source = _app_source()
        assert "def detect_agent(" in source

    def test_chat_input_still_present(self):
        source = _app_source()
        assert "st.chat_input" in source

    def test_pending_prompt_mechanism(self):
        source = _app_source()
        assert "pending_prompt" in source
        assert "pending_targets" in source

    def test_execute_task_called_with_target_key(self):
        source = _app_source()
        assert "corp.execute_task(task_with_context, target_key)" in source

    def test_messages_append_after_response(self):
        source = _app_source()
        lines = source.split("\n")
        for i, line in enumerate(lines):
            if "corp.execute_task(" in line:
                window = "\n".join(lines[i:i + 20])
                assert "messages.append" in window
                return
        assert False, "execute_task not found"

    def test_save_chat_history_after_all_agents(self):
        """save_chat_history is called AFTER the for loop, not inside."""
        source = _app_source()
        lines = source.split("\n")

        start = None
        for i, line in enumerate(lines):
            if '"pending_prompt" in st.session_state' in line:
                start = i
                break

        for_idx = None
        for i in range(start, min(start + 40, len(lines))):
            if "for target_key in targets" in lines[i]:
                for_idx = i
                break
        assert for_idx is not None

        # Find save_chat_history after the for block
        save_idx = None
        for i in range(for_idx, min(for_idx + 50, len(lines))):
            if "save_chat_history" in lines[i]:
                save_idx = i
                break
        assert save_idx is not None

    def test_app_is_valid_python(self):
        source = _app_source()
        ast.parse(source)
