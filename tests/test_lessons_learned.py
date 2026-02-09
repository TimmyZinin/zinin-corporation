"""Tests for src/lessons_learned.py — Lessons Learned System."""

import sys
import os
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.lessons_learned import (
    CATEGORIES,
    Lesson,
    LessonsStore,
    add_lesson,
    get_lessons,
    get_lessons_for_context,
    get_all_lessons,
    get_lesson_stats,
    mark_useful,
    delete_lesson,
    MAX_LESSONS,
    _load_store,
    _save_store,
)


def _tmp_store():
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    f.close()
    return f.name


# ── Models ────────────────────────────────────────────────

class TestModels:
    def test_lesson_defaults(self):
        l = Lesson(summary="Test lesson")
        assert l.summary == "Test lesson"
        assert l.agent == ""
        assert l.category == "other"
        assert l.useful_count == 0
        assert l.timestamp != ""

    def test_lesson_with_all_fields(self):
        l = Lesson(
            id="L0001",
            agent="manager",
            category="quality",
            summary="Test",
            detail="Detail",
            action="Do X",
            task_context="Task Y",
        )
        assert l.id == "L0001"
        assert l.agent == "manager"
        assert l.category == "quality"

    def test_lessons_store_defaults(self):
        store = LessonsStore()
        assert store.lessons == []
        assert store.next_id == 1

    def test_categories_defined(self):
        assert len(CATEGORIES) >= 7
        assert "quality" in CATEGORIES
        assert "tool_usage" in CATEGORIES
        assert "data" in CATEGORIES
        assert "other" in CATEGORIES


# ── Add Lesson ────────────────────────────────────────────

class TestAddLesson:
    def test_add_returns_id(self):
        path = _tmp_store()
        with patch("src.lessons_learned._store_path", return_value=path):
            lid = add_lesson("Test lesson")
            assert lid == "L0001"
        os.unlink(path)

    def test_add_increments_id(self):
        path = _tmp_store()
        with patch("src.lessons_learned._store_path", return_value=path):
            id1 = add_lesson("Lesson 1")
            id2 = add_lesson("Lesson 2")
            id3 = add_lesson("Lesson 3")
            assert id1 == "L0001"
            assert id2 == "L0002"
            assert id3 == "L0003"
        os.unlink(path)

    def test_add_with_agent_and_category(self):
        path = _tmp_store()
        with patch("src.lessons_learned._store_path", return_value=path):
            add_lesson("Test", agent="smm", category="quality")
            lessons = get_all_lessons()
            assert lessons[0].agent == "smm"
            assert lessons[0].category == "quality"
        os.unlink(path)

    def test_invalid_category_falls_back(self):
        path = _tmp_store()
        with patch("src.lessons_learned._store_path", return_value=path):
            add_lesson("Test", category="nonexistent")
            lessons = get_all_lessons()
            assert lessons[0].category == "other"
        os.unlink(path)

    def test_summary_truncated(self):
        path = _tmp_store()
        with patch("src.lessons_learned._store_path", return_value=path):
            add_lesson("A" * 300)
            lessons = get_all_lessons()
            assert len(lessons[0].summary) == 200
        os.unlink(path)

    def test_detail_truncated(self):
        path = _tmp_store()
        with patch("src.lessons_learned._store_path", return_value=path):
            add_lesson("Test", detail="B" * 1500)
            lessons = get_all_lessons()
            assert len(lessons[0].detail) == 1000
        os.unlink(path)

    def test_action_truncated(self):
        path = _tmp_store()
        with patch("src.lessons_learned._store_path", return_value=path):
            add_lesson("Test", action="C" * 600)
            lessons = get_all_lessons()
            assert len(lessons[0].action) == 500
        os.unlink(path)


# ── Get Lessons ───────────────────────────────────────────

