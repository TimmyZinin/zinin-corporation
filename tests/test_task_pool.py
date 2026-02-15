"""Tests for src/task_pool.py — Shared Task Pool with Dependency Engine."""

import json
import os
import pytest
from unittest.mock import patch, MagicMock

from src.task_pool import (
    TaskStatus,
    TaskPriority,
    PoolTask,
    auto_tag,
    suggest_assignee,
    AGENT_TAGS,
    ESCALATION_THRESHOLD,
    create_task,
    assign_task,
    start_task,
    complete_task,
    block_task,
    delete_task,
    get_all_tasks,
    get_task,
    get_tasks_by_status,
    get_tasks_by_assignee,
    get_ready_tasks,
    get_blocked_tasks,
    get_pool_summary,
    format_task_summary,
    format_pool_summary,
    archive_done_tasks,
    get_archived_tasks,
    get_archive_stats,
    get_stale_tasks,
    format_stale_report,
    _archive_dir,
    _load_pool,
    _save_pool,
    _pool_path,
    _find_task,
    _get_unmet_deps,
    _run_dependency_engine,
    _short_id,
)


# ──────────────────────────────────────────────────────────
# Model tests
# ──────────────────────────────────────────────────────────

class TestTaskStatus:
    def test_all_statuses_exist(self):
        assert TaskStatus.TODO == "TODO"
        assert TaskStatus.ASSIGNED == "ASSIGNED"
        assert TaskStatus.IN_PROGRESS == "IN_PROGRESS"
        assert TaskStatus.DONE == "DONE"
        assert TaskStatus.BLOCKED == "BLOCKED"

    def test_status_count(self):
        assert len(TaskStatus) == 5

    def test_status_is_string(self):
        assert isinstance(TaskStatus.TODO, str)
        assert TaskStatus.TODO == "TODO"


class TestTaskPriority:
    def test_priority_values(self):
        assert TaskPriority.CRITICAL == 1
        assert TaskPriority.HIGH == 2
        assert TaskPriority.MEDIUM == 3
        assert TaskPriority.LOW == 4


class TestPoolTask:
    def test_default_values(self):
        t = PoolTask(title="Test")
        assert t.title == "Test"
        assert t.status == TaskStatus.TODO
        assert t.assignee == ""
        assert t.priority == TaskPriority.MEDIUM
        assert t.blocked_by == []
        assert t.blocks == []
        assert t.tags == []
        assert t.result is None
        assert t.completed_at is None
        assert len(t.id) == 8

    def test_custom_values(self):
        t = PoolTask(
            title="MCP обёртка",
            priority=TaskPriority.CRITICAL,
            tags=["mcp", "infrastructure"],
            blocked_by=["abc123"],
            assignee="automator",
        )
        assert t.priority == 1
        assert t.tags == ["mcp", "infrastructure"]
        assert t.blocked_by == ["abc123"]
        assert t.assignee == "automator"

    def test_short_id_unique(self):
        ids = {_short_id() for _ in range(100)}
        assert len(ids) == 100

    def test_model_dump_roundtrip(self):
        t = PoolTask(title="Test", tags=["code"])
        d = t.model_dump()
        t2 = PoolTask(**d)
        assert t2.title == t.title
        assert t2.id == t.id
        assert t2.tags == t.tags


# ──────────────────────────────────────────────────────────
# Auto-tag tests
# ──────────────────────────────────────────────────────────

class TestAutoTag:
    def test_finance_tags(self):
        tags = auto_tag("Подготовить финансовый отчёт по бюджету")
        assert "finance" in tags

    def test_crypto_tags(self):
        tags = auto_tag("Проверить крипто-портфель BTC")
        assert "crypto" in tags

    def test_content_tags(self):
        tags = auto_tag("Написать контент для публикации")
        assert "content" in tags

    def test_linkedin_tags(self):
        tags = auto_tag("Пост для LinkedIn про AI")
        assert "linkedin" in tags

    def test_mcp_tags(self):
        tags = auto_tag("MCP-обёртка для CFO-бота")
        assert "mcp" in tags

    def test_multiple_tags(self):
        tags = auto_tag("MCP-обёртка для API интеграции")
        assert "mcp" in tags
        assert "api" in tags

    def test_empty_string(self):
        assert auto_tag("") == []

    def test_no_match(self):
        assert auto_tag("xyzzy foobar") == []

    def test_case_insensitive(self):
        tags = auto_tag("LINKEDIN пост")
        assert "linkedin" in tags

    def test_threads_tag(self):
        assert "threads" in auto_tag("Публикация в Threads")

    def test_product_tags(self):
        tags = auto_tag("Обновить бэклог продукта")
        assert "product" in tags

    def test_design_tags(self):
        tags = auto_tag("Создать инфографику для статьи")
        assert "design" in tags

    def test_seo_tags(self):
        tags = auto_tag("SEO оптимизация лендинга")
        assert "seo" in tags

    def test_hitl_tags(self):
        tags = auto_tag("Утвердить контент перед публикацией")
        assert "hitl" in tags

    def test_monitoring_tags(self):
        tags = auto_tag("Настроить мониторинг и алерты")
        assert "monitoring" in tags

    def test_sorted_output(self):
        tags = auto_tag("MCP API интеграция инфраструктура")
        assert tags == sorted(tags)

    def test_no_duplicates(self):
        tags = auto_tag("API api API")
        assert tags.count("api") == 1


