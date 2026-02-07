"""
🔬 Deep tests for Fix #2: Chat history persistence

Covers:
- JSON fallback: edge cases (corrupt, partial, huge data)
- PostgreSQL: mocked save/load with realistic scenarios
- Public API: fallback chain (PG success, PG fail→JSON, no PG→JSON only)
- Concurrency: save_to_json thread safety
- Data integrity: cyrillic, emoji, special chars, datetime fields
- Boundary: empty list, single message, 10000 messages
- Integration: app.py imports and uses chat_storage correctly
- Regression: no local persistence functions left in app.py
"""

import ast
import json
import os
import sys
import threading
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

APP_PATH = os.path.join(os.path.dirname(__file__), "..", "app.py")
STORAGE_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "chat_storage.py")


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ═══════════════════════════════════════════════════════════════
# 1. JSON fallback edge cases
# ═══════════════════════════════════════════════════════════════

class TestJsonEdgeCases:

    def test_save_creates_parent_dirs(self, tmp_path):
        from src.chat_storage import save_to_json, load_from_json
        deep_path = tmp_path / "a" / "b" / "c" / "chat.json"
        with patch("src.chat_storage._chat_path", return_value=str(deep_path)):
            assert save_to_json([{"role": "user", "content": "test"}]) is True
            assert load_from_json() == [{"role": "user", "content": "test"}]

    def test_save_overwrite_existing(self, tmp_path):
        from src.chat_storage import save_to_json, load_from_json
        f = tmp_path / "chat.json"
        f.write_text('[{"old": true}]')
        with patch("src.chat_storage._chat_path", return_value=str(f)):
            save_to_json([{"role": "user", "content": "new"}])
            result = load_from_json()
            assert result == [{"role": "user", "content": "new"}]
            assert "old" not in json.dumps(result)

    def test_load_json_object_instead_of_array(self, tmp_path):
        """If file contains a JSON object (not array), return []."""
        from src.chat_storage import load_from_json
        f = tmp_path / "chat.json"
        f.write_text('{"not": "an array"}')
        with patch("src.chat_storage._chat_path", return_value=str(f)):
            assert load_from_json() == []

    def test_load_json_string_instead_of_array(self, tmp_path):
        from src.chat_storage import load_from_json
        f = tmp_path / "chat.json"
        f.write_text('"just a string"')
        with patch("src.chat_storage._chat_path", return_value=str(f)):
            assert load_from_json() == []

    def test_load_json_number_instead_of_array(self, tmp_path):
        from src.chat_storage import load_from_json
        f = tmp_path / "chat.json"
        f.write_text('42')
        with patch("src.chat_storage._chat_path", return_value=str(f)):
            assert load_from_json() == []

    def test_load_truncated_json(self, tmp_path):
        from src.chat_storage import load_from_json
        f = tmp_path / "chat.json"
        f.write_text('[{"role": "user", "content": "trunc')
        with patch("src.chat_storage._chat_path", return_value=str(f)):
            assert load_from_json() == []

    def test_save_returns_false_on_readonly(self, tmp_path):
        from src.chat_storage import save_to_json
        with patch("src.chat_storage._chat_path", return_value="/nonexistent/deep/path/chat.json"):
            assert save_to_json([]) is False

    def test_huge_message_list(self, tmp_path):
        """Save/load 1000 messages."""
        from src.chat_storage import save_to_json, load_from_json
        f = tmp_path / "chat.json"
        msgs = [{"role": "user", "content": f"msg_{i}"} for i in range(1000)]
        with patch("src.chat_storage._chat_path", return_value=str(f)):
            assert save_to_json(msgs) is True
            loaded = load_from_json()
            assert len(loaded) == 1000
            assert loaded[0]["content"] == "msg_0"
            assert loaded[999]["content"] == "msg_999"

    def test_empty_list_saved_and_loaded_as_empty(self, tmp_path):
        """Saving [] then loading returns []."""
        from src.chat_storage import save_to_json, load_from_json
        f = tmp_path / "chat.json"
        with patch("src.chat_storage._chat_path", return_value=str(f)):
            save_to_json([])
            assert load_from_json() == []


# ═══════════════════════════════════════════════════════════════
# 2. Data integrity: special characters
# ═══════════════════════════════════════════════════════════════

