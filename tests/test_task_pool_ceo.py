"""Tests for Task Pool commands and callbacks in CEO bot."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.task_pool import TaskStatus, create_task, get_task, _load_pool, ESCALATION_THRESHOLD
from src.telegram_ceo.keyboards import (
    task_menu_keyboard,
    task_detail_keyboard,
    task_assign_keyboard,
    escalation_keyboard,
    stale_task_keyboard,
)
from src.telegram_ceo.callback_factory import TaskCB, EscCB


# ──────────────────────────────────────────────────────────
# Keyboard tests
# ──────────────────────────────────────────────────────────

class TestTaskKeyboards:
    def test_task_menu_keyboard(self):
        kb = task_menu_keyboard()
        assert len(kb.inline_keyboard) == 2
        assert kb.inline_keyboard[0][0].text == "📝 Новая задача"
        assert kb.inline_keyboard[0][0].callback_data == TaskCB(action="new").pack()

    def test_task_detail_todo(self):
        kb = task_detail_keyboard("abc", "TODO")
        buttons = [b.callback_data for row in kb.inline_keyboard for b in row]
        assert TaskCB(action="assign", id="abc").pack() in buttons
        assert TaskCB(action="delete", id="abc").pack() in buttons

    def test_task_detail_assigned(self):
        kb = task_detail_keyboard("abc", "ASSIGNED")
        buttons = [b.callback_data for row in kb.inline_keyboard for b in row]
        assert TaskCB(action="start", id="abc").pack() in buttons
        assert TaskCB(action="assign", id="abc").pack() in buttons

    def test_task_detail_in_progress(self):
        kb = task_detail_keyboard("abc", "IN_PROGRESS")
        buttons = [b.callback_data for row in kb.inline_keyboard for b in row]
        assert TaskCB(action="done", id="abc").pack() in buttons
        assert TaskCB(action="block", id="abc").pack() in buttons

    def test_task_detail_blocked(self):
        kb = task_detail_keyboard("abc", "BLOCKED")
        buttons = [b.callback_data for row in kb.inline_keyboard for b in row]
        assert TaskCB(action="assign", id="abc").pack() in buttons

    def test_task_detail_done_has_back(self):
        kb = task_detail_keyboard("abc", "DONE")
        buttons = [b.callback_data for row in kb.inline_keyboard for b in row]
        assert TaskCB(action="all").pack() in buttons

    def test_task_assign_keyboard(self):
        kb = task_assign_keyboard("abc")
        callbacks = [b.callback_data for row in kb.inline_keyboard for b in row]
        assert TaskCB(action="do_assign", id="abc", agent="accountant").pack() in callbacks
        assert TaskCB(action="do_assign", id="abc", agent="automator").pack() in callbacks
        assert TaskCB(action="do_assign", id="abc", agent="smm").pack() in callbacks
        assert TaskCB(action="do_assign", id="abc", agent="designer").pack() in callbacks
        assert TaskCB(action="do_assign", id="abc", agent="cpo").pack() in callbacks
        assert TaskCB(action="detail", id="abc").pack() in callbacks  # back button

    def test_task_assign_has_all_agents(self):
        kb = task_assign_keyboard("x")
        agent_keys = []
        for row in kb.inline_keyboard:
            for b in row:
                if b.callback_data and b.callback_data.startswith("task:do_assign:"):
                    cb = TaskCB.unpack(b.callback_data)
                    agent_keys.append(cb.agent)
        assert set(agent_keys) == {"accountant", "automator", "smm", "designer", "cpo"}


# ──────────────────────────────────────────────────────────
# Callback handler tests
# ──────────────────────────────────────────────────────────

class TestTaskCallbacks:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        path = str(tmp_path / "pool.json")
        monkeypatch.setattr("src.task_pool._pool_path", lambda: path)

    def test_new_task_state(self):
        from src.telegram_ceo.handlers.callbacks import (
            is_in_new_task_mode,
            _new_task_state,
        )
        _new_task_state.clear()
        assert is_in_new_task_mode(123) is False
        _new_task_state.add(123)
        assert is_in_new_task_mode(123) is True
        _new_task_state.discard(123)
        assert is_in_new_task_mode(123) is False

    def test_conditions_state_exists(self):
        from src.telegram_ceo.handlers.callbacks import (
            is_in_conditions_mode,
            _conditions_state,
        )
        _conditions_state.clear()
        assert is_in_conditions_mode(999) is False
        _conditions_state[999] = "prop-1"
        assert is_in_conditions_mode(999) is True


# ──────────────────────────────────────────────────────────
# Command handler tests (unit-level, mock message)
# ──────────────────────────────────────────────────────────

def _make_message(text: str = "", user_id: int = 1):
    """Create a mock aiogram Message."""
    msg = AsyncMock()
    msg.text = text
    msg.from_user = MagicMock()
    msg.from_user.id = user_id
    msg.chat = MagicMock()
    msg.chat.id = user_id
    msg.answer = AsyncMock()
    msg.bot = MagicMock()
    return msg


class TestTaskCommand:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        path = str(tmp_path / "pool.json")
        monkeypatch.setattr("src.task_pool._pool_path", lambda: path)

    @pytest.mark.asyncio
    async def test_task_without_title_shows_menu(self):
        from src.telegram_ceo.handlers.commands import cmd_task
        msg = _make_message("/task")
        await cmd_task(msg)
        msg.answer.assert_called_once()
        call_kwargs = msg.answer.call_args
        assert "Task Pool" in call_kwargs.args[0] or "пуст" in call_kwargs.args[0]

    @pytest.mark.asyncio
    async def test_task_with_title_creates(self):
        from src.telegram_ceo.handlers.commands import cmd_task
        msg = _make_message("/task MCP-обёртка для CFO")
        await cmd_task(msg)
        msg.answer.assert_called_once()
        call_args = msg.answer.call_args
        assert "MCP-обёртка для CFO" in call_args.args[0]

    @pytest.mark.asyncio
    async def test_task_with_title_persists(self):
        from src.telegram_ceo.handlers.commands import cmd_task
        msg = _make_message("/task Тестовая задача")
        await cmd_task(msg)
        pool = _load_pool()
        assert len(pool) == 1
        assert pool[0]["title"] == "Тестовая задача"


class TestTasksCommand:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        path = str(tmp_path / "pool.json")
        monkeypatch.setattr("src.task_pool._pool_path", lambda: path)

    @pytest.mark.asyncio
    async def test_tasks_empty(self):
        from src.telegram_ceo.handlers.commands import cmd_tasks
        msg = _make_message("/tasks")
        await cmd_tasks(msg)
        assert "пуст" in msg.answer.call_args.args[0]

    @pytest.mark.asyncio
    async def test_tasks_with_data(self):
        from src.telegram_ceo.handlers.commands import cmd_tasks
        create_task("Task A")
        create_task("Task B", assignee="smm")
        msg = _make_message("/tasks")
        await cmd_tasks(msg)
        text = msg.answer.call_args.args[0]
        assert "Task A" in text
        assert "Task B" in text
        assert "Task Pool" in text


# ──────────────────────────────────────────────────────────
# Escalation keyboard tests
# ──────────────────────────────────────────────────────────

class TestEscalationKeyboards:
    def test_escalation_keyboard_has_4_buttons(self):
        kb = escalation_keyboard("abc")
        all_buttons = [b for row in kb.inline_keyboard for b in row]
        assert len(all_buttons) == 4

    def test_escalation_callback_data(self):
        kb = escalation_keyboard("abc")
        callbacks = [b.callback_data for row in kb.inline_keyboard for b in row]
        assert EscCB(action="extend", id="abc").pack() in callbacks
        assert EscCB(action="create", id="abc").pack() in callbacks
        assert EscCB(action="split", id="abc").pack() in callbacks
        assert EscCB(action="manual", id="abc").pack() in callbacks

    def test_stale_task_keyboard(self):
        kb = stale_task_keyboard("xyz")
        callbacks = [b.callback_data for row in kb.inline_keyboard for b in row]
        assert TaskCB(action="assign", id="xyz").pack() in callbacks
        assert TaskCB(action="block", id="xyz").pack() in callbacks
        assert TaskCB(action="detail", id="xyz").pack() in callbacks


class TestEscalationCallbacks:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        path = str(tmp_path / "pool.json")
        monkeypatch.setattr("src.task_pool._pool_path", lambda: path)

    def test_split_mode_state(self):
        from src.telegram_ceo.handlers.callbacks import (
            is_in_split_mode, _split_task_state,
        )
        _split_task_state.clear()
        assert is_in_split_mode(123) is False
        _split_task_state[123] = "task-1"
        assert is_in_split_mode(123) is True
        del _split_task_state[123]
        assert is_in_split_mode(123) is False


class TestEscalationInTaskCreation:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        path = str(tmp_path / "pool.json")
        monkeypatch.setattr("src.task_pool._pool_path", lambda: path)

    @pytest.mark.asyncio
    async def test_unknown_task_triggers_escalation(self):
        """Task with no matching tags should trigger escalation keyboard."""
        from src.telegram_ceo.handlers.commands import cmd_task
        msg = _make_message("/task Prepare magical unicorn parade")
        await cmd_task(msg)
        call_kwargs = msg.answer.call_args
        # Should contain escalation warning
        assert "⚠️" in call_kwargs.args[0] or "Нет подходящего" in call_kwargs.args[0]

    @pytest.mark.asyncio
    async def test_known_task_shows_recommendation(self):
        """Task with matching tags should show recommendation."""
        from src.telegram_ceo.handlers.commands import cmd_task
        msg = _make_message("/task Настроить MCP инфраструктуру")
        await cmd_task(msg)
        call_kwargs = msg.answer.call_args
        assert "Рекомендация" in call_kwargs.args[0] or "automator" in call_kwargs.args[0]