# ──────────────────────────────────────────────────────────
# Agent Tag Router tests
# ──────────────────────────────────────────────────────────

class TestSuggestAssignee:
    def test_mcp_goes_to_automator(self):
        result = suggest_assignee(["mcp", "infrastructure"])
        assert result[0][0] == "automator"

    def test_content_goes_to_smm(self):
        result = suggest_assignee(["content", "linkedin"])
        assert result[0][0] == "smm"

    def test_finance_goes_to_accountant(self):
        result = suggest_assignee(["finance", "revenue"])
        assert result[0][0] == "accountant"

    def test_design_goes_to_designer(self):
        result = suggest_assignee(["design", "visual"])
        assert result[0][0] == "designer"

    def test_product_goes_to_cpo(self):
        result = suggest_assignee(["product", "backlog"])
        assert result[0][0] == "cpo"

    def test_strategy_goes_to_manager(self):
        result = suggest_assignee(["strategy", "planning"])
        assert result[0][0] == "manager"

    def test_empty_tags(self):
        assert suggest_assignee([]) == []

    def test_unknown_tag(self):
        result = suggest_assignee(["xyzzy"])
        assert result == []

    def test_confidence_sorting(self):
        result = suggest_assignee(["finance", "revenue", "crypto"])
        # accountant should have highest confidence
        assert result[0][0] == "accountant"
        assert result[0][1] >= result[-1][1]

    def test_multiple_matches(self):
        result = suggest_assignee(["code", "content"])
        agents = [r[0] for r in result]
        assert "automator" in agents
        assert "smm" in agents

    def test_confidence_value(self):
        result = suggest_assignee(["finance"])
        # finance matches accountant → 1.0
        assert result[0][1] == 1.0

    def test_partial_confidence(self):
        result = suggest_assignee(["finance", "xyzzy"])
        # 1 out of 2 tags match → 0.5
        assert result[0][1] == 0.5

    def test_all_agents_have_tags(self):
        for agent_key, tags in AGENT_TAGS.items():
            assert len(tags) > 0, f"{agent_key} has no tags"


# ──────────────────────────────────────────────────────────
# Persistence tests
# ──────────────────────────────────────────────────────────

class TestPersistence:
    def test_pool_path_returns_string(self):
        path = _pool_path()
        assert isinstance(path, str)
        assert path.endswith("task_pool.json")

    def test_load_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.task_pool._pool_path", lambda: str(tmp_path / "pool.json"))
        assert _load_pool() == []

    def test_save_and_load(self, tmp_path, monkeypatch):
        path = str(tmp_path / "pool.json")
        monkeypatch.setattr("src.task_pool._pool_path", lambda: path)
        tasks = [{"id": "abc", "title": "Test", "status": "TODO"}]
        _save_pool(tasks)
        loaded = _load_pool()
        assert len(loaded) == 1
        assert loaded[0]["id"] == "abc"

    def test_save_creates_dir(self, tmp_path, monkeypatch):
        path = str(tmp_path / "subdir" / "pool.json")
        monkeypatch.setattr("src.task_pool._pool_path", lambda: path)
        _save_pool([{"id": "x"}])
        assert os.path.exists(path)

    def test_load_corrupted_file(self, tmp_path, monkeypatch):
        path = str(tmp_path / "pool.json")
        monkeypatch.setattr("src.task_pool._pool_path", lambda: path)
        with open(path, "w") as f:
            f.write("not json")
        assert _load_pool() == []

    def test_load_non_list(self, tmp_path, monkeypatch):
        path = str(tmp_path / "pool.json")
        monkeypatch.setattr("src.task_pool._pool_path", lambda: path)
        with open(path, "w") as f:
            json.dump({"key": "value"}, f)
        assert _load_pool() == []

    def test_find_task_found(self):
        tasks = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        assert _find_task(tasks, "b") == {"id": "b"}

    def test_find_task_not_found(self):
        tasks = [{"id": "a"}]
        assert _find_task(tasks, "z") is None

    def test_find_task_empty(self):
        assert _find_task([], "a") is None