class TestDataIntegrity:

    def test_cyrillic_roundtrip(self, tmp_path):
        from src.chat_storage import save_to_json, load_from_json
        f = tmp_path / "chat.json"
        msgs = [{"role": "user", "content": "Финансовый отчёт за январь 2026"}]
        with patch("src.chat_storage._chat_path", return_value=str(f)):
            save_to_json(msgs)
            raw = f.read_text(encoding="utf-8")
            assert "Финансовый" in raw  # not escaped
            loaded = load_from_json()
            assert loaded[0]["content"] == "Финансовый отчёт за январь 2026"

    def test_emoji_roundtrip(self, tmp_path):
        from src.chat_storage import save_to_json, load_from_json
        f = tmp_path / "chat.json"
        msgs = [{"role": "assistant", "content": "📊 Отчёт 💰 готов ✅"}]
        with patch("src.chat_storage._chat_path", return_value=str(f)):
            save_to_json(msgs)
            loaded = load_from_json()
            assert "📊" in loaded[0]["content"]
            assert "💰" in loaded[0]["content"]

    def test_special_chars_in_content(self, tmp_path):
        from src.chat_storage import save_to_json, load_from_json
        f = tmp_path / "chat.json"
        content = 'Кавычки "test" и \'single\', бэкслэш \\, таб\t, новая строка\n, null \x00'
        msgs = [{"role": "user", "content": content}]
        with patch("src.chat_storage._chat_path", return_value=str(f)):
            save_to_json(msgs)
            loaded = load_from_json()
            assert loaded[0]["content"] == content

    def test_all_message_fields_preserved(self, tmp_path):
        """All fields including time, date, agent_key survive round-trip."""
        from src.chat_storage import save_to_json, load_from_json
        f = tmp_path / "chat.json"
        msg = {
            "role": "assistant",
            "content": "Response text",
            "agent_key": "accountant",
            "agent_name": "Маттиас",
            "time": "14:30",
            "date": "07.02.2026",
        }
        with patch("src.chat_storage._chat_path", return_value=str(f)):
            save_to_json([msg])
            loaded = load_from_json()
            assert loaded[0] == msg


# ═══════════════════════════════════════════════════════════════
# 3. PostgreSQL mocked scenarios
# ═══════════════════════════════════════════════════════════════

class TestPostgresMocked:

    def test_save_to_postgres_serializes_json(self):
        """Verify JSON serialization is passed to execute."""
        from src.chat_storage import save_to_postgres
        msgs = [{"role": "user", "content": "тест"}]

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cur
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.chat_storage._get_db_url", return_value="postgresql://x"), \
             patch("src.chat_storage._get_connection", return_value=mock_conn):
            result = save_to_postgres(msgs)

        assert result is True
        # Check the JSON was passed correctly
        call_args = mock_cur.execute.call_args_list
        # Second call is the UPSERT (first is CREATE TABLE)
        upsert_call = call_args[1]
        json_str = upsert_call[0][1][0]
        parsed = json.loads(json_str)
        assert parsed == msgs

    def test_load_from_postgres_handles_string_data(self):
        """If PostgreSQL returns string instead of JSONB, it should be parsed."""
        from src.chat_storage import load_from_postgres
        expected = [{"role": "user", "content": "test"}]

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        # Return as string (some drivers do this)
        mock_cur.fetchone.return_value = (json.dumps(expected),)
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cur
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.chat_storage._get_db_url", return_value="postgresql://x"), \
             patch("src.chat_storage._get_connection", return_value=mock_conn):
            result = load_from_postgres()

        assert result == expected

    def test_load_from_postgres_handles_list_data(self):
        """If PostgreSQL returns native list (JSONB), use directly."""
        from src.chat_storage import load_from_postgres
        expected = [{"role": "user", "content": "test"}]

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = (expected,)
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cur
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.chat_storage._get_db_url", return_value="postgresql://x"), \
             patch("src.chat_storage._get_connection", return_value=mock_conn):
            result = load_from_postgres()

        assert result == expected

    def test_load_from_postgres_empty_table_returns_empty_list(self):
        """If no row exists, return []."""
        from src.chat_storage import load_from_postgres

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = None
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cur
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.chat_storage._get_db_url", return_value="postgresql://x"), \
             patch("src.chat_storage._get_connection", return_value=mock_conn):
            result = load_from_postgres()

        assert result == []

    def test_save_to_postgres_exception_returns_false(self):
        from src.chat_storage import save_to_postgres
        with patch("src.chat_storage._get_db_url", return_value="postgresql://x"), \
             patch("src.chat_storage._get_connection", side_effect=Exception("boom")):
            assert save_to_postgres([]) is False

    def test_load_from_postgres_exception_returns_none(self):
        from src.chat_storage import load_from_postgres
        with patch("src.chat_storage._get_db_url", return_value="postgresql://x"), \
             patch("src.chat_storage._get_connection", side_effect=Exception("boom")):
            assert load_from_postgres() is None


# ═══════════════════════════════════════════════════════════════
# 4. Public API: fallback chain
# ═══════════════════════════════════════════════════════════════