class TestGetLessons:
    def test_get_all_empty(self):
        path = _tmp_store()
        with patch("src.lessons_learned._store_path", return_value=path):
            assert get_all_lessons() == []
        os.unlink(path)

    def test_get_by_agent(self):
        path = _tmp_store()
        with patch("src.lessons_learned._store_path", return_value=path):
            add_lesson("L1", agent="smm")
            add_lesson("L2", agent="automator")
            add_lesson("L3", agent="smm")
            results = get_lessons(agent="smm")
            assert len(results) == 2
            assert all(l.agent == "smm" for l in results)
        os.unlink(path)

    def test_get_by_category(self):
        path = _tmp_store()
        with patch("src.lessons_learned._store_path", return_value=path):
            add_lesson("L1", category="quality")
            add_lesson("L2", category="data")
            add_lesson("L3", category="quality")
            results = get_lessons(category="quality")
            assert len(results) == 2
        os.unlink(path)

    def test_get_with_limit(self):
        path = _tmp_store()
        with patch("src.lessons_learned._store_path", return_value=path):
            for i in range(10):
                add_lesson(f"Lesson {i}")
            results = get_lessons(limit=3)
            assert len(results) == 3
            # Should be the 3 most recent
            assert results[-1].summary == "Lesson 9"
        os.unlink(path)

    def test_get_combined_filters(self):
        path = _tmp_store()
        with patch("src.lessons_learned._store_path", return_value=path):
            add_lesson("L1", agent="smm", category="quality")
            add_lesson("L2", agent="smm", category="data")
            add_lesson("L3", agent="automator", category="quality")
            results = get_lessons(agent="smm", category="quality")
            assert len(results) == 1
            assert results[0].summary == "L1"
        os.unlink(path)


# ── Context Injection ─────────────────────────────────────

class TestContextInjection:
    def test_empty_store_returns_empty(self):
        path = _tmp_store()
        with patch("src.lessons_learned._store_path", return_value=path):
            ctx = get_lessons_for_context()
            assert ctx == ""
        os.unlink(path)

    def test_returns_formatted_text(self):
        path = _tmp_store()
        with patch("src.lessons_learned._store_path", return_value=path):
            add_lesson("Never fabricate data", agent="manager", action="Use tools instead")
            ctx = get_lessons_for_context(agent="manager")
            assert "УРОКИ ИЗ ПРОШЛОГО ОПЫТА" in ctx
            assert "Never fabricate data" in ctx
            assert "Use tools instead" in ctx
        os.unlink(path)

    def test_filters_by_agent(self):
        path = _tmp_store()
        with patch("src.lessons_learned._store_path", return_value=path):
            add_lesson("SMM lesson", agent="smm")
            add_lesson("Automator lesson", agent="automator")
            ctx = get_lessons_for_context(agent="smm")
            assert "SMM lesson" in ctx
            assert "Automator lesson" not in ctx
        os.unlink(path)

    def test_includes_general_lessons(self):
        path = _tmp_store()
        with patch("src.lessons_learned._store_path", return_value=path):
            add_lesson("General lesson", agent="")
            add_lesson("SMM lesson", agent="smm")
            ctx = get_lessons_for_context(agent="smm")
            assert "General lesson" in ctx
            assert "SMM lesson" in ctx
        os.unlink(path)

    def test_respects_limit(self):
        path = _tmp_store()
        with patch("src.lessons_learned._store_path", return_value=path):
            for i in range(10):
                add_lesson(f"Lesson {i}")
            ctx = get_lessons_for_context(limit=3)
            # Should have 3 bullet points
            bullet_count = ctx.count("•")
            assert bullet_count == 3
        os.unlink(path)


# ── Stats ─────────────────────────────────────────────────