# ──────────────────────────────────────────────────────────
# CRUD tests
# ──────────────────────────────────────────────────────────

class TestCreateTask:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        path = str(tmp_path / "pool.json")
        monkeypatch.setattr("src.task_pool._pool_path", lambda: path)

    def test_basic_create(self):
        task = create_task("Test task")
        assert task.title == "Test task"
        assert task.status == TaskStatus.TODO
        assert len(task.id) == 8

    def test_auto_tags(self):
        task = create_task("MCP-обёртка для API")
        assert "mcp" in task.tags
        assert "api" in task.tags

    def test_explicit_tags(self):
        task = create_task("Custom", tags=["a", "b"])
        assert task.tags == ["a", "b"]

    def test_persisted(self):
        create_task("Persisted task")
        pool = _load_pool()
        assert len(pool) == 1
        assert pool[0]["title"] == "Persisted task"

    def test_with_assignee(self):
        task = create_task("Assigned", assignee="smm")
        assert task.status == TaskStatus.ASSIGNED
        assert task.assignee == "smm"
        assert task.assigned_at is not None

    def test_with_blocked_by(self):
        t1 = create_task("First")
        t2 = create_task("Second", blocked_by=[t1.id])
        assert t2.status == TaskStatus.BLOCKED
        assert t1.id in t2.blocked_by

    def test_blocked_sets_reverse_blocks(self):
        t1 = create_task("First")
        t2 = create_task("Second", blocked_by=[t1.id])
        # Reload t1 from pool to check blocks was added
        pool = _load_pool()
        t1_raw = _find_task(pool, t1.id)
        assert t2.id in t1_raw["blocks"]

    def test_priority(self):
        task = create_task("Critical", priority=TaskPriority.CRITICAL)
        assert task.priority == 1

    def test_source(self):
        task = create_task("From TG", source="telegram")
        assert task.source == "telegram"

    def test_multiple_tasks(self):
        for i in range(5):
            create_task(f"Task {i}")
        assert len(_load_pool()) == 5


class TestAssignTask:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        path = str(tmp_path / "pool.json")
        monkeypatch.setattr("src.task_pool._pool_path", lambda: path)

    def test_basic_assign(self):
        t = create_task("Task")
        result = assign_task(t.id, "accountant")
        assert result.status == TaskStatus.ASSIGNED
        assert result.assignee == "accountant"
        assert result.assigned_by == "ceo-alexey"

    def test_assign_nonexistent(self):
        assert assign_task("nonexistent", "smm") is None

    def test_assign_done_task(self):
        t = create_task("Task", assignee="smm")
        start_task(t.id)
        complete_task(t.id)
        assert assign_task(t.id, "automator") is None

    def test_assign_blocked_task(self):
        t1 = create_task("Dep")
        t2 = create_task("Blocked", blocked_by=[t1.id])
        result = assign_task(t2.id, "smm")
        assert result.status == TaskStatus.BLOCKED  # stays blocked
        assert result.assignee == "smm"

    def test_custom_assigned_by(self):
        t = create_task("Task")
        result = assign_task(t.id, "smm", assigned_by="tim")
        assert result.assigned_by == "tim"


class TestStartTask:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        path = str(tmp_path / "pool.json")
        monkeypatch.setattr("src.task_pool._pool_path", lambda: path)

    def test_basic_start(self):
        t = create_task("Task", assignee="smm")
        result = start_task(t.id)
        assert result.status == TaskStatus.IN_PROGRESS

    def test_start_todo_fails(self):
        t = create_task("Task")
        assert start_task(t.id) is None

    def test_start_nonexistent(self):
        assert start_task("nonexistent") is None


class TestCompleteTask:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        path = str(tmp_path / "pool.json")
        monkeypatch.setattr("src.task_pool._pool_path", lambda: path)

    def test_basic_complete(self):
        t = create_task("Task", assignee="smm")
        start_task(t.id)
        result = complete_task(t.id, result="Done!")
        assert result.status == TaskStatus.DONE
        assert result.result == "Done!"
        assert result.completed_at is not None

    def test_complete_from_assigned(self):
        t = create_task("Task", assignee="smm")
        result = complete_task(t.id)
        assert result.status == TaskStatus.DONE

    def test_complete_todo_fails(self):
        t = create_task("Task")
        assert complete_task(t.id) is None

    def test_complete_nonexistent(self):
        assert complete_task("nonexistent") is None


class TestBlockTask:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        path = str(tmp_path / "pool.json")
        monkeypatch.setattr("src.task_pool._pool_path", lambda: path)

    def test_block(self):
        t = create_task("Task", assignee="smm")
        result = block_task(t.id)
        assert result.status == TaskStatus.BLOCKED

    def test_block_nonexistent(self):
        assert block_task("nonexistent") is None


