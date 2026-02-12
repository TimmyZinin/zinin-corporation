"""Tests for src/brain_dump.py — Brain Dump processor."""

import pytest

from src.brain_dump import (
    is_brain_dump,
    parse_brain_dump,
    format_brain_dump_result,
    _is_task_line,
    _detect_priority,
    MIN_BRAIN_DUMP_LENGTH,
)
from src.task_pool import TaskPriority, TaskStatus


class TestIsBrainDump:
    def test_short_text_is_not(self):
        assert is_brain_dump("Привет") is False

    def test_long_text_without_structure_is_not(self):
        text = "A" * 500  # no newlines
        assert is_brain_dump(text) is False

    def test_long_structured_text_is_brain_dump(self):
        text = (
            "Планы на неделю:\n"
            "1. Настроить MCP-обёртку для CFO бота\n"
            "2. Создать контент-стратегию для LinkedIn\n"
            "3. Обновить финансовый отчёт\n"
            "4. Проверить API health мониторинг\n"
            + "x" * 200
        )
        assert is_brain_dump(text) is True

    def test_bullets_are_brain_dump(self):
        text = (
            "Что нужно сделать:\n"
            "- Подготовить бюджет на Q1\n"
            "- Настроить Threads для Кристины\n"
            "- Обновить документацию\n"
            "- Запустить мониторинг API\n"
            + "z" * 200
        )
        assert is_brain_dump(text) is True

    def test_less_than_2_task_lines_is_not(self):
        text = "1. First task\n" + "Just regular text without markers. " * 20
        assert is_brain_dump(text) is False

    def test_min_length_threshold(self):
        assert MIN_BRAIN_DUMP_LENGTH == 300


class TestIsTaskLine:
    def test_numbered_dot(self):
        assert _is_task_line("1. Сделать что-то")

    def test_numbered_paren(self):
        assert _is_task_line("2) Проверить API")

    def test_bullet_dash(self):
        assert _is_task_line("- Настроить мониторинг")

    def test_bullet_dot(self):
        assert _is_task_line("• Обновить документацию")

    def test_todo_prefix(self):
        assert _is_task_line("TODO: Починить баг")

    def test_задача_prefix(self):
        assert _is_task_line("ЗАДАЧА: Подготовить отчёт")

    def test_нужно_prefix(self):
        assert _is_task_line("Нужно обновить конфигурацию")

    def test_plain_text_not_task(self):
        assert _is_task_line("Обычный текст без маркеров") is False


class TestDetectPriority:
    def test_critical_keywords(self):
        assert _detect_priority("Срочно починить деплой") == TaskPriority.CRITICAL
        assert _detect_priority("ASAP fix") == TaskPriority.CRITICAL

    def test_high_keywords(self):
        assert _detect_priority("Важно: обновить API") == TaskPriority.HIGH

    def test_low_keywords(self):
        assert _detect_priority("Потом можно сделать") == TaskPriority.LOW
        assert _detect_priority("nice to have feature") == TaskPriority.LOW

    def test_default_medium(self):
        assert _detect_priority("Обычная задача") == TaskPriority.MEDIUM


class TestParseBrainDump:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        path = str(tmp_path / "pool.json")
        monkeypatch.setattr("src.task_pool._pool_path", lambda: path)

    def test_numbered_list(self):
        text = (
            "1. Настроить MCP-обёртку\n"
            "2. Создать контент-стратегию\n"
            "3. Обновить отчёт\n"
        )
        tasks = parse_brain_dump(text)
        assert len(tasks) == 3
        assert "MCP-обёртку" in tasks[0].title
        assert "контент-стратегию" in tasks[1].title

    def test_bullet_list(self):
        text = (
            "- Подготовить бюджет\n"
            "- Проверить API\n"
        )
        tasks = parse_brain_dump(text)
        assert len(tasks) == 2

    def test_mixed_list(self):
        text = (
            "Планы:\n"
            "1. Первая задача\n"
            "- Вторая задача\n"
            "TODO: Третья задача\n"
        )
        tasks = parse_brain_dump(text)
        assert len(tasks) == 3

    def test_multiline_task(self):
        text = (
            "1. Настроить MCP-обёртку\n"
            "   для CFO бота с финансовыми данными\n"
            "2. Создать контент\n"
        )
        tasks = parse_brain_dump(text)
        assert len(tasks) == 2
        assert "CFO бота" in tasks[0].title

    def test_short_lines_skipped(self):
        text = "1. OK\n2. Hi\n3. Настроить мониторинг API\n"
        tasks = parse_brain_dump(text)
        assert len(tasks) == 1  # first two are < 5 chars

    def test_auto_tags_applied(self):
        text = "1. Настроить MCP-обёртку для API\n"
        tasks = parse_brain_dump(text)
        assert len(tasks) == 1
        assert "mcp" in tasks[0].tags or "api" in tasks[0].tags

    def test_priority_detection(self):
        text = "1. Срочно починить деплой\n2. Потом можно обновить доки\n"
        tasks = parse_brain_dump(text)
        assert tasks[0].priority == TaskPriority.CRITICAL
        assert tasks[1].priority == TaskPriority.LOW

    def test_source_field(self):
        text = "1. Test task\n"
        tasks = parse_brain_dump(text, source="telegram")
        if tasks:
            assert tasks[0].source == "telegram"

    def test_empty_text(self):
        assert parse_brain_dump("") == []

    def test_no_tasks_found(self):
        text = "Просто длинный текст без задач, размышления о жизни и прочее."
        tasks = parse_brain_dump(text)
        assert tasks == []

    def test_tasks_persisted(self):
        from src.task_pool import get_all_tasks
        text = "1. Задача раз\n2. Задача два\n"
        parse_brain_dump(text)
        all_tasks = get_all_tasks()
        assert len(all_tasks) == 2


class TestFormatBrainDumpResult:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        path = str(tmp_path / "pool.json")
        monkeypatch.setattr("src.task_pool._pool_path", lambda: path)

    def test_empty_result(self):
        result = format_brain_dump_result([])
        assert "Не удалось" in result

    def test_with_tasks(self):
        text = "1. Настроить MCP\n2. Создать контент\n"
        tasks = parse_brain_dump(text)
        result = format_brain_dump_result(tasks)
        assert "Brain Dump" in result
        assert "2 задач" in result

    def test_includes_suggestions(self):
        text = "1. Настроить MCP инфраструктуру\n"
        tasks = parse_brain_dump(text)
        result = format_brain_dump_result(tasks)
        # Should suggest automator for MCP
        assert "automator" in result or "💡" in result
