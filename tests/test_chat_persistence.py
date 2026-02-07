"""Tests proving chat history persistence problems on Railway (ephemeral filesystem).

These tests demonstrate that:
- Chat history relies solely on a local JSON file
- DATABASE_URL is checked in UI but never used for chat storage
- Exceptions in save are silently swallowed
- No volume mount or external storage is configured
- No backup/restore mechanism exists
- Fresh deploys lose all history, resetting to a single welcome message
- format_chat_context() truncates agent replies to 300 chars, losing information
"""

import sys
import os
import json
import inspect
import ast

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Import the functions under test directly from app.py.
# We do a manual import to avoid Streamlit's runtime requirements.
APP_DIR = os.path.join(os.path.dirname(__file__), "..")
APP_PATH = os.path.join(APP_DIR, "app.py")


def _load_app_source() -> str:
    with open(APP_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _load_app_ast() -> ast.Module:
    return ast.parse(_load_app_source())


# ---------------------------------------------------------------------------
# Helpers: extract the three functions from app.py without importing Streamlit
# We exec only the relevant function bodies inside a controlled namespace.
# ---------------------------------------------------------------------------
def _build_chat_functions(tmp_path=None):
    """Build the chat persistence functions in an isolated namespace.

    If tmp_path is provided, the working directory context will make
    _chat_path() resolve inside tmp_path.
    """
    ns = {"os": os, "json": json}
    source = _load_app_source()
    tree = ast.parse(source)

    func_names = {"_chat_path", "load_chat_history", "save_chat_history", "format_chat_context"}
    func_sources = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in func_names:
                func_sources.append(ast.get_source_segment(source, node))

    for src in func_sources:
        exec(src, ns)

    return ns


# ===================================================================
# Test class: chat storage relies on local JSON file
# ===================================================================

class TestChatStorageIsLocalFile:
    """Prove that all chat persistence goes through a local JSON file."""

    def test_chat_path_returns_json_file_path(self):
        """_chat_path() always returns a path ending in chat_history.json,
        confirming storage is a plain file, not a database or external service."""
        ns = _build_chat_functions()
        path = ns["_chat_path"]()
        assert path.endswith("chat_history.json"), (
            f"Expected path ending with chat_history.json, got: {path}"
        )

    def test_chat_path_only_checks_two_local_paths(self):
        """_chat_path() only considers /app/data/ and data/ -- both are local
        filesystem paths. No environment variable, no volume mount path, no
        cloud storage URL is ever consulted."""
        source = _load_app_source()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_chat_path":
                func_source = ast.get_source_segment(source, node)
                # Must contain only these two hardcoded paths
                assert "/app/data/chat_history.json" in func_source
                assert "data/chat_history.json" in func_source
                # Must NOT reference any env var for storage location
                assert "os.getenv" not in func_source, (
                    "_chat_path() does not read any environment variable for storage path"
                )
                assert "os.environ" not in func_source
                return
        raise AssertionError("_chat_path function not found in app.py")

    def test_save_writes_json_to_local_file(self, tmp_path):
        """save_chat_history() writes a JSON file to the local filesystem.
        This file will be lost on Railway redeploy because Railway containers
        use ephemeral storage."""
        ns = _build_chat_functions()
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        chat_file = data_dir / "chat_history.json"

        messages = [
            {"role": "assistant", "content": "Hello", "agent_name": "Alexey"},
            {"role": "user", "content": "Hi"},
        ]

        # Patch _chat_path to use our tmp location
        ns["_chat_path"] = lambda: str(chat_file)
        ns["save_chat_history"](messages)

        assert chat_file.exists(), "JSON file should have been created on disk"
        loaded = json.loads(chat_file.read_text(encoding="utf-8"))
        assert loaded == messages

    def test_load_reads_from_local_file(self, tmp_path):
        """load_chat_history() reads from a local JSON file -- the same file
        that disappears when Railway rebuilds the container."""
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

class TestDatabaseUrlIsCosmetic:
    """Prove that DATABASE_URL is checked in the UI but never wired into
    the chat persistence layer."""

    def test_database_url_checked_in_env_status(self):
        """check_env_vars() reads DATABASE_URL and the sidebar shows a green
        checkmark when it is set, implying database storage is active."""
        source = _load_app_source()
        # DATABASE_URL is listed in optional env vars
        assert "DATABASE_URL" in source
        # UI shows a success message when DATABASE_URL exists
        assert "PostgreSQL" in source, (
            "UI tells the user PostgreSQL is connected when DATABASE_URL is set"
        )

    def test_save_chat_history_never_references_database(self):
        """save_chat_history() source code contains zero references to
        DATABASE_URL, psycopg2, sqlalchemy, or any database driver.
        It only writes to a local JSON file."""
        source = _load_app_source()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "save_chat_history":
                func_src = ast.get_source_segment(source, node)
                for keyword in ["DATABASE_URL", "psycopg", "sqlalchemy", "postgres",
                                "sqlite", "database", "cursor", "conn", "engine"]:
                    assert keyword.lower() not in func_src.lower(), (
                        f"save_chat_history should not reference '{keyword}' but it does"
                    )
                return
        raise AssertionError("save_chat_history not found in source")

    def test_load_chat_history_never_references_database(self):
        """load_chat_history() likewise has no database logic -- only JSON file I/O."""
        source = _load_app_source()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "load_chat_history":
                func_src = ast.get_source_segment(source, node)
                for keyword in ["DATABASE_URL", "psycopg", "sqlalchemy", "postgres",
                                "sqlite", "database", "cursor", "conn", "engine"]:
                    assert keyword.lower() not in func_src.lower(), (
                        f"load_chat_history should not reference '{keyword}' but it does"
                    )
                return
        raise AssertionError("load_chat_history not found in source")


# ===================================================================
# Test class: save_chat_history silently swallows all exceptions
# ===================================================================

class TestSaveSilentlySwallowsExceptions:
    """Prove that save_chat_history() catches Exception and does nothing,
    meaning data loss is completely invisible to the user."""

    def test_bare_except_in_save_source(self):
        """The save function has a bare 'except Exception: pass' block,
        which means ANY failure (disk full, permission denied, encoding error)
        is silently ignored."""
        source = _load_app_source()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "save_chat_history":
                func_src = ast.get_source_segment(source, node)
                assert "except Exception" in func_src, (
                    "save_chat_history should have a broad except clause"
                )
                # Check that the except block only contains 'pass' (no logging)
                assert "logging" not in func_src.lower()
                assert "log(" not in func_src
                assert "print(" not in func_src
                assert "st.error" not in func_src
                assert "st.warning" not in func_src
                return
        raise AssertionError("save_chat_history not found")

    def test_save_to_readonly_path_raises_no_error(self, tmp_path):
        """When saving to a path that cannot be written (e.g. read-only dir),
        the function returns silently instead of raising or notifying."""
        ns = _build_chat_functions()

        # Point to a path inside a non-existent deeply nested structure
        # under a read-only directory
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        os.chmod(str(readonly_dir), 0o444)

        impossible_path = str(readonly_dir / "subdir" / "chat_history.json")
        ns["_chat_path"] = lambda: impossible_path

        # This must NOT raise -- that is the bug: silent failure
        ns["save_chat_history"]([{"role": "user", "content": "lost message"}])

        # The file was not created (data is lost), but no error was raised
        assert not os.path.exists(impossible_path), (
            "File should not exist because the directory is read-only"
        )

        # Cleanup: restore permissions so pytest can clean up tmp_path
        os.chmod(str(readonly_dir), 0o755)

    def test_load_also_swallows_exceptions(self):
        """load_chat_history() also has a bare except that swallows errors
        such as corrupt JSON, returning an empty list instead of reporting."""
        source = _load_app_source()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "load_chat_history":
                func_src = ast.get_source_segment(source, node)
                assert "except Exception" in func_src
                assert "pass" in func_src
                return
        raise AssertionError("load_chat_history not found")

    def test_corrupt_json_returns_empty_silently(self, tmp_path):
        """If the JSON file is corrupt, load returns [] with no warning.
        The user sees a fresh chat as if nothing happened."""
        ns = _build_chat_functions()
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        chat_file = data_dir / "chat_history.json"
        chat_file.write_text("{{{CORRUPT JSON!!!", encoding="utf-8")

        ns["_chat_path"] = lambda: str(chat_file)
        result = ns["load_chat_history"]()
        assert result == [], "Corrupt JSON silently returns empty list"


# ===================================================================
# Test class: _chat_path has no volume mount awareness
# ===================================================================

class TestNoVolumeMountSupport:
    """Prove that _chat_path() has no mechanism to use Railway volumes,
    persistent disks, or any external mount point."""

    def test_no_env_var_for_storage_path(self):
        """There is no CHAT_STORAGE_PATH, DATA_DIR, or PERSISTENT_DIR
        environment variable consulted for choosing the storage location."""
        source = _load_app_source()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_chat_path":
                func_src = ast.get_source_segment(source, node)
                assert "getenv" not in func_src, (
                    "_chat_path reads no env vars, so there is no way to "
                    "configure a persistent volume mount path at deploy time"
                )
                return
        raise AssertionError("_chat_path not found")

    def test_hardcoded_paths_are_inside_container(self):
        """Both candidate paths (/app/data/ and data/) are inside the
        container filesystem. /app is the typical WORKDIR in Dockerfiles.
        Neither points to a Railway volume mount (typically /data or /mnt)."""
        ns = _build_chat_functions()
        source = _load_app_source()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_chat_path":
                func_src = ast.get_source_segment(source, node)
                # The two hardcoded paths
                assert "/app/data/chat_history.json" in func_src
                assert "data/chat_history.json" in func_src
                # Neither is a Railway volume mount location
                assert "/mnt/" not in func_src
                # No configurable volume path
                assert "RAILWAY_VOLUME" not in func_src
                return
        raise AssertionError("_chat_path not found")

    def test_path_falls_back_to_relative_when_app_data_missing(self, tmp_path):
        """When /app/data/ does not exist (as on a dev machine),
        _chat_path() falls back to relative 'data/chat_history.json'
        which is inside the ephemeral container working directory."""
        ns = _build_chat_functions()
        # On a dev machine, /app/data/ typically does not exist
        path = ns["_chat_path"]()
        # It must be one of the two hardcoded values
        assert path in ["/app/data/chat_history.json", "data/chat_history.json"]


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

class TestFreshDeployLosesHistory:
    """Prove that a fresh container (no data/chat_history.json) starts
    with zero history and only a single welcome message."""

    def test_missing_file_returns_empty_list(self, tmp_path):
        """When chat_history.json does not exist (fresh Railway deploy),
        load_chat_history() returns an empty list."""
        ns = _build_chat_functions()
        nonexistent = str(tmp_path / "data" / "chat_history.json")
        ns["_chat_path"] = lambda: nonexistent

        result = ns["load_chat_history"]()
        assert result == [], (
            "Fresh deploy with no file should return empty list, triggering "
            "the welcome message fallback in main()"
        )

    def test_empty_file_returns_empty_list(self, tmp_path):
        """An empty file (0 bytes) also returns [], losing any indication
        that history was supposed to be there."""
        ns = _build_chat_functions()
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        chat_file = data_dir / "chat_history.json"
        chat_file.write_text("", encoding="utf-8")

        ns["_chat_path"] = lambda: str(chat_file)
        result = ns["load_chat_history"]()
        assert result == []

    def test_empty_json_array_returns_empty_list(self, tmp_path):
        """An empty JSON array '[]' also triggers fresh-start behavior because
        load_chat_history checks 'len(data) > 0'."""
        ns = _build_chat_functions()
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        chat_file = data_dir / "chat_history.json"
        chat_file.write_text("[]", encoding="utf-8")

        ns["_chat_path"] = lambda: str(chat_file)
        result = ns["load_chat_history"]()
        assert result == [], "Empty array returns [] -- same as no history"

    def test_welcome_message_is_only_fallback(self):
        """When load_chat_history() returns [], the app creates a hardcoded
        welcome message. This is the ONLY recovery mechanism -- there is no
        attempt to restore from a backup, database, or remote storage."""
        source = _load_app_source()
        # The welcome message pattern
        assert "Добрый день! Я Алексей Воронов" in source, (
            "The hardcoded welcome message is the sole fallback for empty history"
        )
        # Verify it is gated behind `if saved:` / `else:`
        assert "saved = load_chat_history()" in source
        assert "st.session_state.messages = saved" in source

    def test_previous_conversations_irrecoverable_after_redeploy(self, tmp_path):
        """Simulate a redeploy scenario: save messages, delete the file
        (simulating container replacement), then load. All history is gone."""
        ns = _build_chat_functions()
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        chat_file = data_dir / "chat_history.json"

        ns["_chat_path"] = lambda: str(chat_file)

        # User has a conversation
        conversation = [
            {"role": "assistant", "content": "Welcome!", "agent_name": "Alexey"},
            {"role": "user", "content": "Analyze our Q4 revenue"},
            {"role": "assistant", "content": "Revenue analysis: ...(detailed report)...",
             "agent_name": "Matthias"},
            {"role": "user", "content": "Now plan the marketing strategy"},
            {"role": "assistant", "content": "Marketing strategy: ...(detailed plan)...",
             "agent_name": "Yuki"},
        ]
        ns["save_chat_history"](conversation)
        assert chat_file.exists()
        assert len(json.loads(chat_file.read_text())) == 5

        # === Railway redeploy happens: container is destroyed and recreated ===
        chat_file.unlink()  # File is gone with the old container

        # New container starts
        result = ns["load_chat_history"]()
        assert result == [], (
            "After redeploy, ALL conversation history is permanently lost. "
            "The revenue analysis and marketing strategy are irrecoverable."
        )


# ===================================================================
# Test class: format_chat_context truncates messages
# ===================================================================

class TestFormatChatContextTruncation:
    """Prove that format_chat_context() truncates agent messages to 300
    characters, silently discarding potentially critical information."""

    def test_agent_messages_truncated_to_300_chars(self):
        """Agent replies are sliced at [:300], meaning any content beyond
        300 characters is silently dropped from the context window."""
        ns = _build_chat_functions()
        fmt = ns["format_chat_context"]

        long_reply = "A" * 500  # 500-char reply
        messages = [
            {"role": "assistant", "content": long_reply, "agent_name": "Matthias"},
            {"role": "user", "content": "follow up question"},
        ]

        result = fmt(messages)
        # The agent message in context should be truncated
        assert "A" * 300 in result, "Should contain first 300 chars"
        assert "A" * 301 not in result, (
            "Characters beyond 300 are dropped -- agent provided 500 chars "
            "but only 300 survive into the context"
        )

    def test_truncation_loses_critical_data(self):
        """A realistic scenario: a financial report with key numbers at the
        end is truncated, so the agent loses access to its own conclusions."""
        ns = _build_chat_functions()
        fmt = ns["format_chat_context"]

        # Pad to push the conclusion past 300 chars
        padding = "Анализ финансовых показателей за Q4 2025. " * 8  # ~328 chars
        conclusion = "ИТОГО: чистая прибыль 2.4M USD, ROI 340%"
        full_report = padding + conclusion

        assert len(full_report) > 300, "Report must exceed 300 chars for this test"

        messages = [
            {"role": "assistant", "content": full_report, "agent_name": "Matthias"},
            {"role": "user", "content": "What was the ROI?"},
        ]

        result = fmt(messages)
        assert "ROI 340%" not in result, (
            "The ROI figure is past the 300-char cutoff and is LOST from context. "
            "The agent cannot reference its own previous conclusion."
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

    def test_truncation_hardcoded_not_configurable(self):
        """The 300-char limit is hardcoded in the source with [:300].
        There is no parameter or env var to adjust it."""
        source = _load_app_source()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "format_chat_context":
                func_src = ast.get_source_segment(source, node)
                assert "[:300]" in func_src, (
                    "The 300-char truncation is hardcoded as [:300]"
                )
                # No configurable max_content_length parameter
                assert "max_content" not in func_src
                assert "max_length" not in func_src
                assert "truncate_at" not in func_src
                return
        raise AssertionError("format_chat_context not found")