class TestDeleteTask:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        path = str(tmp_path / "pool.json")
        monkeypatch.setattr("src.task_pool._pool_path", lambda: path)

    def test_delete(self):
        t = create_task("Task")
        assert delete_task(t.id) is True
        assert len(_load_pool()) == 0

    def test_delete_nonexistent(self):
        assert delete_task("nonexistent") is False

    def test_delete_cleans_blocked_by(self):
        t1 = create_task("Dep")
        t2 = create_task("Blocked", blocked_by=[t1.id])
        delete_task(t1.id)
        pool = _load_pool()
        t2_raw = _find_task(pool, t2.id)
        assert t1.id not in t2_raw.get("blocked_by", [])

    def test_delete_cleans_blocks(self):
        t1 = create_task("Dep")
        t2 = create_task("Blocked", blocked_by=[t1.id])
        delete_task(t2.id)
        pool = _load_pool()
        t1_raw = _find_task(pool, t1.id)
        assert t2.id not in t1_raw.get("blocks", [])


# ──────────────────────────────────────────────────────────
# Dependency Engine tests
# ──────────────────────────────────────────────────────────

class TestDependencyEngine:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        path = str(tmp_path / "pool.json")
        monkeypatch.setattr("src.task_pool._pool_path", lambda: path)

    def test_complete_unblocks_dependent(self):
        t1 = create_task("First", assignee="automator")
        t2 = create_task("Second", blocked_by=[t1.id], assignee="smm")
        assert get_task(t2.id).status == TaskStatus.BLOCKED

        start_task(t1.id)
        complete_task(t1.id)

        t2_after = get_task(t2.id)
        assert t2_after.status == TaskStatus.ASSIGNED

    def test_complete_does_not_unblock_with_remaining_deps(self):
        t1 = create_task("Dep1", assignee="automator")
        t2 = create_task("Dep2", assignee="smm")
        t3 = create_task("Blocked", blocked_by=[t1.id, t2.id], assignee="cpo")

        start_task(t1.id)
        complete_task(t1.id)

        t3_after = get_task(t3.id)
        assert t3_after.status == TaskStatus.BLOCKED
        assert t2.id in t3_after.blocked_by
        assert t1.id not in t3_after.blocked_by

    def test_chain_unblock(self):
        """A → B → C chain of dependencies."""
        a = create_task("A", assignee="automator")
        b = create_task("B", blocked_by=[a.id], assignee="smm")
        c = create_task("C", blocked_by=[b.id], assignee="cpo")

        # Complete A → B unblocked
        start_task(a.id)
        complete_task(a.id)
        assert get_task(b.id).status == TaskStatus.ASSIGNED
        assert get_task(c.id).status == TaskStatus.BLOCKED

        # Complete B → C unblocked
        start_task(b.id)
        complete_task(b.id)
        assert get_task(c.id).status == TaskStatus.ASSIGNED

    def test_unblock_to_todo_when_no_assignee(self):
        t1 = create_task("Dep", assignee="automator")
        t2 = create_task("Unassigned", blocked_by=[t1.id])
        assert get_task(t2.id).status == TaskStatus.BLOCKED

        start_task(t1.id)
        complete_task(t1.id)

        t2_after = get_task(t2.id)
        assert t2_after.status == TaskStatus.TODO

    def test_missing_dependency_treated_as_met(self):
        """If a dependency task doesn't exist, treat as satisfied."""
        pool = [
            {"id": "t1", "title": "T1", "status": "BLOCKED",
             "blocked_by": ["nonexistent"], "assignee": "smm",
             "blocks": [], "tags": [], "priority": 3,
             "created_at": "", "assigned_at": None,
             "completed_at": None, "result": None,
             "assigned_by": "", "source": ""},
        ]
        unmet = _get_unmet_deps(pool, pool[0])
        assert unmet == []

    def test_fan_out_unblock(self):
        """One task unblocks multiple dependents."""
        dep = create_task("Dep", assignee="automator")
        t1 = create_task("Fan1", blocked_by=[dep.id], assignee="smm")
        t2 = create_task("Fan2", blocked_by=[dep.id], assignee="cpo")
        t3 = create_task("Fan3", blocked_by=[dep.id], assignee="designer")

        start_task(dep.id)
        complete_task(dep.id)

        assert get_task(t1.id).status == TaskStatus.ASSIGNED
        assert get_task(t2.id).status == TaskStatus.ASSIGNED
        assert get_task(t3.id).status == TaskStatus.ASSIGNED


# ──────────────────────────────────────────────────────────
# Query tests
# ──────────────────────────────────────────────────────────

