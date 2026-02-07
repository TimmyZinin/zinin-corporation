"""Tests for chat history persistence.

Verifies:
- Chat storage module provides PostgreSQL + JSON fallback
- JSON fallback works correctly for local development
- DATABASE_URL is now used for persistent storage (FIXED)
- format_chat_context() truncates agent replies to 800 chars (FIXED from 300)
"""

import sys
import os
import json
import inspect
import ast
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

APP_DIR = os.path.join(os.path.dirname(__file__), "..")
APP_PATH = os.path.join(APP_DIR, "app.py")
STORAGE_PATH = os.path.join(APP_DIR, "src", "chat_storage.py")


def _load_app_source() -> str:
    with open(APP_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _load_storage_source() -> str:
    with open(STORAGE_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _load_app_ast() -> ast.Module:
    return ast.parse(_load_app_source())


def _build_chat_functions(tmp_path=None):
    """Build chat functions from both app.py and chat_storage.py."""
    ns = {"os": os, "json": json, "logging": logging}

    # Extract format_chat_context from app.py
    app_source = _load_app_source()
    app_tree = ast.parse(app_source)
    for node in ast.walk(app_tree):
        if isinstance(node, ast.FunctionDef) and node.name == "format_chat_context":
            exec(ast.get_source_segment(app_source, node), ns)

    # Extract storage functions from chat_storage.py
    storage_source = _load_storage_source()
    storage_tree = ast.parse(storage_source)
    func_names = {"_chat_path", "save_to_json", "load_from_json"}
    for node in ast.walk(storage_tree):
        if isinstance(node, ast.FunctionDef) and node.name in func_names:
            exec(ast.get_source_segment(storage_source, node), ns)

    # Map to expected names
    if "save_to_json" in ns:
        ns["save_chat_history"] = ns["save_to_json"]
    if "load_from_json" in ns:
        ns["load_chat_history"] = ns["load_from_json"]

    return ns


# ===================================================================
# Test class: chat storage relies on local JSON file
# ===================================================================

class TestChatStorageJsonFallback:
    """Test the JSON fallback in chat_storage module."""

    def test_chat_path_returns_json_file_path(self):
        """_chat_path() returns a path ending in chat_history.json."""
        ns = _build_chat_functions()
        path = ns["_chat_path"]()
        assert path.endswith("chat_history.json")

    def test_chat_path_in_storage_module(self):
        """_chat_path is defined in src/chat_storage.py."""
        source = _load_storage_source()
        assert "def _chat_path" in source

    def test_save_writes_json_to_local_file(self, tmp_path):
        """save_to_json writes a JSON file to the local filesystem."""
        ns = _build_chat_functions()
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        chat_file = data_dir / "chat_history.json"

        messages = [
            {"role": "assistant", "content": "Hello", "agent_name": "Alexey"},
            {"role": "user", "content": "Hi"},
        ]

        ns["_chat_path"] = lambda: str(chat_file)
        ns["save_chat_history"](messages)

        assert chat_file.exists()
        loaded = json.loads(chat_file.read_text(encoding="utf-8"))
        assert loaded == messages

    def test_load_reads_from_local_file(self, tmp_path):
        """load_from_json reads from a local JSON file."""
        ns = _build_chat_functions()
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        chat_file = data_dir / "chat_history.json"

        messages = [{"role": "user", "content": "test message"}]
        chat_file.write_text(json.dumps(messages), encoding="utf-8")

        ns["_chat_path"] = lambda: str(chat_file)
        result = ns["load_chat_history"]()
        assert result == messages


# ===================================================================
# Test class: DATABASE_URL is cosmetic -- never used for chat storage
# ===================================================================

class TestDatabaseUrlUsed:
    """Verify that DATABASE_URL is now actively used for persistent storage (FIXED)."""

    def test_database_url_in_app_ui(self):
        """app.py shows DATABASE_URL status in the UI."""
        source = _load_app_source()
        assert "DATABASE_URL" in source
        assert "PostgreSQL" in source

    def test_chat_storage_uses_database_url(self):
        """chat_storage.py reads DATABASE_URL for PostgreSQL connection."""
        source = _load_storage_source()
        assert "DATABASE_URL" in source

    def test_chat_storage_has_postgresql_logic(self):
        """chat_storage.py has save_to_postgres and load_from_postgres."""
        source = _load_storage_source()
        assert "def save_to_postgres" in source
        assert "def load_from_postgres" in source
        assert "psycopg2" in source


# ===================================================================
# Test class: save_chat_history silently swallows all exceptions
# ===================================================================

class TestErrorHandling:
    """Verify error handling in chat storage."""

    def test_save_to_json_returns_false_on_error(self):
        """save_to_json returns False when it can't write."""
        from unittest.mock import patch
        from src.chat_storage import save_to_json
        with patch("src.chat_storage._chat_path", return_value="/nonexistent/deep/path/chat.json"):
            result = save_to_json([{"role": "user", "content": "test"}])
            assert result is False

    def test_load_corrupt_json_returns_empty(self, tmp_path):
        """Corrupt JSON file returns empty list."""
        ns = _build_chat_functions()
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        chat_file = data_dir / "chat_history.json"
        chat_file.write_text("{{{CORRUPT JSON!!!", encoding="utf-8")

        ns["_chat_path"] = lambda: str(chat_file)
        result = ns["load_chat_history"]()
        assert result == []

    def test_chat_storage_has_logging(self):
        """chat_storage.py uses logging for errors (not silent pass)."""
        source = _load_storage_source()
        assert "logger" in source
        assert "logging" in source

    def test_save_to_json_returns_true_on_success(self, tmp_path):
        """save_to_json returns True on successful write."""
        from unittest.mock import patch
        from src.chat_storage import save_to_json
        json_file = tmp_path / "chat_history.json"
        with patch("src.chat_storage._chat_path", return_value=str(json_file)):
            result = save_to_json([{"role": "user", "content": "test"}])
            assert result is True


# ===================================================================
# Test class: _chat_path has no volume mount awareness
# ===================================================================

class TestPersistenceStrategy:
    """Verify the persistence strategy: PostgreSQL primary, JSON fallback."""

    def test_chat_storage_module_exists(self):
        """src/chat_storage.py exists."""
        assert os.path.exists(STORAGE_PATH)

    def test_app_imports_from_chat_storage(self):
        """app.py imports persistence functions from chat_storage module."""
        source = _load_app_source()
        assert "from src.chat_storage import" in source

    def test_storage_has_is_persistent_function(self):
        """chat_storage.py exposes is_persistent() check."""
        source = _load_storage_source()
        assert "def is_persistent" in source


# ===================================================================
# Test class: no backup or restore mechanism
# ===================================================================

class TestNoBackupRestoreMechanism:
    """Prove there is no backup, export, or restore capability for chat history."""

    def test_no_backup_function_exists(self):
        """There is no backup_chat_history, export_chat, or restore_chat
        function defined anywhere in app.py."""
        source = _load_app_source()
        tree = ast.parse(source)

        all_functions = [
            node.name for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
        ]

        backup_keywords = ["backup", "export", "restore", "migrate", "snapshot", "dump"]
        backup_functions = [
            fn for fn in all_functions
            if any(kw in fn.lower() for kw in backup_keywords)
        ]
        assert backup_functions == [], (
            f"No backup/restore functions should exist but found: {backup_functions}"
            if backup_functions else "Confirmed: no backup/restore functions exist"
        )
        # The assertion passes when the list is empty -- which proves the absence
        assert len(backup_functions) == 0, "No backup/restore mechanism exists"

    def test_no_s3_or_cloud_storage_references_in_persistence(self):
        """The persistence functions contain no references to S3, GCS, or
        any cloud storage that could serve as a backup target."""
        source = _load_app_source()
        tree = ast.parse(source)

        persistence_funcs = {"_chat_path", "load_chat_history", "save_chat_history"}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in persistence_funcs:
                func_src = ast.get_source_segment(source, node)
                for cloud_kw in ["s3", "boto", "gcs", "azure", "cloud", "bucket", "redis"]:
                    assert cloud_kw not in func_src.lower(), (
                        f"Persistence function should not reference '{cloud_kw}'"
                    )


# ===================================================================
# Test class: fresh deploy loses all history
# ===================================================================

class TestJsonFallbackBehavior:
    """Test JSON fallback behavior (when no DATABASE_URL)."""

    def test_missing_file_returns_empty_list(self, tmp_path):
        """Missing file returns empty list."""
        ns = _build_chat_functions()
        nonexistent = str(tmp_path / "data" / "chat_history.json")
        ns["_chat_path"] = lambda: nonexistent
        result = ns["load_chat_history"]()
        assert result == []

    def test_empty_file_returns_empty_list(self, tmp_path):
        """Empty file returns empty list."""
        ns = _build_chat_functions()
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        chat_file = data_dir / "chat_history.json"
        chat_file.write_text("", encoding="utf-8")
        ns["_chat_path"] = lambda: str(chat_file)
        result = ns["load_chat_history"]()
        assert result == []

    def test_empty_json_array_returns_empty(self, tmp_path):
        """Empty JSON array returns empty list."""
        ns = _build_chat_functions()
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        chat_file = data_dir / "chat_history.json"
        chat_file.write_text("[]", encoding="utf-8")
        ns["_chat_path"] = lambda: str(chat_file)
        result = ns["load_chat_history"]()
        assert result == []

    def test_welcome_message_fallback_exists(self):
        """Welcome message is the fallback for empty history."""
        source = _load_app_source()
        assert "Добрый день! Я Алексей Воронов" in source
        assert "saved = load_chat_history()" in source

    def test_json_save_and_load_round_trip(self, tmp_path):
        """Save then load preserves all data."""
        ns = _build_chat_functions()
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        chat_file = data_dir / "chat_history.json"
        ns["_chat_path"] = lambda: str(chat_file)

        conversation = [
            {"role": "user", "content": "Analyze Q4"},
            {"role": "assistant", "content": "Report...", "agent_name": "Matthias"},
        ]
        ns["save_chat_history"](conversation)
        result = ns["load_chat_history"]()
        assert len(result) == 2
        assert result[0]["content"] == "Analyze Q4"


# ===================================================================
# Test class: format_chat_context truncates messages
# ===================================================================

class TestFormatChatContextTruncation:
    """Prove that format_chat_context() truncates agent messages to 300
    characters, silently discarding potentially critical information."""

    def test_agent_messages_truncated_to_800_chars(self):
        """Agent replies are sliced at [:800] (FIXED from 300), meaning content
        up to 800 characters is preserved in the context window."""
        ns = _build_chat_functions()
        fmt = ns["format_chat_context"]

        long_reply = "A" * 900  # 900-char reply
        messages = [
            {"role": "assistant", "content": long_reply, "agent_name": "Matthias"},
            {"role": "user", "content": "follow up question"},
        ]

        result = fmt(messages)
        assert "A" * 800 in result, "Should contain first 800 chars"
        assert "A" * 801 not in result, (
            "Characters beyond 800 are dropped -- agent provided 900 chars "
            "but only 800 survive into the context"
        )

    def test_truncation_preserves_critical_data_under_800(self):
        """A realistic scenario: a financial report with key numbers fits
        within 800 chars, so the agent CAN reference its own conclusions (FIXED)."""
        ns = _build_chat_functions()
        fmt = ns["format_chat_context"]

        # Pad to push past 300 but stay under 800
        padding = "Анализ финансовых показателей за Q4 2025. " * 8  # ~328 chars
        conclusion = "ИТОГО: чистая прибыль 2.4M USD, ROI 340%"
        full_report = padding + conclusion

        assert len(full_report) > 300, "Report must exceed 300 chars"
        assert len(full_report) < 800, "Report must fit within 800 chars"

        messages = [
            {"role": "assistant", "content": full_report, "agent_name": "Matthias"},
            {"role": "user", "content": "What was the ROI?"},
        ]

        result = fmt(messages)
        assert "ROI 340%" in result, (
            "FIX VERIFIED: The ROI figure is within the 800-char limit "
            "and is now PRESERVED in context."
        )

    def test_user_messages_not_truncated(self):
        """User messages are NOT truncated (no [:300] slice), creating an
        asymmetry: user context is preserved but agent context is cut."""
        ns = _build_chat_functions()
        fmt = ns["format_chat_context"]

        long_user_msg = "B" * 500
        messages = [
            {"role": "user", "content": long_user_msg},
            {"role": "user", "content": "next question"},
        ]

        result = fmt(messages)
        assert "B" * 500 in result, (
            "User messages are kept in full while agent messages are truncated"
        )

    def test_max_messages_limits_context_window(self):
        """format_chat_context uses max_messages=10 by default, meaning only
        the last 10 messages are included. Older context is discarded entirely."""
        ns = _build_chat_functions()
        fmt = ns["format_chat_context"]

        messages = []
        for i in range(20):
            messages.append({"role": "user", "content": f"message_{i}"})

        # Add one more as "current message" (which is excluded by the [-11:-1] slice)
        messages.append({"role": "user", "content": "current"})

        result = fmt(messages, max_messages=10)
        # Older messages should be absent
        assert "message_0" not in result, "Old messages are dropped from context"
        assert "message_5" not in result, "Messages before the window are dropped"
        # Recent messages should be present
        assert "message_19" in result, "Recent messages should be in context"

    def test_truncation_hardcoded_at_800(self):
        """The 800-char limit is hardcoded in the source with [:800] (FIXED from 300)."""
        source = _load_app_source()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "format_chat_context":
                func_src = ast.get_source_segment(source, node)
                assert "[:800]" in func_src, (
                    "The 800-char truncation is hardcoded as [:800]"
                )
                assert "[:300]" not in func_src, "Old 300-char truncation should be removed"
                assert "max_length" not in func_src
                assert "truncate_at" not in func_src
                return
        raise AssertionError("format_chat_context not found")
