"""Tests for Tribute webhook endpoint, notifier, and revenue auto-update."""

import hashlib
import hmac
import json
import os
import sys
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.monitor.webhook_tribute import (
    TRIBUTE_PROJECTS,
    SUBSCRIPTION_EVENTS,
    NOTIFY_EVENTS,
    _get_api_key,
    _try_all_keys,
    _get_revenue_channel,
    _get_display_name,
    tribute_webhook,
)
from src.monitor.webhook_notifier import (
    _get_chat_id,
    notify_ceo,
    notify_cfo,
    _send_telegram,
)
from src.tools.financial.tribute import TributeWebhookVerifier
from src.revenue_tracker import recalculate_channel_from_events


# ── Fixtures ─────────────────────────────────────────────

TEST_API_KEY = "test_tribute_api_key_123"

def _make_signature(body: bytes, key: str = TEST_API_KEY) -> str:
    """Create valid HMAC-SHA256 signature."""
    return hmac.new(key.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _make_event(event_type: str = "newSubscription", **overrides) -> dict:
    """Create a test Tribute webhook event."""
    event = {
        "event": event_type,
        "id": overrides.pop("id", "evt_test_001"),
        "subscription_name": "Premium",
        "subscription_id": "sub_123",
        "telegram_user_id": 12345,
        "channel_name": "Test Channel",
        "amount": 500,
        "currency": "RUB",
        "period": "monthly",
    }
    event.update(overrides)
    return event


class FakeRequest:
    """Minimal Starlette-like request for testing."""

    def __init__(self, body: bytes, headers: dict = None, query_params: dict = None):
        self._body = body
        self.headers = headers or {}
        self.query_params = query_params or {}

    async def body(self):
        return self._body


# ── TributeWebhookVerifier (existing) ───────────────────

class TestWebhookVerifier:
    def test_valid_signature(self):
        body = b'{"event": "test"}'
        sig = _make_signature(body)
        assert TributeWebhookVerifier.verify_signature(body, sig, TEST_API_KEY)

    def test_invalid_signature(self):
        body = b'{"event": "test"}'
        assert not TributeWebhookVerifier.verify_signature(body, "bad_sig", TEST_API_KEY)

    def test_wrong_key(self):
        body = b'{"event": "test"}'
        sig = _make_signature(body, "wrong_key")
        assert not TributeWebhookVerifier.verify_signature(body, sig, TEST_API_KEY)

    def test_empty_body(self):
        sig = _make_signature(b"")
        assert TributeWebhookVerifier.verify_signature(b"", sig, TEST_API_KEY)

    def test_process_event_stores(self):
        payments = []
        with patch("src.tools.financial.tribute._load_payments", return_value=payments), \
             patch("src.tools.financial.tribute._save_payments") as mock_save:
            event = {"event": "newSubscription", "id": "evt_unique_1"}
            TributeWebhookVerifier.process_event(event)
            mock_save.assert_called_once()
            saved = mock_save.call_args[0][0]
            assert len(saved) == 1
            assert saved[0]["id"] == "evt_unique_1"
            assert "received_at" in saved[0]

    def test_process_event_dedup(self):
        existing = [{"id": "evt_dup", "event": "test"}]
        with patch("src.tools.financial.tribute._load_payments", return_value=existing), \
             patch("src.tools.financial.tribute._save_payments") as mock_save:
            TributeWebhookVerifier.process_event({"id": "evt_dup", "event": "test"})
            mock_save.assert_not_called()


# ── API Key Resolution ───────────────────────────────────

class TestApiKeyResolution:
    def test_project_specific_key(self):
        with patch.dict(os.environ, {"TRIBUTE_API_KEY_KRMKTL": "key_krmktl"}):
            assert _get_api_key("krmktl") == "key_krmktl"

    def test_fallback_to_default(self):
        env = {"TRIBUTE_API_KEY": "default_key"}
        with patch.dict(os.environ, env, clear=False):
            # Remove project-specific key if set
            os.environ.pop("TRIBUTE_API_KEY_KRMKTL", None)
            assert _get_api_key("krmktl") == "default_key"

    def test_unknown_project_uses_default(self):
        with patch.dict(os.environ, {"TRIBUTE_API_KEY": "default_key"}):
            assert _get_api_key("unknown_project") == "default_key"

    def test_no_key_returns_none(self):
        with patch.dict(os.environ, {}, clear=True):
            assert _get_api_key("krmktl") is None

    def test_try_all_keys_matches_correct_project(self):
        body = b'{"event": "test"}'
        sig = _make_signature(body, "key_sborka")
        env = {
            "TRIBUTE_API_KEY_KRMKTL": "key_krmktl",
            "TRIBUTE_API_KEY_SBORKA": "key_sborka",
            "TRIBUTE_API_KEY_BOTANICA": "key_botanica",
        }
        with patch.dict(os.environ, env, clear=False):
            result = _try_all_keys(body, sig)
            assert result == "sborka"

    def test_try_all_keys_default_fallback(self):
        body = b'{"event": "test"}'
        sig = _make_signature(body, "default_key")
        env = {"TRIBUTE_API_KEY": "default_key"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("TRIBUTE_API_KEY_KRMKTL", None)
            os.environ.pop("TRIBUTE_API_KEY_SBORKA", None)
            os.environ.pop("TRIBUTE_API_KEY_BOTANICA", None)
            result = _try_all_keys(body, sig)
            assert result == "__default__"

    def test_try_all_keys_no_match(self):
        body = b'{"event": "test"}'
        with patch.dict(os.environ, {}, clear=True):
            result = _try_all_keys(body, "bad_sig")
            assert result is None


# ── Revenue Channel Resolution ───────────────────────────

class TestRevenueChannelResolution:
    def test_explicit_project(self):
        assert _get_revenue_channel("krmktl", {}) == "krmktl"

    def test_from_channel_name(self):
        event = {"channel_name": "Крипто Маркетологи"}
        assert _get_revenue_channel(None, event) == "krmktl"

    def test_unknown_channel(self):
        assert _get_revenue_channel(None, {"channel_name": "Random"}) is None

    def test_display_name(self):
        assert _get_display_name("krmktl") == "Крипто Маркетологи"
        assert _get_display_name("sborka") == "СБОРКА"
        assert _get_display_name(None) == "Unknown"


# ── Webhook Endpoint ─────────────────────────────────────

class TestWebhookEndpoint:
    @pytest.mark.asyncio
    async def test_missing_signature_400(self):
        req = FakeRequest(b'{"event": "test"}', headers={}, query_params={"project": "krmktl"})
        resp = await tribute_webhook(req)
        assert resp.status_code == 400
        body = json.loads(resp.body)
        assert "missing" in body["error"]

    @pytest.mark.asyncio
    async def test_invalid_signature_401(self):
        with patch.dict(os.environ, {"TRIBUTE_API_KEY_KRMKTL": TEST_API_KEY}):
            req = FakeRequest(
                b'{"event": "test"}',
                headers={"trbt-signature": "invalid_signature"},
                query_params={"project": "krmktl"},
            )
            resp = await tribute_webhook(req)
            assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_json_422(self):
        body = b"not json"
        sig = _make_signature(body)
        with patch.dict(os.environ, {"TRIBUTE_API_KEY_KRMKTL": TEST_API_KEY}):
            req = FakeRequest(
                body,
                headers={"trbt-signature": sig},
                query_params={"project": "krmktl"},
            )
            resp = await tribute_webhook(req)
            assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_valid_webhook_200(self):
        event = _make_event()
        body = json.dumps(event).encode()
        sig = _make_signature(body)

        with patch.dict(os.environ, {"TRIBUTE_API_KEY_KRMKTL": TEST_API_KEY}), \
             patch("src.tools.financial.tribute._load_payments", return_value=[]), \
             patch("src.tools.financial.tribute._save_payments"), \
             patch("src.monitor.webhook_tribute.notify_ceo", new_callable=AsyncMock) as mock_ceo, \
             patch("src.monitor.webhook_tribute.notify_cfo", new_callable=AsyncMock) as mock_cfo, \
             patch("src.monitor.webhook_tribute._update_revenue_from_event"):
            req = FakeRequest(
                body,
                headers={"trbt-signature": sig},
                query_params={"project": "krmktl"},
            )
            resp = await tribute_webhook(req)
            assert resp.status_code == 200
            data = json.loads(resp.body)
            assert data["ok"] is True
            assert data["event"] == "newSubscription"
            mock_ceo.assert_called_once()

    @pytest.mark.asyncio
    async def test_auto_project_detection(self):
        event = _make_event()
        body = json.dumps(event).encode()
        sig = _make_signature(body, "key_botanica")

        with patch.dict(os.environ, {
            "TRIBUTE_API_KEY_KRMKTL": "key_krmktl",
            "TRIBUTE_API_KEY_SBORKA": "key_sborka",
            "TRIBUTE_API_KEY_BOTANICA": "key_botanica",
        }), \
             patch("src.tools.financial.tribute._load_payments", return_value=[]), \
             patch("src.tools.financial.tribute._save_payments"), \
             patch("src.monitor.webhook_tribute.notify_ceo", new_callable=AsyncMock), \
             patch("src.monitor.webhook_tribute.notify_cfo", new_callable=AsyncMock), \
             patch("src.monitor.webhook_tribute._update_revenue_from_event") as mock_update:
            req = FakeRequest(
                body,
                headers={"trbt-signature": sig},
                query_params={},
            )
            resp = await tribute_webhook(req)
            assert resp.status_code == 200
            mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_renewed_subscription_no_notification(self):
        event = _make_event("renewedSubscription")
        body = json.dumps(event).encode()
        sig = _make_signature(body)

        with patch.dict(os.environ, {"TRIBUTE_API_KEY_KRMKTL": TEST_API_KEY}), \
             patch("src.tools.financial.tribute._load_payments", return_value=[]), \
             patch("src.tools.financial.tribute._save_payments"), \
             patch("src.monitor.webhook_tribute.notify_ceo", new_callable=AsyncMock) as mock_ceo, \
             patch("src.monitor.webhook_tribute.notify_cfo", new_callable=AsyncMock) as mock_cfo, \
             patch("src.monitor.webhook_tribute._update_revenue_from_event"):
            req = FakeRequest(
                body,
                headers={"trbt-signature": sig},
                query_params={"project": "krmktl"},
            )
            resp = await tribute_webhook(req)
            assert resp.status_code == 200
            mock_ceo.assert_not_called()
            mock_cfo.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_api_key_for_project_400(self):
        with patch.dict(os.environ, {}, clear=True):
            req = FakeRequest(
                b'{"event": "test"}',
                headers={"trbt-signature": "any"},
                query_params={"project": "krmktl"},
            )
            resp = await tribute_webhook(req)
            assert resp.status_code == 400
            assert "no API key" in json.loads(resp.body)["error"]

    @pytest.mark.asyncio
    async def test_non_dict_json_422(self):
        body = b'[1, 2, 3]'
        sig = _make_signature(body)
        with patch.dict(os.environ, {"TRIBUTE_API_KEY_KRMKTL": TEST_API_KEY}):
            req = FakeRequest(
                body,
                headers={"trbt-signature": sig},
                query_params={"project": "krmktl"},
            )
            resp = await tribute_webhook(req)
            assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_channel_tag_added_to_event(self):
        event = _make_event()
        body = json.dumps(event).encode()
        sig = _make_signature(body)
        stored_events = []

        def fake_process(evt):
            stored_events.append(evt)

        with patch.dict(os.environ, {"TRIBUTE_API_KEY_KRMKTL": TEST_API_KEY}), \
             patch("src.monitor.webhook_tribute.TributeWebhookVerifier.process_event", side_effect=fake_process), \
             patch("src.monitor.webhook_tribute.notify_ceo", new_callable=AsyncMock), \
             patch("src.monitor.webhook_tribute.notify_cfo", new_callable=AsyncMock), \
             patch("src.monitor.webhook_tribute._update_revenue_from_event"):
            req = FakeRequest(
                body,
                headers={"trbt-signature": sig},
                query_params={"project": "krmktl"},
            )
            resp = await tribute_webhook(req)
            assert resp.status_code == 200
            assert len(stored_events) == 1
            assert stored_events[0]["_channel"] == "krmktl"


# ── Revenue Recalculation ────────────────────────────────

class TestRevenueRecalculation:
    def _make_payments(self, channel: str) -> list[dict]:
        """Create a series of subscription events."""
        return [
            {"event": "newSubscription", "telegram_user_id": 1, "amount": 500, "currency": "RUB", "_channel": channel, "received_at": "2026-02-01T10:00:00"},
            {"event": "newSubscription", "telegram_user_id": 2, "amount": 500, "currency": "RUB", "_channel": channel, "received_at": "2026-02-02T10:00:00"},
            {"event": "newSubscription", "telegram_user_id": 3, "amount": 500, "currency": "RUB", "_channel": channel, "received_at": "2026-02-03T10:00:00"},
            {"event": "cancelledSubscription", "telegram_user_id": 1, "_channel": channel, "received_at": "2026-02-05T10:00:00"},
        ]

    def test_calculates_active_members(self):
        payments = self._make_payments("krmktl")
        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        tmp.write(b"{}"); tmp.close()

        with patch("src.tools.financial.tribute._load_payments", return_value=payments), \
             patch("src.revenue_tracker._REVENUE_PATH", tmp.name):
            result = recalculate_channel_from_events("krmktl")
            assert result["members"] == 2  # 3 new - 1 cancelled
            assert result["events_counted"] == 4
            assert result["mrr"] > 0

        os.unlink(tmp.name)

    def test_empty_payments(self):
        with patch("src.tools.financial.tribute._load_payments", return_value=[]):
            result = recalculate_channel_from_events("krmktl")
            assert result["mrr"] == 0.0
            assert result["members"] == 0

    def test_filters_by_channel(self):
        payments = [
            {"event": "newSubscription", "telegram_user_id": 1, "amount": 10, "currency": "USD", "_channel": "krmktl", "received_at": "2026-02-01T10:00:00"},
            {"event": "newSubscription", "telegram_user_id": 2, "amount": 10, "currency": "USD", "_channel": "sborka", "received_at": "2026-02-01T10:00:00"},
        ]
        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        tmp.write(b"{}"); tmp.close()

        with patch("src.tools.financial.tribute._load_payments", return_value=payments), \
             patch("src.revenue_tracker._REVENUE_PATH", tmp.name):
            result = recalculate_channel_from_events("krmktl")
            assert result["members"] == 1

        os.unlink(tmp.name)

    def test_renewed_keeps_subscriber(self):
        payments = [
            {"event": "newSubscription", "telegram_user_id": 1, "amount": 10, "currency": "USD", "_channel": "krmktl", "received_at": "2026-02-01T10:00:00"},
            {"event": "renewedSubscription", "telegram_user_id": 1, "amount": 10, "currency": "USD", "_channel": "krmktl", "received_at": "2026-02-15T10:00:00"},
        ]
        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        tmp.write(b"{}"); tmp.close()

        with patch("src.tools.financial.tribute._load_payments", return_value=payments), \
             patch("src.revenue_tracker._REVENUE_PATH", tmp.name):
            result = recalculate_channel_from_events("krmktl")
            assert result["members"] == 1  # Still 1 active
            assert result["events_counted"] == 2

        os.unlink(tmp.name)


# ── Webhook Notifier ─────────────────────────────────────

class TestWebhookNotifier:
    def test_get_chat_id_from_env(self):
        with patch.dict(os.environ, {"TELEGRAM_CEO_ALLOWED_USERS": "123456,789"}):
            assert _get_chat_id() == "123456"

    def test_get_chat_id_empty(self):
        with patch.dict(os.environ, {}, clear=True):
            assert _get_chat_id() is None

    @pytest.mark.asyncio
    async def test_notify_ceo_no_token(self):
        with patch.dict(os.environ, {}, clear=True):
            result = await notify_ceo("test message")
            assert result is False

    @pytest.mark.asyncio
    async def test_notify_ceo_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch.dict(os.environ, {
            "TELEGRAM_CEO_BOT_TOKEN": "fake_token",
            "TELEGRAM_CEO_ALLOWED_USERS": "123456",
        }), patch("src.monitor.webhook_notifier.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_instance.post = AsyncMock(return_value=mock_resp)
            mock_client.return_value = mock_instance

            result = await notify_ceo("Test notification")
            assert result is True

    @pytest.mark.asyncio
    async def test_notify_failure_returns_false(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.text = "Forbidden"

        with patch.dict(os.environ, {
            "TELEGRAM_CEO_BOT_TOKEN": "fake_token",
            "TELEGRAM_CEO_ALLOWED_USERS": "123456",
        }), patch("src.monitor.webhook_notifier.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_instance.post = AsyncMock(return_value=mock_resp)
            mock_client.return_value = mock_instance

            result = await notify_ceo("Test notification")
            assert result is False


# ── Project Configuration ────────────────────────────────

class TestProjectConfig:
    def test_three_projects_configured(self):
        assert len(TRIBUTE_PROJECTS) == 3
        assert "krmktl" in TRIBUTE_PROJECTS
        assert "sborka" in TRIBUTE_PROJECTS
        assert "botanica" in TRIBUTE_PROJECTS

    def test_subscription_events_defined(self):
        assert "newSubscription" in SUBSCRIPTION_EVENTS
        assert "renewedSubscription" in SUBSCRIPTION_EVENTS
        assert "cancelledSubscription" in SUBSCRIPTION_EVENTS

    def test_notify_events_subset(self):
        # Only new and cancelled trigger notifications (not renewals)
        assert "newSubscription" in NOTIFY_EVENTS
        assert "cancelledSubscription" in NOTIFY_EVENTS
        assert "renewedSubscription" not in NOTIFY_EVENTS

    def test_each_project_has_env_key(self):
        for key, config in TRIBUTE_PROJECTS.items():
            assert "env_key" in config
            assert "revenue_channel" in config
            assert "display_name" in config