class TestQueries:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        path = str(tmp_path / "pool.json")
        monkeypatch.setattr("src.task_pool._pool_path", lambda: path)

    def test_get_all_tasks(self):
        create_task("A")
        create_task("B")
        assert len(get_all_tasks()) == 2

    def test_get_task(self):
        t = create_task("A")
        found = get_task(t.id)
        assert found.title == "A"

    def test_get_task_not_found(self):
        assert get_task("nonexistent") is None

    def test_get_tasks_by_status(self):
        create_task("A")
        create_task("B", assignee="smm")
        todos = get_tasks_by_status(TaskStatus.TODO)
        assigned = get_tasks_by_status(TaskStatus.ASSIGNED)
        assert len(todos) == 1
        assert len(assigned) == 1

    def test_get_tasks_by_assignee(self):
        create_task("A", assignee="smm")
        create_task("B", assignee="smm")
        create_task("C", assignee="automator")
        assert len(get_tasks_by_assignee("smm")) == 2
        assert len(get_tasks_by_assignee("automator")) == 1
        assert len(get_tasks_by_assignee("unknown")) == 0

    def test_get_ready_tasks(self):
        t1 = create_task("Ready")
        t2 = create_task("Blocked dep", assignee="automator")
        t3 = create_task("Blocked", blocked_by=[t2.id])
        ready = get_ready_tasks()
        ids = [t.id for t in ready]
        assert t1.id in ids
        assert t3.id not in ids

    def test_get_ready_tasks_sorted_by_priority(self):
        create_task("Low", priority=TaskPriority.LOW)
        create_task("Critical", priority=TaskPriority.CRITICAL)
        create_task("Medium", priority=TaskPriority.MEDIUM)
        ready = get_ready_tasks()
        priorities = [t.priority for t in ready]
        assert priorities == sorted(priorities)

    def test_get_blocked_tasks(self):
        t1 = create_task("Dep", assignee="smm")
        t2 = create_task("Blocked", blocked_by=[t1.id])
        blocked = get_blocked_tasks()
        assert len(blocked) == 1
        assert blocked[0].id == t2.id

    def test_get_pool_summary(self):
        create_task("A")
        create_task("B", assignee="smm")
        s = get_pool_summary()
        assert s["TODO"] == 1
        assert s["ASSIGNED"] == 1
        assert s["total"] == 2

    def test_get_pool_summary_empty(self):
        s = get_pool_summary()
        assert s["total"] == 0


# ──────────────────────────────────────────────────────────
# Formatting tests
# ──────────────────────────────────────────────────────────