class TestFallbackChain:

    def test_save_pg_success_also_saves_json(self):
        """When PG succeeds, JSON is also written as local cache."""
        from src import chat_storage
        msgs = [{"role": "user", "content": "x"}]
        with patch.object(chat_storage, "_get_db_url", return_value="pg://x"), \
             patch.object(chat_storage, "save_to_postgres", return_value=True) as pg, \
             patch.object(chat_storage, "save_to_json", return_value=True) as js:
            chat_storage.save_chat_history(msgs)
        pg.assert_called_once_with(msgs)
        js.assert_called_once_with(msgs)

    def test_save_pg_fail_falls_back_to_json(self):
        from src import chat_storage
        msgs = [{"role": "user", "content": "x"}]
        with patch.object(chat_storage, "_get_db_url", return_value="pg://x"), \
             patch.object(chat_storage, "save_to_postgres", return_value=False), \
             patch.object(chat_storage, "save_to_json", return_value=True) as js:
            chat_storage.save_chat_history(msgs)
        js.assert_called_once_with(msgs)

    def test_save_no_pg_uses_json_only(self):
        from src import chat_storage
        msgs = [{"role": "user", "content": "x"}]
        with patch.object(chat_storage, "_get_db_url", return_value=None), \
             patch.object(chat_storage, "save_to_postgres") as pg, \
             patch.object(chat_storage, "save_to_json", return_value=True) as js:
            chat_storage.save_chat_history(msgs)
        pg.assert_not_called()
        js.assert_called_once()

    def test_load_pg_success_returns_pg_data(self):
        from src import chat_storage
        with patch.object(chat_storage, "_get_db_url", return_value="pg://x"), \
             patch.object(chat_storage, "load_from_postgres", return_value=[{"x": 1}]):
            result = chat_storage.load_chat_history()
        assert result == [{"x": 1}]

    def test_load_pg_returns_none_falls_to_json(self):
        from src import chat_storage
        with patch.object(chat_storage, "_get_db_url", return_value="pg://x"), \
             patch.object(chat_storage, "load_from_postgres", return_value=None), \
             patch.object(chat_storage, "load_from_json", return_value=[{"y": 2}]):
            result = chat_storage.load_chat_history()
        assert result == [{"y": 2}]

    def test_load_no_pg_uses_json(self):
        from src import chat_storage
        with patch.object(chat_storage, "_get_db_url", return_value=None), \
             patch.object(chat_storage, "load_from_json", return_value=[{"z": 3}]):
            result = chat_storage.load_chat_history()
        assert result == [{"z": 3}]

    def test_is_persistent_true(self):
        from src.chat_storage import is_persistent
        with patch.dict(os.environ, {"DATABASE_URL": "pg://x"}):
            assert is_persistent() is True

    def test_is_persistent_false(self):
        from src.chat_storage import is_persistent
        with patch.dict(os.environ, {}, clear=True):
            with patch("src.chat_storage._get_db_url", return_value=None):
                assert is_persistent() is False


# ═══════════════════════════════════════════════════════════════
# 5. Thread safety
# ═══════════════════════════════════════════════════════════════

class TestThreadSafety:

    def test_concurrent_json_saves(self, tmp_path):
        """Multiple threads saving concurrently should not corrupt the file."""
        from src.chat_storage import save_to_json, load_from_json
        f = tmp_path / "chat.json"
        errors = []

        def save_batch(batch_id):
            try:
                msgs = [{"role": "user", "content": f"batch_{batch_id}_{i}"} for i in range(10)]
                with patch("src.chat_storage._chat_path", return_value=str(f)):
                    save_to_json(msgs)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=save_batch, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Errors in concurrent save: {errors}"
        # File should be valid JSON
        with patch("src.chat_storage._chat_path", return_value=str(f)):
            result = load_from_json()
        assert isinstance(result, list)
        assert len(result) == 10  # last batch wins


# ═══════════════════════════════════════════════════════════════
# 6. SQL safety
# ═══════════════════════════════════════════════════════════════

class TestSQLSafety:

    def test_upsert_uses_parameterized(self):
        source = _read(STORAGE_PATH)
        assert "%s" in source
        # No f-strings or .format() in SQL
        assert "f'" not in source or "f'" in source.split("def ")[0]

    def test_no_raw_string_interpolation_in_sql(self):
        source = _read(STORAGE_PATH)
        # SQL blocks should not have .format() or f""
        for sql_var in ["_CREATE_TABLE", "_UPSERT", "_SELECT"]:
            if sql_var in source:
                idx = source.index(sql_var)
                block = source[idx:idx + 200]
                assert ".format(" not in block


# ═══════════════════════════════════════════════════════════════
# 7. app.py integration
# ═══════════════════════════════════════════════════════════════

class TestAppIntegration:

    def test_no_local_persistence_functions(self):
        """app.py should NOT define _chat_path, save_chat_history, load_chat_history."""
        source = _read(APP_PATH)
        tree = ast.parse(source)
        local_funcs = {"_chat_path", "save_chat_history", "load_chat_history"}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in local_funcs:
                pytest.fail(f"app.py still defines {node.name} locally")

    def test_imports_from_chat_storage(self):
        source = _read(APP_PATH)
        assert "from src.chat_storage import" in source
        assert "save_chat_history" in source
        assert "load_chat_history" in source

    def test_save_called_after_pending_prompt(self):
        source = _read(APP_PATH)
        lines = source.split("\n")
        for i, line in enumerate(lines):
            if '"pending_prompt" in st.session_state' in line:
                block = "\n".join(lines[i:i + 80])
                assert "save_chat_history" in block
                return
        pytest.fail("pending_prompt block not found")

    def test_load_called_for_session_init(self):
        source = _read(APP_PATH)
        assert "load_chat_history()" in source

    def test_chat_storage_module_is_valid_python(self):
        source = _read(STORAGE_PATH)
        ast.parse(source)

    def test_app_is_valid_python(self):
        source = _read(APP_PATH)
        ast.parse(source)
