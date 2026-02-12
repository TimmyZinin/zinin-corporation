"""Tests for per-user chat context isolation in CEO and Yuki bots."""

import pytest


# ──────────────────────────────────────────────────────────
# CEO Bot: per-user context isolation
# ──────────────────────────────────────────────────────────

class TestCeoChatContextIsolation:
    """Verify that CEO bot uses per-user chat context (not shared global)."""

    def _reset_module(self):
        """Reset the module-level state."""
        from src.telegram_ceo.handlers import messages as mod
        mod._chat_contexts.clear()
        return mod

    def test_chat_contexts_is_dict(self):
        from src.telegram_ceo.handlers import messages as mod
        assert isinstance(mod._chat_contexts, dict)

    def test_get_context_creates_new_list_for_user(self):
        mod = self._reset_module()
        ctx = mod._get_context(100)
        assert isinstance(ctx, list)
        assert len(ctx) == 0

    def test_get_context_returns_same_list_for_same_user(self):
        mod = self._reset_module()
        ctx1 = mod._get_context(100)
        ctx1.append({"role": "user", "text": "hello"})
        ctx2 = mod._get_context(100)
        assert ctx2 is ctx1
        assert len(ctx2) == 1

    def test_get_context_isolates_users(self):
        mod = self._reset_module()
        ctx_user1 = mod._get_context(100)
        ctx_user2 = mod._get_context(200)
        ctx_user1.append({"role": "user", "text": "from user 1"})
        assert len(ctx_user2) == 0
        assert len(ctx_user1) == 1

    def test_context_does_not_leak_between_users(self):
        mod = self._reset_module()
        ctx_a = mod._get_context(111)
        ctx_b = mod._get_context(222)
        ctx_a.append({"role": "user", "text": "secret A"})
        ctx_b.append({"role": "user", "text": "secret B"})
        assert ctx_a[0]["text"] == "secret A"
        assert ctx_b[0]["text"] == "secret B"
        assert len(ctx_a) == 1
        assert len(ctx_b) == 1

    def test_multiple_users_independent_growth(self):
        mod = self._reset_module()
        for uid in [1, 2, 3]:
            ctx = mod._get_context(uid)
            for i in range(uid * 5):
                ctx.append({"role": "user", "text": f"msg {i}"})
        assert len(mod._get_context(1)) == 5
        assert len(mod._get_context(2)) == 10
        assert len(mod._get_context(3)) == 15

    def test_max_context_constant(self):
        from src.telegram_ceo.handlers import messages as mod
        assert mod.MAX_CONTEXT == 20

    def test_format_context_user_messages(self):
        from src.telegram_ceo.handlers.messages import _format_context
        msgs = [
            {"role": "user", "text": "привет"},
            {"role": "assistant", "text": "здравствуйте"},
        ]
        result = _format_context(msgs)
        assert "Тим: привет" in result
        assert "Алексей: здравствуйте" in result

    def test_format_context_truncates_assistant(self):
        from src.telegram_ceo.handlers.messages import _format_context
        long_text = "x" * 1000
        msgs = [{"role": "assistant", "text": long_text}]
        result = _format_context(msgs)
        assert len(result) < 900  # truncated to 800

    def test_format_context_empty(self):
        from src.telegram_ceo.handlers.messages import _format_context
        assert _format_context([]) == ""

    def test_no_global_chat_context_list(self):
        """Ensure there's no leftover global _chat_context list."""
        from src.telegram_ceo.handlers import messages as mod
        assert not hasattr(mod, "_chat_context") or isinstance(
            getattr(mod, "_chat_context", None), type(None)
        )


# ──────────────────────────────────────────────────────────
# Yuki Bot: per-user context isolation
# ──────────────────────────────────────────────────────────

class TestYukiChatContextIsolation:
    """Verify that Yuki bot uses per-user chat context (not shared global)."""

    def _reset_module(self):
        from src.telegram_yuki.handlers import messages as mod
        mod._chat_contexts.clear()
        return mod

    def test_chat_contexts_is_dict(self):
        from src.telegram_yuki.handlers import messages as mod
        assert isinstance(mod._chat_contexts, dict)

    def test_get_context_creates_new_list_for_user(self):
        mod = self._reset_module()
        ctx = mod._get_context(300)
        assert isinstance(ctx, list)
        assert len(ctx) == 0

    def test_get_context_returns_same_list_for_same_user(self):
        mod = self._reset_module()
        ctx1 = mod._get_context(300)
        ctx1.append({"role": "user", "text": "hello"})
        ctx2 = mod._get_context(300)
        assert ctx2 is ctx1
        assert len(ctx2) == 1

    def test_get_context_isolates_users(self):
        mod = self._reset_module()
        ctx_user1 = mod._get_context(300)
        ctx_user2 = mod._get_context(400)
        ctx_user1.append({"role": "user", "text": "from user 300"})
        assert len(ctx_user2) == 0

    def test_context_does_not_leak(self):
        mod = self._reset_module()
        ctx_a = mod._get_context(500)
        ctx_b = mod._get_context(600)
        ctx_a.append({"role": "user", "text": "alpha"})
        ctx_b.append({"role": "user", "text": "beta"})
        ctx_b.append({"role": "assistant", "text": "gamma"})
        assert len(ctx_a) == 1
        assert len(ctx_b) == 2

    def test_max_context_constant(self):
        from src.telegram_yuki.handlers import messages as mod
        assert mod.MAX_CONTEXT == 20

    def test_format_context_yuki(self):
        from src.telegram_yuki.handlers.messages import _format_context
        msgs = [
            {"role": "user", "text": "напиши пост"},
            {"role": "assistant", "text": "вот пост"},
        ]
        result = _format_context(msgs)
        assert "Тим: напиши пост" in result
        assert "Юки: вот пост" in result

    def test_format_context_truncates_assistant(self):
        from src.telegram_yuki.handlers.messages import _format_context
        long_text = "y" * 1000
        msgs = [{"role": "assistant", "text": long_text}]
        result = _format_context(msgs)
        assert len(result) < 900

    def test_no_global_chat_context_list(self):
        """Ensure there's no leftover global _chat_context list."""
        from src.telegram_yuki.handlers import messages as mod
        assert not hasattr(mod, "_chat_context") or isinstance(
            getattr(mod, "_chat_context", None), type(None)
        )