class TestFormatting:
    def test_format_task_summary(self):
        t = PoolTask(title="MCP обёртка", tags=["mcp"], assignee="automator")
        text = format_task_summary(t)
        assert "MCP обёртка" in text
        assert "automator" in text
        assert "mcp" in text

    def test_format_task_summary_blocked(self):
        t = PoolTask(title="Blocked", status=TaskStatus.BLOCKED, blocked_by=["abc"])
        text = format_task_summary(t)
        assert "🚫" in text
        assert "abc" in text

    def test_format_task_summary_done(self):
        t = PoolTask(title="Done", status=TaskStatus.DONE)
        text = format_task_summary(t)
        assert "✅" in text

    def test_format_pool_summary_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.task_pool._pool_path", lambda: str(tmp_path / "p.json"))
        text = format_pool_summary()
        assert "пуст" in text

    def test_format_pool_summary_with_tasks(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.task_pool._pool_path", lambda: str(tmp_path / "p.json"))
        create_task("A")
        create_task("B", assignee="smm")
        text = format_pool_summary()
        assert "Task Pool" in text
        assert "TODO" in text
        assert "ASSIGNED" in text

    def test_priority_emoji(self):
        for p, emoji in [(1, "🔴"), (2, "🟠"), (3, "🟡"), (4, "🟢")]:
            t = PoolTask(title="X", priority=p)
            text = format_task_summary(t)
            assert emoji in text


# ──────────────────────────────────────────────────────────
# Status transition flow tests
# ──────────────────────────────────────────────────────────

class TestStatusFlow:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        path = str(tmp_path / "pool.json")
        monkeypatch.setattr("src.task_pool._pool_path", lambda: path)

    def test_full_lifecycle(self):
        """TODO → ASSIGNED → IN_PROGRESS → DONE."""
        t = create_task("Full lifecycle")
        assert t.status == TaskStatus.TODO

        t = assign_task(t.id, "smm")
        assert t.status == TaskStatus.ASSIGNED

        t = start_task(t.id)
        assert t.status == TaskStatus.IN_PROGRESS

        t = complete_task(t.id, result="All done")
        assert t.status == TaskStatus.DONE
        assert t.result == "All done"

    def test_blocked_lifecycle(self):
        """BLOCKED → ASSIGNED (after dep completes) → IN_PROGRESS → DONE."""
        dep = create_task("Dependency", assignee="automator")
        t = create_task("Blocked", blocked_by=[dep.id], assignee="smm")
        assert t.status == TaskStatus.BLOCKED

        start_task(dep.id)
        complete_task(dep.id)

        t = get_task(t.id)
        assert t.status == TaskStatus.ASSIGNED

        t = start_task(t.id)
        assert t.status == TaskStatus.IN_PROGRESS

        t = complete_task(t.id)
        assert t.status == TaskStatus.DONE

    def test_manual_block_and_reassign(self):
        """ASSIGNED → manual BLOCK → re-assign → ASSIGNED."""
        t = create_task("Task", assignee="smm")
        block_task(t.id)
        assert get_task(t.id).status == TaskStatus.BLOCKED

        result = assign_task(t.id, "automator")
        # Re-assigning blocked task keeps BLOCKED (no unmet deps cleared)
        # Actually blocked_by is empty, so it becomes ASSIGNED
        assert result.status == TaskStatus.ASSIGNED
        assert result.assignee == "automator"


# ──────────────────────────────────────────────────────────
# updated_at tracking
# ──────────────────────────────────────────────────────────

class TestUpdatedAt:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        path = str(tmp_path / "pool.json")
        monkeypatch.setattr("src.task_pool._pool_path", lambda: path)

    def test_create_sets_updated_at(self):
        t = create_task("Test")
        assert t.updated_at is not None

    def test_assign_updates_updated_at(self):
        t = create_task("Test")
        old = t.updated_at
        result = assign_task(t.id, "smm")
        assert result.updated_at >= old

    def test_start_updates_updated_at(self):
        t = create_task("Test", assignee="smm")
        result = start_task(t.id)
        assert result.updated_at is not None

    def test_complete_updates_updated_at(self):
        t = create_task("Test", assignee="smm")
        start_task(t.id)
        result = complete_task(t.id)
        assert result.updated_at is not None

    def test_block_updates_updated_at(self):
        t = create_task("Test", assignee="smm")
        result = block_task(t.id)
        assert result.updated_at is not None


# ──────────────────────────────────────────────────────────
# Archive tests
# ──────────────────────────────────────────────────────────

class TestArchive:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        pool_path = str(tmp_path / "pool.json")
        arc_dir = str(tmp_path / "archive")
        monkeypatch.setattr("src.task_pool._pool_path", lambda: pool_path)
        monkeypatch.setattr("src.task_pool._archive_dir", lambda: arc_dir)
        self.arc_dir = arc_dir

    def test_archive_moves_done_tasks(self):
        from datetime import datetime, timedelta
        t = create_task("Done task", assignee="smm")
        complete_task(t.id)
        # Manually backdate the completed_at
        pool = _load_pool()
        pool[0]["completed_at"] = (datetime.now() - timedelta(days=5)).isoformat()
        _save_pool(pool)

        count = archive_done_tasks(keep_recent_days=1)
        assert count == 1
        assert len(get_all_tasks()) == 0

    def test_archive_keeps_recent_done(self):
        t = create_task("Recent done", assignee="smm")
        complete_task(t.id)
        count = archive_done_tasks(keep_recent_days=1)
        assert count == 0
        assert len(get_all_tasks()) == 1

    def test_archive_keeps_non_done(self):
        create_task("TODO task")
        count = archive_done_tasks(keep_recent_days=0)
        assert count == 0

    def test_get_archived_tasks(self):
        from datetime import datetime, timedelta
        t = create_task("Archived", assignee="smm")
        complete_task(t.id)
        pool = _load_pool()
        yesterday = datetime.now() - timedelta(days=2)
        pool[0]["completed_at"] = yesterday.isoformat()
        _save_pool(pool)

        archive_done_tasks(keep_recent_days=1)
        date_str = yesterday.strftime("%Y-%m-%d")
        archived = get_archived_tasks(date_str)
        assert len(archived) == 1
        assert archived[0].title == "Archived"

    def test_get_archived_tasks_nonexistent_date(self):
        assert get_archived_tasks("2020-01-01") == []

    def test_get_archive_stats_empty(self):
        stats = get_archive_stats()
        assert stats["files"] == 0
        assert stats["total_tasks"] == 0

    def test_get_archive_stats(self):
        from datetime import datetime, timedelta
        t = create_task("Stat task", assignee="smm")
        complete_task(t.id)
        pool = _load_pool()
        pool[0]["completed_at"] = (datetime.now() - timedelta(days=3)).isoformat()
        _save_pool(pool)
        archive_done_tasks(keep_recent_days=1)

        stats = get_archive_stats()
        assert stats["files"] == 1
        assert stats["total_tasks"] == 1
        assert len(stats["dates"]) == 1

    def test_archive_appends_to_existing_file(self):
        from datetime import datetime, timedelta
        target_date = datetime.now() - timedelta(days=5)

        t1 = create_task("First", assignee="smm")
        complete_task(t1.id)
        pool = _load_pool()
        pool[0]["completed_at"] = target_date.isoformat()
        _save_pool(pool)
        archive_done_tasks(keep_recent_days=1)

        t2 = create_task("Second", assignee="smm")
        complete_task(t2.id)
        pool = _load_pool()
        pool[0]["completed_at"] = target_date.isoformat()
        _save_pool(pool)
        archive_done_tasks(keep_recent_days=1)

        date_str = target_date.strftime("%Y-%m-%d")
        archived = get_archived_tasks(date_str)
        assert len(archived) == 2

    def test_archive_returns_zero_when_nothing_to_archive(self):
        count = archive_done_tasks(keep_recent_days=1)
        assert count == 0


# ──────────────────────────────────────────────────────────
# Stale task detection tests
# ──────────────────────────────────────────────────────────

class TestStaleTasks:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        path = str(tmp_path / "pool.json")
        monkeypatch.setattr("src.task_pool._pool_path", lambda: path)

    def test_no_stale_tasks(self):
        create_task("Fresh", assignee="smm")
        assert get_stale_tasks(stale_days=3) == []

    def test_stale_assigned_task(self):
        from datetime import datetime, timedelta
        t = create_task("Stale", assignee="smm")
        # Backdate updated_at
        pool = _load_pool()
        pool[0]["updated_at"] = (datetime.now() - timedelta(days=5)).isoformat()
        _save_pool(pool)

        stale = get_stale_tasks(stale_days=3)
        assert len(stale) == 1
        assert stale[0].id == t.id

    def test_stale_in_progress_task(self):
        from datetime import datetime, timedelta
        t = create_task("In progress stale", assignee="smm")
        start_task(t.id)
        pool = _load_pool()
        pool[0]["updated_at"] = (datetime.now() - timedelta(days=4)).isoformat()
        _save_pool(pool)

        stale = get_stale_tasks(stale_days=3)
        assert len(stale) == 1

    def test_done_not_stale(self):
        from datetime import datetime, timedelta
        t = create_task("Done", assignee="smm")
        complete_task(t.id)
        pool = _load_pool()
        pool[0]["updated_at"] = (datetime.now() - timedelta(days=10)).isoformat()
        _save_pool(pool)

        assert get_stale_tasks(stale_days=3) == []

    def test_todo_not_stale(self):
        from datetime import datetime, timedelta
        create_task("Todo")
        pool = _load_pool()
        pool[0]["updated_at"] = (datetime.now() - timedelta(days=10)).isoformat()
        _save_pool(pool)

        assert get_stale_tasks(stale_days=3) == []

    def test_stale_sorted_by_priority(self):
        from datetime import datetime, timedelta
        old = (datetime.now() - timedelta(days=5)).isoformat()
        create_task("Low", assignee="smm", priority=TaskPriority.LOW)
        create_task("Critical", assignee="smm", priority=TaskPriority.CRITICAL)
        pool = _load_pool()
        for t in pool:
            t["updated_at"] = old
        _save_pool(pool)

        stale = get_stale_tasks(stale_days=3)
        assert stale[0].priority == TaskPriority.CRITICAL
        assert stale[1].priority == TaskPriority.LOW

    def test_format_stale_report_empty(self):
        report = format_stale_report([])
        assert "orphan'ов нет" in report

    def test_format_stale_report_with_tasks(self):
        t = PoolTask(title="Stale task", assignee="smm", status=TaskStatus.ASSIGNED)
        report = format_stale_report([t])
        assert "Stale task" in report
        assert "smm" in report


# ──────────────────────────────────────────────────────────
# Escalation threshold
# ──────────────────────────────────────────────────────────

class TestEscalation:
    def test_threshold_value(self):
        assert ESCALATION_THRESHOLD == 0.3

    def test_known_tags_above_threshold(self):
        suggestions = suggest_assignee(["finance"])
        assert suggestions and suggestions[0][1] >= ESCALATION_THRESHOLD

    def test_unknown_tags_no_match(self):
        suggestions = suggest_assignee(["xxxxxx"])
        assert len(suggestions) == 0


# ──────────────────────────────────────────────────────────
# EventBus integration tests
# ──────────────────────────────────────────────────────────

class TestTaskPoolEventBus:
    """Verify that Task Pool CRUD operations emit EventBus events."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        from src.event_bus import reset_event_bus
        reset_event_bus()
        path = str(tmp_path / "pool.json")
        monkeypatch.setattr("src.task_pool._pool_path", lambda: path)
        yield
        reset_event_bus()

    def test_create_task_emits_event(self):
        from src.event_bus import get_event_bus, TASK_CREATED
        bus = get_event_bus()
        received = []
        bus.on(TASK_CREATED, lambda e: received.append(e))

        task = create_task("финансовый отчёт", source="test")
        assert len(received) == 1
        assert received[0].payload["task_id"] == task.id
        assert received[0].payload["title"] == "финансовый отчёт"

    def test_assign_task_emits_event(self):
        from src.event_bus import get_event_bus, TASK_ASSIGNED
        bus = get_event_bus()
        received = []
        bus.on(TASK_ASSIGNED, lambda e: received.append(e))

        task = create_task("test task", source="test")
        assign_task(task.id, "accountant")
        assert len(received) == 1
        assert received[0].payload["assignee"] == "accountant"

    def test_start_task_emits_event(self):
        from src.event_bus import get_event_bus, TASK_STARTED
        bus = get_event_bus()
        received = []
        bus.on(TASK_STARTED, lambda e: received.append(e))

        task = create_task("test", source="test")
        assign_task(task.id, "smm")
        start_task(task.id)
        assert len(received) == 1
        assert received[0].payload["assignee"] == "smm"

    def test_complete_task_emits_event(self):
        from src.event_bus import get_event_bus, TASK_COMPLETED
        bus = get_event_bus()
        received = []
        bus.on(TASK_COMPLETED, lambda e: received.append(e))

        task = create_task("test", source="test")
        assign_task(task.id, "smm")
        start_task(task.id)
        complete_task(task.id, result="done")
        assert len(received) == 1
        assert received[0].payload["task_id"] == task.id
        assert received[0].payload["result"] == "done"

    def test_complete_task_emits_unblocked(self):
        from src.event_bus import get_event_bus, TASK_UNBLOCKED
        bus = get_event_bus()
        unblocked_events = []
        bus.on(TASK_UNBLOCKED, lambda e: unblocked_events.append(e))

        # Create blocker task
        blocker = create_task("blocker", source="test")
        assign_task(blocker.id, "automator")

        # Create dependent task blocked by blocker
        dependent = create_task(
            "dependent", source="test",
            blocked_by=[blocker.id], assignee="smm",
        )

        # Complete blocker → should unblock dependent
        start_task(blocker.id)
        complete_task(blocker.id, result="done")

        assert len(unblocked_events) == 1
        assert unblocked_events[0].payload["task_id"] == dependent.id
        assert unblocked_events[0].payload["assignee"] == "smm"
        assert unblocked_events[0].payload["unblocked_by"] == blocker.id

    def test_complete_unblocked_has_title(self):
        from src.event_bus import get_event_bus, TASK_UNBLOCKED
        bus = get_event_bus()
        events = []
        bus.on(TASK_UNBLOCKED, lambda e: events.append(e))

        blocker = create_task("step one", source="test")
        assign_task(blocker.id, "automator")
        create_task("step two", source="test", blocked_by=[blocker.id], assignee="smm")

        start_task(blocker.id)
        complete_task(blocker.id)

        assert events[0].payload["title"] == "step two"

    def test_no_event_on_invalid_complete(self):
        from src.event_bus import get_event_bus, TASK_COMPLETED
        bus = get_event_bus()
        received = []
        bus.on(TASK_COMPLETED, lambda e: received.append(e))

        complete_task("nonexistent")
        assert len(received) == 0

    def test_assign_nonexistent_no_event(self):
        from src.event_bus import get_event_bus, TASK_ASSIGNED
        bus = get_event_bus()
        received = []
        bus.on(TASK_ASSIGNED, lambda e: received.append(e))

        assign_task("nonexistent", "smm")
        assert len(received) == 0


# ── Checkpoint & Retry fields ──


class TestCheckpointFields:
    def test_set_checkpoint(self):
        from src.task_pool import set_checkpoint
        task = create_task("Test checkpoint")
        assert set_checkpoint(task.id, "started") is True
        updated = get_task(task.id)
        assert updated.checkpoint == "started"

    def test_set_checkpoint_nonexistent(self):
        from src.task_pool import set_checkpoint
        assert set_checkpoint("nonexistent", "started") is False

    def test_increment_retry(self):
        from src.task_pool import increment_retry
        task = create_task("Test retry")
        assert task.retry_count == 0
        assert increment_retry(task.id) == 1
        assert increment_retry(task.id) == 2
        updated = get_task(task.id)
        assert updated.retry_count == 2

    def test_increment_retry_nonexistent(self):
        from src.task_pool import increment_retry
        assert increment_retry("nonexistent") == -1

    def test_checkpoint_default_empty(self):
        task = create_task("No checkpoint")
        assert task.checkpoint == ""
        assert task.retry_count == 0
