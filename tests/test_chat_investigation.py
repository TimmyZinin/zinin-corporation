"""
🔬 Исследовательские тесты чат-переписки с агентами

Покрывает:
1. Сохранение истории — чат не пропадает при reload
2. Видимость агентов друг другом — контекст передаётся
3. Скролл и отображение — HTML корректен, JS auto-scroll
4. Целостность сообщений — порядок, поля, кодировка
5. Edge cases — пустые сообщения, огромные сообщения, спецсимволы

При нахождении багов — тест фиксит проблему.
"""

import ast
import json
import os
import re
import sys
import time
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

APP_PATH = os.path.join(os.path.dirname(__file__), "..", "app.py")


def _app_source():
    with open(APP_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _build_func(func_name: str):
    """Extract a function from app.py by name and return it as callable.
    Injects all module-level dependencies needed by the function."""
    import html as html_module
    source = _app_source()
    tree = ast.parse(source)

    # Extract all needed functions and constants
    needed_funcs = {
        "render_chat_html": [
            "md_to_html", "hex_to_rgba", "AGENTS", "AGENT_COLORS",
        ],
        "md_to_html": [],
        "hex_to_rgba": [],
        "format_chat_context": [],
    }

    # Build namespace with dependencies
    ns = {
        "datetime": datetime,
        "timedelta": timedelta,
        "re": re,
        "html_module": html_module,
        "AGENTS": {
            "manager": {"name": "Алексей", "emoji": "👑", "flag": "🇷🇺", "title": "CEO",
                         "keywords": ["алексей", "ceo"]},
            "accountant": {"name": "Маттиас", "emoji": "🏦", "flag": "🇨🇭", "title": "CFO",
                            "keywords": ["маттиас", "финанс"]},
            "smm": {"name": "Юки", "emoji": "📱", "flag": "🇰🇷", "title": "Head of SMM",
                     "keywords": ["юки", "smm"]},
            "automator": {"name": "Мартин", "emoji": "⚙️", "flag": "🇦🇷", "title": "CTO",
                           "keywords": ["мартин", "cto"]},
        },
        "AGENT_COLORS": {
            "manager": "#e74c3c",
            "accountant": "#f39c12",
            "smm": "#e91e63",
            "automator": "#2ecc71",
        },
    }

    # Extract all functions from app.py
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            try:
                exec(ast.get_source_segment(source, node), ns)
            except Exception:
                pass

    if func_name not in ns:
        raise KeyError(f"Function {func_name} not found in app.py")
    return ns[func_name]


# ═══════════════════════════════════════════════════════════════
# 1. СОХРАНЕНИЕ ИСТОРИИ — Чат не пропадает
# ═══════════════════════════════════════════════════════════════

class TestChatPersistenceNotLost:
    """Чат-история НЕ ДОЛЖНА пропадать при перезагрузке."""

    def test_save_after_user_message(self):
        """save_chat_history вызывается СРАЗУ после добавления user-сообщения."""
        source = _app_source()
        lines = source.split("\n")
        # Find: st.session_state.messages.append({... "role": "user" ...})
        # Then: save_chat_history MUST follow within 5 lines
        for i, line in enumerate(lines):
            if '"role": "user"' in line and "messages.append" in lines[max(0, i - 3):i + 1][-1] if lines[max(0, i - 3):i + 1] else False:
                continue
        # Direct check: after user message append, save_chat_history is called
        user_append_pattern = re.compile(
            r'st\.session_state\.messages\.append\(\{.*?"role":\s*"user"',
            re.DOTALL,
        )
        match = user_append_pattern.search(source)
        assert match is not None, "User message append not found"
        # After this append, find save_chat_history within 10 lines
        pos = match.end()
        remaining = source[pos:pos + 500]
        assert "save_chat_history" in remaining, (
            "save_chat_history must be called right after user message is appended"
        )

    def test_save_after_agent_response(self):
        """save_chat_history вызывается после ответа всех агентов."""
        source = _app_source()
        lines = source.split("\n")
        # Find pending_prompt block
        for i, line in enumerate(lines):
            if '"pending_prompt" in st.session_state' in line:
                block = "\n".join(lines[i:i + 80])
                assert "save_chat_history" in block, (
                    "save_chat_history must be called in the pending_prompt block"
                )
                return
        pytest.fail("pending_prompt processing block not found")

    def test_load_on_init_before_default(self):
        """При инициализации load_chat_history вызывается ПЕРЕД созданием default message."""
        source = _app_source()
        load_pos = source.find("load_chat_history()")
        default_pos = source.find('"Добрый день! Я Алексей')
        assert load_pos > 0, "load_chat_history() not called"
        assert default_pos > 0, "default message not found"
        assert load_pos < default_pos, (
            "load_chat_history must be called BEFORE default message creation"
        )

    def test_json_save_load_roundtrip(self, tmp_path):
        """JSON save/load round-trip сохраняет все поля."""
        from src.chat_storage import save_to_json, load_from_json

        messages = [
            {
                "role": "user",
                "content": "Привет!",
                "time": "14:30",
                "date": "07.02.2026",
            },
            {
                "role": "assistant",
                "content": "Здравствуйте! Алексей на связи.",
                "agent_key": "manager",
                "agent_name": "Алексей",
                "time": "14:30",
                "date": "07.02.2026",
            },
        ]
        json_path = tmp_path / "chat_history.json"
        with patch("src.chat_storage._chat_path", return_value=str(json_path)):
            save_to_json(messages)
            loaded = load_from_json()
        assert len(loaded) == 2
        assert loaded[0]["content"] == "Привет!"
        assert loaded[1]["agent_key"] == "manager"
        assert loaded[1]["agent_name"] == "Алексей"

    def test_all_message_fields_preserved_after_save(self, tmp_path):
        """Все поля сообщения (role, content, time, date, agent_key, agent_name) сохраняются."""
        from src.chat_storage import save_to_json, load_from_json

        msg = {
            "role": "assistant",
            "content": "Тест 🇷🇺 エモジ",
            "agent_key": "smm",
            "agent_name": "Юки",
            "time": "18:00",
            "date": "07.02.2026",
        }
        json_path = tmp_path / "chat.json"
        with patch("src.chat_storage._chat_path", return_value=str(json_path)):
            save_to_json([msg])
            loaded = load_from_json()
        assert loaded[0] == msg

    def test_cyrillic_and_emoji_not_escaped_in_json(self, tmp_path):
        """Кириллица и эмодзи НЕ экранируются в JSON файле (ensure_ascii=False)."""
        from src.chat_storage import save_to_json

        msg = [{"role": "user", "content": "Привет 🌍 мир"}]
        json_path = tmp_path / "chat.json"
        with patch("src.chat_storage._chat_path", return_value=str(json_path)):
            save_to_json(msg)
        raw = json_path.read_text(encoding="utf-8")
        assert "Привет" in raw
        assert "🌍" in raw
        # ensure_ascii=False means no \\uXXXX escapes
        assert "\\u" not in raw

    def test_save_preserves_message_order(self, tmp_path):
        """Порядок сообщений сохраняется (FIFO)."""
        from src.chat_storage import save_to_json, load_from_json

        messages = [
            {"role": "user", "content": f"msg_{i}", "time": f"10:{i:02d}"}
            for i in range(50)
        ]
        json_path = tmp_path / "chat.json"
        with patch("src.chat_storage._chat_path", return_value=str(json_path)):
            save_to_json(messages)
            loaded = load_from_json()
        for i in range(50):
            assert loaded[i]["content"] == f"msg_{i}"

    def test_empty_save_and_load(self, tmp_path):
        """Сохранение пустого списка и загрузка."""
        from src.chat_storage import save_to_json, load_from_json

        json_path = tmp_path / "chat.json"
        with patch("src.chat_storage._chat_path", return_value=str(json_path)):
            save_to_json([])
            loaded = load_from_json()
        assert loaded == []

    def test_corrupt_json_file_returns_empty(self, tmp_path):
        """Повреждённый JSON файл не крашит — возвращает []."""
        from src.chat_storage import load_from_json

        json_path = tmp_path / "chat.json"
        json_path.write_text("{corrupt data!!", encoding="utf-8")
        with patch("src.chat_storage._chat_path", return_value=str(json_path)):
            loaded = load_from_json()
        assert loaded == []

    def test_save_during_thinking_state(self):
        """User message сохраняется ДО начала pending_prompt обработки."""
        source = _app_source()
        # Find the chat_input block where user types a message
        lines = source.split("\n")
        chat_input_idx = None
        for i, line in enumerate(lines):
            if "st.chat_input" in line and "prompt" in line:
                chat_input_idx = i
                break
        assert chat_input_idx is not None

        # After chat_input, find messages.append for user and save_chat_history
        block = "\n".join(lines[chat_input_idx:chat_input_idx + 40])
        append_pos = block.find("messages.append")
        save_pos = block.find("save_chat_history")
        pending_pos = block.find("pending_prompt")

        assert append_pos > 0, "messages.append not found after chat_input"
        assert save_pos > 0, "save_chat_history not found after chat_input"
        assert pending_pos > 0, "pending_prompt not found after chat_input"
        # Save must be BEFORE pending_prompt is set
        assert save_pos < pending_pos, (
            "save_chat_history must be called BEFORE setting pending_prompt, "
            "so user message is saved even if page crashes during agent response"
        )


# ═══════════════════════════════════════════════════════════════
# 2. ВИДИМОСТЬ АГЕНТОВ — Агенты видят друг друга
# ═══════════════════════════════════════════════════════════════

class TestAgentInterVisibility:
    """Агенты ДОЛЖНЫ видеть ответы друг друга через format_chat_context."""

    def test_context_includes_all_previous_messages(self):
        """format_chat_context включает ВСЕ последние сообщения."""
        fmt = _build_func("format_chat_context")
        messages = [
            {"role": "user", "content": "Вопрос всем"},
            {"role": "assistant", "content": "Ответ Маттиаса", "agent_name": "Маттиас"},
            {"role": "assistant", "content": "Ответ Мартина", "agent_name": "Мартин"},
        ]
        ctx = fmt(messages)
        assert "Тим: Вопрос всем" in ctx
        assert "Маттиас: Ответ Маттиаса" in ctx
        assert "Мартин: Ответ Мартина" in ctx

    def test_second_agent_sees_first_agents_response(self):
        """В broadcast loop агент #2 видит ответ агента #1."""
        fmt = _build_func("format_chat_context")
        # Simulate broadcast: user sends, then agent 1 replies
        msgs = [
            {"role": "user", "content": "Привет всем"},
            {"role": "assistant", "content": "Отчёт от CFO", "agent_name": "Маттиас"},
        ]
        # Now agent 2 gets context
        ctx = fmt(msgs)
        assert "Маттиас: Отчёт от CFO" in ctx

    def test_third_agent_sees_both_previous(self):
        """Агент #3 видит ответы агентов #1 и #2."""
        fmt = _build_func("format_chat_context")
        msgs = [
            {"role": "user", "content": "Всем привет"},
            {"role": "assistant", "content": "R1", "agent_name": "Маттиас"},
            {"role": "assistant", "content": "R2", "agent_name": "Мартин"},
        ]
        ctx = fmt(msgs)
        assert "Маттиас: R1" in ctx
        assert "Мартин: R2" in ctx

    def test_context_recomputed_inside_for_loop(self):
        """format_chat_context вызывается ВНУТРИ for loop (не до него)."""
        source = _app_source()
        lines = source.split("\n")
        # Find the for target_key in targets loop
        for_idx = None
        for i, line in enumerate(lines):
            if "for target_key in targets" in line:
                for_idx = i
                break
        assert for_idx is not None, "for target_key in targets not found"

        # Find format_chat_context after for loop
        fmt_idx = None
        for i in range(for_idx + 1, min(for_idx + 20, len(lines))):
            if "format_chat_context" in lines[i]:
                fmt_idx = i
                break
        assert fmt_idx is not None, "format_chat_context not found after for loop"

        # Must be indented more than the for loop (i.e., inside it)
        for_indent = len(lines[for_idx]) - len(lines[for_idx].lstrip())
        fmt_indent = len(lines[fmt_idx]) - len(lines[fmt_idx].lstrip())
        assert fmt_indent > for_indent, (
            f"format_chat_context (indent={fmt_indent}) must be INSIDE "
            f"for loop (indent={for_indent})"
        )

    def test_context_header_present(self):
        """Контекст начинается с заголовка 'Контекст предыдущей переписки'."""
        fmt = _build_func("format_chat_context")
        msgs = [{"role": "user", "content": "test"}]
        ctx = fmt(msgs)
        assert ctx.startswith("Контекст предыдущей переписки")

    def test_context_wraps_prompt_correctly(self):
        """task_with_context формируется как 'контекст + --- + новое сообщение'."""
        source = _app_source()
        assert '---\\nНовое сообщение от Тима:' in source or \
               '---\nНовое сообщение от Тима:' in source, (
            "Context wrapper format not found in app.py"
        )

    def test_agent_name_labels_correct(self):
        """В контексте user = 'Тим', assistant = agent_name."""
        fmt = _build_func("format_chat_context")
        msgs = [
            {"role": "user", "content": "Вопрос"},
            {"role": "assistant", "content": "Ответ", "agent_name": "Юки"},
        ]
        ctx = fmt(msgs)
        assert "Тим: Вопрос" in ctx
        assert "Юки: Ответ" in ctx

    def test_missing_agent_name_defaults_to_aleksey(self):
        """Если agent_name отсутствует, подставляется 'Алексей'."""
        fmt = _build_func("format_chat_context")
        msgs = [{"role": "assistant", "content": "Ответ без имени"}]
        ctx = fmt(msgs)
        assert "Алексей: Ответ без имени" in ctx

    def test_long_response_truncated_to_800(self):
        """Ответ агента обрезается до 800 символов в контексте."""
        fmt = _build_func("format_chat_context")
        long_content = "Б" * 2000
        msgs = [{"role": "assistant", "content": long_content, "agent_name": "Test"}]
        ctx = fmt(msgs)
        assert "Б" * 800 in ctx
        assert "Б" * 801 not in ctx

    def test_user_message_not_truncated(self):
        """Сообщение пользователя НЕ обрезается."""
        fmt = _build_func("format_chat_context")
        long_user = "У" * 5000
        msgs = [{"role": "user", "content": long_user}]
        ctx = fmt(msgs)
        assert "У" * 5000 in ctx

    def test_max_messages_default_20(self):
        """По умолчанию контекст содержит последние 20 сообщений."""
        fmt = _build_func("format_chat_context")
        msgs = [{"role": "user", "content": f"m{i}"} for i in range(30)]
        ctx = fmt(msgs)
        assert "m9" not in ctx  # first 10 dropped
        assert "m10" in ctx     # 11th kept
        assert "m29" in ctx     # last kept

    def test_execute_task_called_with_target_key(self):
        """corp.execute_task вызывается с правильными аргументами."""
        source = _app_source()
        assert "corp.execute_task(task_with_context, target_key)" in source

    def test_response_appended_with_correct_agent_key(self):
        """Ответ агента сохраняется с правильным agent_key и agent_name."""
        source = _app_source()
        lines = source.split("\n")
        for i, line in enumerate(lines):
            if "corp.execute_task(" in line:
                block = "\n".join(lines[i:i + 20])
                assert '"agent_key": target_key' in block, (
                    "agent_key should be set to target_key in response"
                )
                assert 'AGENTS[target_key]["name"]' in block, (
                    "agent_name should come from AGENTS registry"
                )
                return
        pytest.fail("execute_task call not found")


# ═══════════════════════════════════════════════════════════════
# 3. СКРОЛЛ И ОТОБРАЖЕНИЕ — История видна и прокручивается
# ═══════════════════════════════════════════════════════════════

class TestScrollAndDisplay:
    """Чат ДОЛЖЕН автоматически скроллиться вниз и показывать всю историю."""

    def test_auto_scroll_js_exists(self):
        """JavaScript auto-scroll присутствует в app.py."""
        source = _app_source()
        assert "scrollTop" in source, "JS scrollTop not found"
        assert "scrollHeight" in source, "JS scrollHeight not found"

    def test_auto_scroll_uses_components_html(self):
        """Auto-scroll использует st_components.html (позволяет JS)."""
        source = _app_source()
        assert "st_components.html" in source, "st_components.html not used for scroll"

    def test_scroll_script_targets_correct_container(self):
        """JS скрипт ищет правильный контейнер для скролла."""
        source = _app_source()
        # Should target the main app container
        assert "stAppViewBlockContainer" in source or "stVerticalBlock" in source, (
            "Scroll script must target Streamlit container elements"
        )

    def test_all_messages_rendered_in_html(self):
        """render_chat_html рендерит ВСЕ переданные сообщения."""
        render = _build_func("render_chat_html")
        messages = [
            {"role": "user", "content": f"msg_{i}", "time": f"10:{i:02d}",
             "date": "07.02.2026"}
            for i in range(10)
        ]
        html = render(messages)
        for i in range(10):
            assert f"msg_{i}" in html, f"Message msg_{i} not found in rendered HTML"

    def test_messages_in_correct_order(self):
        """Сообщения отображаются в хронологическом порядке."""
        render = _build_func("render_chat_html")
        messages = [
            {"role": "user", "content": "FIRST", "time": "10:00", "date": "07.02.2026"},
            {"role": "assistant", "content": "SECOND", "agent_key": "manager",
             "time": "10:01", "date": "07.02.2026"},
            {"role": "user", "content": "THIRD", "time": "10:02", "date": "07.02.2026"},
        ]
        html = render(messages)
        pos_first = html.find("FIRST")
        pos_second = html.find("SECOND")
        pos_third = html.find("THIRD")
        assert pos_first < pos_second < pos_third, (
            "Messages must appear in chronological order"
        )

    def test_chat_container_has_log_role(self):
        """Chat container имеет role='log' для accessibility."""
        render = _build_func("render_chat_html")
        html = render([{"role": "user", "content": "x", "time": "", "date": ""}])
        assert 'role="log"' in html

    def test_user_message_has_sent_class(self):
        """User message имеет класс zc-sent."""
        render = _build_func("render_chat_html")
        html = render([{"role": "user", "content": "test", "time": "", "date": ""}])
        assert "zc-sent" in html

    def test_agent_message_has_recv_class(self):
        """Agent message имеет класс zc-received."""
        render = _build_func("render_chat_html")
        html = render([
            {"role": "assistant", "content": "test", "agent_key": "manager",
             "time": "", "date": ""}
        ])
        assert "zc-received" in html

    def test_agent_color_border(self):
        """Agent bubble имеет цветной border-left."""
        render = _build_func("render_chat_html")
        html = render([
            {"role": "assistant", "content": "test", "agent_key": "accountant",
             "time": "", "date": ""}
        ])
        assert "border-left:3px solid" in html
        assert "#f39c12" in html  # accountant color

    def test_date_separator_rendered(self):
        """Разделитель дат рендерится между сообщениями разных дней."""
        render = _build_func("render_chat_html")
        html = render([
            {"role": "user", "content": "day1", "time": "23:59", "date": "06.02.2026"},
            {"role": "user", "content": "day2", "time": "00:01", "date": "07.02.2026"},
        ])
        assert "zc-date-sep" in html

    def test_last_message_has_animation_class(self):
        """Последнее сообщение имеет класс zc-new для анимации."""
        render = _build_func("render_chat_html")
        html = render([
            {"role": "user", "content": "first", "time": "", "date": ""},
            {"role": "user", "content": "last", "time": "", "date": ""},
        ])
        # zc-new should be on the last message only
        parts = html.split("zc-new")
        assert len(parts) == 2, "zc-new should appear exactly once (on last message)"

    def test_time_displayed_in_bubble(self):
        """Время отображается в каждом bubble."""
        render = _build_func("render_chat_html")
        html = render([
            {"role": "user", "content": "test", "time": "14:30", "date": ""},
        ])
        assert "14:30" in html
        assert "zc-time" in html

    def test_avatar_shown_for_first_message(self):
        """Аватар показывается для первого сообщения агента в группе."""
        render = _build_func("render_chat_html")
        html = render([
            {"role": "assistant", "content": "Hello", "agent_key": "manager",
             "time": "", "date": ""},
        ])
        assert "zc-avatar" in html
        assert "👑" in html  # manager emoji

    def test_grouped_messages_no_duplicate_avatar(self):
        """Группированные сообщения одного агента — аватар только первый раз."""
        render = _build_func("render_chat_html")
        html = render([
            {"role": "assistant", "content": "msg1", "agent_key": "manager",
             "time": "", "date": ""},
            {"role": "assistant", "content": "msg2", "agent_key": "manager",
             "time": "", "date": ""},
        ])
        # Second message should have avatar-space instead of avatar
        assert "zc-avatar-space" in html
        assert html.count("zc-grouped") >= 1

    def test_scroll_height_zero(self):
        """st_components.html для скролла имеет height=0 (невидимый)."""
        source = _app_source()
        # Find the scroll script block
        lines = source.split("\n")
        for i, line in enumerate(lines):
            if "scrollTop" in line and "scrollHeight" in line:
                # Look for height=0 nearby
                block = "\n".join(lines[max(0, i - 5):i + 5])
                assert "height=0" in block, (
                    "Scroll script must use height=0 to be invisible"
                )
                return
        pytest.fail("Scroll script not found")

    def test_render_html_used_with_st_html(self):
        """render_chat_html вызывается и результат передаётся в st.html()."""
        source = _app_source()
        assert "render_chat_html(st.session_state.messages)" in source, (
            "render_chat_html should be called with session messages"
        )
        assert "st.html(chat_html" in source, (
            "chat_html should be passed to st.html()"
        )


# ═══════════════════════════════════════════════════════════════
# 4. ЦЕЛОСТНОСТЬ ДАННЫХ — Формат сообщений
# ═══════════════════════════════════════════════════════════════

class TestMessageIntegrity:
    """Формат и целостность сообщений."""

    def test_user_message_has_required_fields(self):
        """User сообщение содержит role, content, time, date."""
        source = _app_source()
        # Find user message append
        pattern = re.compile(
            r'messages\.append\(\{[^}]*"role":\s*"user"[^}]*\}',
            re.DOTALL,
        )
        match = pattern.search(source)
        assert match is not None
        block = match.group()
        assert '"content"' in block
        assert '"time"' in block
        assert '"date"' in block

    def test_agent_message_has_required_fields(self):
        """Agent сообщение содержит role, content, agent_key, agent_name, time, date."""
        source = _app_source()
        lines = source.split("\n")
        for i, line in enumerate(lines):
            if "corp.execute_task(" in line:
                block = "\n".join(lines[i:i + 25])
                assert '"role": "assistant"' in block
                assert '"content"' in block
                assert '"agent_key"' in block
                assert '"agent_name"' in block
                assert '"time"' in block
                assert '"date"' in block
                return
        pytest.fail("execute_task block not found")

    def test_detect_agents_returns_list(self):
        """detect_agents всегда возвращает list."""
        source = _app_source()
        tree = ast.parse(source)
        ns = {"st": MagicMock(), "AGENTS": {
            "manager": {"name": "Алексей", "emoji": "👑", "flag": "🇷🇺", "title": "CEO",
                         "keywords": ["алексей", "ceo"]},
            "accountant": {"name": "Маттиас", "emoji": "🏦", "flag": "🇨🇭", "title": "CFO",
                            "keywords": ["маттиас", "финанс"]},
            "smm": {"name": "Юки", "emoji": "📱", "flag": "🇰🇷", "title": "SMM",
                     "keywords": ["юки", "smm", "пост"]},
            "automator": {"name": "Мартин", "emoji": "⚙️", "flag": "🇦🇷", "title": "CTO",
                           "keywords": ["мартин", "cto"]},
        }}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "detect_agents":
                exec(ast.get_source_segment(source, node), ns)
                break
        detect_agents = ns["detect_agents"]

        # Mock st.session_state.get
        ns["st"].session_state.get.return_value = "manager"
        result = detect_agents("Привет всем")
        assert isinstance(result, list)
        assert len(result) == 4  # "всем" targets all agents

    def test_detect_agents_single_agent(self):
        """detect_agents для одного агента — list из одного элемента."""
        source = _app_source()
        tree = ast.parse(source)
        ns = {"st": MagicMock(), "AGENTS": {
            "manager": {"name": "Алексей", "emoji": "👑", "flag": "🇷🇺", "title": "CEO",
                         "keywords": ["алексей", "ceo"]},
            "accountant": {"name": "Маттиас", "emoji": "🏦", "flag": "🇨🇭", "title": "CFO",
                            "keywords": ["маттиас", "финанс"]},
            "smm": {"name": "Юки", "emoji": "📱", "flag": "🇰🇷", "title": "SMM",
                     "keywords": ["юки", "smm", "пост"]},
            "automator": {"name": "Мартин", "emoji": "⚙️", "flag": "🇦🇷", "title": "CTO",
                           "keywords": ["мартин", "cto"]},
        }}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "detect_agents":
                exec(ast.get_source_segment(source, node), ns)
                break
        detect_agents = ns["detect_agents"]
        ns["st"].session_state.get.return_value = "manager"

        result = detect_agents("Маттиас, как дела?")
        assert result == ["accountant"]

    def test_default_message_on_fresh_start(self):
        """При отсутствии истории создаётся приветственное сообщение."""
        source = _app_source()
        assert "Добрый день! Я Алексей" in source

    def test_default_message_has_all_fields(self):
        """Приветственное сообщение содержит все обязательные поля."""
        source = _app_source()
        # Find default message block
        idx = source.find('"Добрый день! Я Алексей')
        assert idx > 0
        block = source[idx - 200:idx + 500]
        assert '"role": "assistant"' in block
        assert '"agent_key": "manager"' in block
        assert '"agent_name": "Алексей"' in block
        assert '"time"' in block
        assert '"date"' in block


# ═══════════════════════════════════════════════════════════════
# 5. EDGE CASES — Экстремальные сценарии
# ═══════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Экстремальные сценарии, которые не должны ломать чат."""

    def test_render_empty_messages(self):
        """Рендер пустого списка сообщений не крашится."""
        render = _build_func("render_chat_html")
        html = render([])
        assert "zc-chat" in html

    def test_render_message_without_time(self):
        """Сообщение без поля time не крашит рендер."""
        render = _build_func("render_chat_html")
        html = render([{"role": "user", "content": "test"}])
        assert "test" in html

    def test_render_message_without_date(self):
        """Сообщение без поля date не крашит рендер."""
        render = _build_func("render_chat_html")
        html = render([{"role": "user", "content": "test", "time": "10:00"}])
        assert "test" in html

    def test_render_message_without_agent_key(self):
        """Сообщение assistant без agent_key использует manager по умолчанию."""
        render = _build_func("render_chat_html")
        html = render([{"role": "assistant", "content": "test", "time": "10:00",
                         "date": "07.02.2026"}])
        assert "test" in html
        assert "👑" in html  # manager avatar

    def test_huge_message_renders(self):
        """Огромное сообщение (100K символов) рендерится без ошибок."""
        render = _build_func("render_chat_html")
        big = "X" * 100_000
        html = render([{"role": "user", "content": big, "time": "", "date": ""}])
        assert "X" * 100 in html

    def test_xss_in_content_escaped(self):
        """HTML в content экранируется (XSS protection)."""
        md_to_html = _build_func("md_to_html")
        result = md_to_html('<script>alert("xss")</script>')
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_many_messages_performance(self):
        """500 сообщений рендерятся менее чем за 2 секунды."""
        render = _build_func("render_chat_html")
        messages = [
            {"role": "user" if i % 2 == 0 else "assistant",
             "content": f"Message number {i} with some text",
             "agent_key": "manager",
             "time": f"{i % 24:02d}:{i % 60:02d}",
             "date": "07.02.2026"}
            for i in range(500)
        ]
        start = time.time()
        html = render(messages)
        elapsed = time.time() - start
        assert elapsed < 2.0, f"Rendering 500 messages took {elapsed:.2f}s (>2s)"
        assert "Message number 499" in html

    def test_special_chars_in_content(self):
        """Спецсимволы (кавычки, амперсанды) не ломают HTML."""
        render = _build_func("render_chat_html")
        html = render([
            {"role": "user", "content": 'Тест "кавычки" & <спецсимволы>',
             "time": "", "date": ""},
        ])
        assert "&amp;" in html or "&" in html  # escaped or raw
        assert "<спецсимволы>" not in html  # should be escaped


# ═══════════════════════════════════════════════════════════════
# 6. CLEAR CHAT — Очистка чата
# ═══════════════════════════════════════════════════════════════

class TestClearChat:
    """Очистка чата работает корректно."""

    def test_clear_has_confirmation(self):
        """Очистка чата требует подтверждения (двухшаговая)."""
        source = _app_source()
        assert "confirm_clear" in source, "Two-step clear confirmation not found"

    def test_clear_saves_new_state(self):
        """После очистки save_chat_history вызывается."""
        source = _app_source()
        lines = source.split("\n")
        for i, line in enumerate(lines):
            if "confirm_yes" in line:
                block = "\n".join(lines[i:i + 20])
                assert "save_chat_history" in block, (
                    "save_chat_history must be called after clearing chat"
                )
                return
        pytest.fail("confirm_yes button not found")

    def test_clear_resets_to_welcome_message(self):
        """После очистки остаётся приветственное сообщение."""
        source = _app_source()
        lines = source.split("\n")
        for i, line in enumerate(lines):
            if "confirm_yes" in line:
                block = "\n".join(lines[i:i + 20])
                assert "Чат очищен" in block, (
                    "After clear, a welcome message should be shown"
                )
                return
        pytest.fail("confirm_yes block not found")


# ═══════════════════════════════════════════════════════════════
# 7. REGRESSION — Ничего не сломано
# ═══════════════════════════════════════════════════════════════

class TestRegression:
    """Базовые функции не сломаны."""

    def test_app_is_valid_python(self):
        ast.parse(_app_source())

    def test_chat_storage_is_valid_python(self):
        storage_path = os.path.join(os.path.dirname(__file__), "..", "src", "chat_storage.py")
        with open(storage_path) as f:
            ast.parse(f.read())

    def test_agents_registry_has_4_agents(self):
        source = _app_source()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "AGENTS":
                        assert isinstance(node.value, ast.Dict)
                        assert len(node.value.keys) == 4
                        return
        pytest.fail("AGENTS dict not found")

    def test_chat_input_present(self):
        assert "st.chat_input" in _app_source()

    def test_render_chat_html_function_exists(self):
        assert "def render_chat_html" in _app_source()

    def test_format_chat_context_function_exists(self):
        assert "def format_chat_context" in _app_source()

    def test_detect_agents_function_exists(self):
        assert "def detect_agents" in _app_source()

    def test_save_chat_history_imported(self):
        assert "from src.chat_storage import" in _app_source()
        assert "save_chat_history" in _app_source()
        assert "load_chat_history" in _app_source()