class TestStats:
    def test_empty_stats(self):
        path = _tmp_store()
        with patch("src.lessons_learned._store_path", return_value=path):
            stats = get_lesson_stats()
            assert stats["total"] == 0
            assert stats["by_category"] == {}
            assert stats["by_agent"] == {}
        os.unlink(path)

    def test_stats_count(self):
        path = _tmp_store()
        with patch("src.lessons_learned._store_path", return_value=path):
            add_lesson("L1", agent="smm", category="quality")
            add_lesson("L2", agent="smm", category="data")
            add_lesson("L3", agent="automator", category="quality")
            stats = get_lesson_stats()
            assert stats["total"] == 3
            assert stats["by_category"]["quality"] == 2
            assert stats["by_category"]["data"] == 1
            assert stats["by_agent"]["smm"] == 2
            assert stats["by_agent"]["automator"] == 1
        os.unlink(path)


# ── Mark Useful ───────────────────────────────────────────

class TestMarkUseful:
    def test_mark_useful_increments(self):
        path = _tmp_store()
        with patch("src.lessons_learned._store_path", return_value=path):
            lid = add_lesson("Test lesson")
            assert mark_useful(lid) is True
            lessons = get_all_lessons()
            assert lessons[0].useful_count == 1
            mark_useful(lid)
            lessons = get_all_lessons()
            assert lessons[0].useful_count == 2
        os.unlink(path)

    def test_mark_useful_not_found(self):
        path = _tmp_store()
        with patch("src.lessons_learned._store_path", return_value=path):
            assert mark_useful("L9999") is False
        os.unlink(path)


# ── Delete ────────────────────────────────────────────────

class TestDelete:
    def test_delete_lesson(self):
        path = _tmp_store()
        with patch("src.lessons_learned._store_path", return_value=path):
            lid = add_lesson("To delete")
            assert delete_lesson(lid) is True
            assert len(get_all_lessons()) == 0
        os.unlink(path)

    def test_delete_not_found(self):
        path = _tmp_store()
        with patch("src.lessons_learned._store_path", return_value=path):
            assert delete_lesson("L9999") is False
        os.unlink(path)

    def test_delete_preserves_others(self):
        path = _tmp_store()
        with patch("src.lessons_learned._store_path", return_value=path):
            lid1 = add_lesson("Keep")
            lid2 = add_lesson("Delete")
            lid3 = add_lesson("Keep too")
            delete_lesson(lid2)
            remaining = get_all_lessons()
            assert len(remaining) == 2
            assert remaining[0].summary == "Keep"
            assert remaining[1].summary == "Keep too"
        os.unlink(path)


# ── Persistence ───────────────────────────────────────────

class TestPersistence:
    def test_load_missing_file(self):
        with patch("src.lessons_learned._store_path", return_value="/tmp/nonexistent_lessons_12345.json"):
            store = _load_store()
            assert isinstance(store, LessonsStore)
            assert store.lessons == []

    def test_load_corrupted_file(self):
        path = _tmp_store()
        with open(path, "w") as f:
            f.write("not json!!!")
        with patch("src.lessons_learned._store_path", return_value=path):
            store = _load_store()
            assert isinstance(store, LessonsStore)
        os.unlink(path)

    def test_roundtrip(self):
        path = _tmp_store()
        with patch("src.lessons_learned._store_path", return_value=path):
            add_lesson("Lesson A", agent="smm", category="quality", action="Do X")
            add_lesson("Lesson B", agent="automator", category="integration")
            lessons = get_all_lessons()
            assert len(lessons) == 2
            assert lessons[0].summary == "Lesson A"
            assert lessons[0].action == "Do X"
            assert lessons[1].agent == "automator"
        os.unlink(path)

    def test_cap_at_max(self):
        path = _tmp_store()
        with patch("src.lessons_learned._store_path", return_value=path):
            for i in range(MAX_LESSONS + 10):
                add_lesson(f"Lesson {i}")
            lessons = get_all_lessons()
            assert len(lessons) == MAX_LESSONS
            assert lessons[-1].summary == f"Lesson {MAX_LESSONS + 9}"
        os.unlink(path)
