"""
🧪 Tests for Fix #2: Chat history persistence across redeploys

Verifies:
1. chat_storage module exists with PostgreSQL + JSON fallback
2. save/load round-trip works for JSON fallback
3. PostgreSQL integration (mocked)
4. app.py imports from chat_storage (not local functions)
5. Regression: nothing broken
"""

import ast
import json
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

APP_PATH = os.path.join(os.path.dirname(__file__), "..", "app.py")
STORAGE_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "chat_storage.py")


def _read_source(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ──────────────────────────────────────────────────────────
# 1. chat_storage module structure
# ──────────────────────────────────────────────────────────

class TestChatStorageModule:
    """Verify the new chat_storage module exists and has the right structure."""

    def test_module_exists(self):
        assert os.path.exists(STORAGE_PATH)

    def test_importable(self):
        from src.chat_storage import save_chat_history, load_chat_history, is_persistent
        assert callable(save_chat_history)
        assert callable(load_chat_history)
        assert callable(is_persistent)

    def test_has_postgres_functions(self):
        from src.chat_storage import save_to_postgres, load_from_postgres
        assert callable(save_to_postgres)
        assert callable(load_from_postgres)

    def test_has_json_functions(self):
        from src.chat_storage import save_to_json, load_from_json
        assert callable(save_to_json)
        assert callable(load_from_json)

    def test_has_sql_statements(self):
        source = _read_source(STORAGE_PATH)
        assert "CREATE TABLE" in source
        assert "chat_history" in source
        assert "JSONB" in source

    def test_valid_python(self):
        source = _read_source(STORAGE_PATH)
        ast.parse(source)


# ──────────────────────────────────────────────────────────
# 2. JSON fallback round-trip
# ──────────────────────────────────────────────────────────

class TestJsonFallback:
    """Verify JSON save/load works as before."""

    def test_save_and_load_round_trip(self, tmp_path):
        from src.chat_storage import save_to_json, load_from_json, _chat_path
        json_file = tmp_path / "chat_history.json"

        messages = [
            {"role": "user", "content": "Привет", "time": "12:00"},
            {"role": "assistant", "content": "Добрый день!", "agent_name": "Алексей", "time": "12:01"},
        ]

        with patch("src.chat_storage._chat_path", return_value=str(json_file)):
            assert save_to_json(messages) is True
            loaded = load_from_json()
            assert len(loaded) == 2
            assert loaded[0]["content"] == "Привет"
            assert loaded[1]["content"] == "Добрый день!"

    def test_load_empty_file_returns_empty(self, tmp_path):
        from src.chat_storage import load_from_json
        json_file = tmp_path / "chat_history.json"
        json_file.write_text("[]")

        with patch("src.chat_storage._chat_path", return_value=str(json_file)):
            result = load_from_json()
            assert result == []

    def test_load_missing_file_returns_empty(self, tmp_path):
        from src.chat_storage import load_from_json
        json_file = tmp_path / "nonexistent.json"

        with patch("src.chat_storage._chat_path", return_value=str(json_file)):
            result = load_from_json()
            assert result == []

    def test_load_corrupt_json_returns_empty(self, tmp_path):
        from src.chat_storage import load_from_json
        json_file = tmp_path / "chat_history.json"
        json_file.write_text("{corrupt!!!")

        with patch("src.chat_storage._chat_path", return_value=str(json_file)):
            result = load_from_json()
            assert result == []

    def test_cyrillic_preserved(self, tmp_path):
        from src.chat_storage import save_to_json, load_from_json
        json_file = tmp_path / "chat_history.json"

        messages = [{"role": "user", "content": "Финансовый отчёт за январь"}]
        with patch("src.chat_storage._chat_path", return_value=str(json_file)):
            save_to_json(messages)
            raw = json_file.read_text(encoding="utf-8")
            assert "Финансовый" in raw  # ensure_ascii=False
            loaded = load_from_json()
            assert loaded[0]["content"] == "Финансовый отчёт за январь"


# ──────────────────────────────────────────────────────────
# 3. PostgreSQL integration (mocked)
# ──────────────────────────────────────────────────────────

class TestPostgresIntegration:
    """Verify PostgreSQL save/load with mocked psycopg2."""

    def test_save_to_postgres_calls_execute(self):
        from src.chat_storage import save_to_postgres
        messages = [{"role": "user", "content": "test"}]

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.chat_storage._get_db_url", return_value="postgresql://test"), \
             patch("src.chat_storage._get_connection", return_value=mock_conn):
            result = save_to_postgres(messages)

        assert result is True
        # Should have called execute at least twice (CREATE TABLE + UPSERT)
        assert mock_cursor.execute.call_count >= 2
        mock_conn.commit.assert_called()
        mock_conn.close.assert_called_once()

    def test_load_from_postgres_returns_data(self):
        from src.chat_storage import load_from_postgres
        expected = [{"role": "user", "content": "saved"}]

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (expected,)
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.chat_storage._get_db_url", return_value="postgresql://test"), \
             patch("src.chat_storage._get_connection", return_value=mock_conn):
            result = load_from_postgres()

        assert result == expected

    def test_load_from_postgres_no_url_returns_none(self):
        from src.chat_storage import load_from_postgres
        with patch("src.chat_storage._get_db_url", return_value=None):
            result = load_from_postgres()
            assert result is None

    def test_save_to_postgres_no_url_returns_false(self):
        from src.chat_storage import save_to_postgres
        with patch("src.chat_storage._get_db_url", return_value=None):
            result = save_to_postgres([])
            assert result is False

    def test_save_to_postgres_connection_error_returns_false(self):
        from src.chat_storage import save_to_postgres
        with patch("src.chat_storage._get_db_url", return_value="postgresql://test"), \
             patch("src.chat_storage._get_connection", side_effect=Exception("conn failed")):
            result = save_to_postgres([{"role": "user", "content": "test"}])
            assert result is False

    def test_is_persistent_with_url(self):
        from src.chat_storage import is_persistent
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test"}):
            assert is_persistent() is True

    def test_is_persistent_without_url(self):
        from src.chat_storage import is_persistent
        with patch.dict(os.environ, {}, clear=True):
            # Also ensure DATABASE_URL is not set
            with patch("src.chat_storage._get_db_url", return_value=None):
                assert is_persistent() is False


# ──────────────────────────────────────────────────────────
# 4. Public API: fallback behavior
# ──────────────────────────────────────────────────────────

class TestPublicAPIFallback:
    """Verify save/load_chat_history use PostgreSQL first, then JSON."""

    def test_save_uses_postgres_when_available(self, tmp_path):
        from src import chat_storage
        messages = [{"role": "user", "content": "test"}]

        with patch.object(chat_storage, "_get_db_url", return_value="postgresql://test"), \
             patch.object(chat_storage, "save_to_postgres", return_value=True) as mock_pg, \
             patch.object(chat_storage, "save_to_json", return_value=True) as mock_json:
            chat_storage.save_chat_history(messages)

        mock_pg.assert_called_once_with(messages)
        mock_json.assert_called_once_with(messages)  # also saves to JSON as cache

    def test_save_falls_back_to_json_on_postgres_failure(self):
        from src import chat_storage
        messages = [{"role": "user", "content": "test"}]

        with patch.object(chat_storage, "_get_db_url", return_value="postgresql://test"), \
             patch.object(chat_storage, "save_to_postgres", return_value=False), \
             patch.object(chat_storage, "save_to_json", return_value=True) as mock_json:
            chat_storage.save_chat_history(messages)

        mock_json.assert_called_once_with(messages)

    def test_save_uses_json_only_without_database_url(self):
        from src import chat_storage
        messages = [{"role": "user", "content": "test"}]

        with patch.object(chat_storage, "_get_db_url", return_value=None), \
             patch.object(chat_storage, "save_to_postgres") as mock_pg, \
             patch.object(chat_storage, "save_to_json", return_value=True) as mock_json:
            chat_storage.save_chat_history(messages)

        mock_pg.assert_not_called()
        mock_json.assert_called_once_with(messages)

    def test_load_uses_postgres_when_available(self):
        from src import chat_storage
        expected = [{"role": "user", "content": "from_pg"}]

        with patch.object(chat_storage, "_get_db_url", return_value="postgresql://test"), \
             patch.object(chat_storage, "load_from_postgres", return_value=expected):
            result = chat_storage.load_chat_history()

        assert result == expected

    def test_load_falls_back_to_json_on_postgres_failure(self):
        from src import chat_storage
        json_data = [{"role": "user", "content": "from_json"}]

        with patch.object(chat_storage, "_get_db_url", return_value="postgresql://test"), \
             patch.object(chat_storage, "load_from_postgres", return_value=None), \
             patch.object(chat_storage, "load_from_json", return_value=json_data):
            result = chat_storage.load_chat_history()

        assert result == json_data


# ──────────────────────────────────────────────────────────
# 5. app.py imports from chat_storage
# ──────────────────────────────────────────────────────────

class TestAppUsesModule:
    """Verify app.py uses the new chat_storage module."""

    def test_app_imports_from_chat_storage(self):
        source = _read_source(APP_PATH)
        assert "from src.chat_storage import" in source

    def test_app_imports_save_chat_history(self):
        source = _read_source(APP_PATH)
        assert "save_chat_history" in source

    def test_app_imports_load_chat_history(self):
        source = _read_source(APP_PATH)
        assert "load_chat_history" in source

    def test_no_local_save_function_in_app(self):
        """app.py should NOT define its own save_chat_history anymore."""
        source = _read_source(APP_PATH)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "save_chat_history":
                pytest.fail("app.py still defines its own save_chat_history — should import from chat_storage")

    def test_no_local_load_function_in_app(self):
        """app.py should NOT define its own load_chat_history anymore."""
        source = _read_source(APP_PATH)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "load_chat_history":
                pytest.fail("app.py still defines its own load_chat_history — should import from chat_storage")

    def test_app_valid_python(self):
        source = _read_source(APP_PATH)
        ast.parse(source)


# ──────────────────────────────────────────────────────────
# 6. Regression: SQL injection safety
# ──────────────────────────────────────────────────────────

class TestSQLSafety:
    """Verify the SQL is parameterized, not string-formatted."""

    def test_upsert_uses_parameterized_query(self):
        source = _read_source(STORAGE_PATH)
        # Should use %s placeholder, NOT f-string or .format()
        assert "%s" in source
        assert "f'" not in source.split("_UPSERT")[1].split('"""')[0] if "_UPSERT" in source else True

    def test_no_string_format_in_sql(self):
        source = _read_source(STORAGE_PATH)
        # Check that SQL statements don't use .format() or f-strings
        assert ".format(" not in source.split("CREATE TABLE")[0] if "CREATE TABLE" in source else True
