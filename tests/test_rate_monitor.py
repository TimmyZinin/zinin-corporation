"""Tests for src/rate_monitor.py — Rate Limit Monitor."""

import sys
import os
import tempfile
from unittest.mock import patch
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.rate_monitor import (
    PROVIDER_LIMITS,
    ApiCall,
    RateLimitAlert,
    RateMonitorStore,
    record_api_call,
    get_provider_usage,
    get_all_usage,
    get_rate_alerts,
    get_usage_summary,
    MAX_CALLS,
    MAX_ALERTS,
    _load_store,
    _save_store,
    _count_calls,
)


def _tmp_store():
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    f.close()
    return f.name


# ── Models ────────────────────────────────────────────────

class TestModels:
    def test_api_call_defaults(self):
        c = ApiCall(provider="openrouter")
        assert c.provider == "openrouter"
        assert c.success is True
        assert c.agent == ""
        assert c.timestamp != ""

    def test_api_call_with_details(self):
        c = ApiCall(
            provider="openrouter",
            agent="smm",
            success=False,
            status_code=429,
            latency_ms=150,
        )
        assert c.status_code == 429
        assert c.latency_ms == 150
        assert c.success is False

    def test_rate_limit_alert(self):
        a = RateLimitAlert(
            provider="openrouter",
            window="minute",
            current=50,
            limit=60,
            pct=83.3,
        )
        assert a.provider == "openrouter"
        assert a.pct == 83.3

    def test_store_defaults(self):
        store = RateMonitorStore()
        assert store.calls == []
        assert store.alerts == []


# ── Provider Limits ───────────────────────────────────────

class TestProviderLimits:
    def test_known_providers(self):
        expected = {"openrouter", "elevenlabs", "openai", "coingecko", "groq"}
        assert expected.issubset(set(PROVIDER_LIMITS.keys()))

    def test_each_has_required_fields(self):
        for key, limits in PROVIDER_LIMITS.items():
            assert "name" in limits, f"{key} missing name"
            assert "requests_per_minute" in limits, f"{key} missing rpm"
            assert "requests_per_day" in limits, f"{key} missing daily"
            assert "warn_pct" in limits, f"{key} missing warn_pct"

    def test_warn_pct_range(self):
        for key, limits in PROVIDER_LIMITS.items():
            assert 50 <= limits["warn_pct"] <= 100, f"{key} warn_pct out of range"


# ── Record API Call ───────────────────────────────────────

class TestRecordApiCall:
    def test_record_call(self):
        path = _tmp_store()
        with patch("src.rate_monitor._store_path", return_value=path):
            result = record_api_call("openrouter", agent="smm")
            store = _load_store()
            assert len(store.calls) == 1
            assert store.calls[0].provider == "openrouter"
            assert store.calls[0].agent == "smm"
        os.unlink(path)

    def test_record_multiple_calls(self):
        path = _tmp_store()
        with patch("src.rate_monitor._store_path", return_value=path):
            record_api_call("openrouter")
            record_api_call("elevenlabs")
            record_api_call("openrouter")
            store = _load_store()
            assert len(store.calls) == 3
        os.unlink(path)

    def test_record_failed_call(self):
        path = _tmp_store()
        with patch("src.rate_monitor._store_path", return_value=path):
            record_api_call("openrouter", success=False, status_code=429)
            store = _load_store()
            assert store.calls[0].success is False
            assert store.calls[0].status_code == 429
        os.unlink(path)

    def test_no_alert_under_threshold(self):
        path = _tmp_store()
        with patch("src.rate_monitor._store_path", return_value=path):
            alert = record_api_call("openrouter")
            assert alert is None
        os.unlink(path)

    def test_calls_capped(self):
        path = _tmp_store()
        with patch("src.rate_monitor._store_path", return_value=path):
            for i in range(MAX_CALLS + 50):
                record_api_call("openrouter")
            store = _load_store()
            assert len(store.calls) <= MAX_CALLS
        os.unlink(path)


# ── Provider Usage ────────────────────────────────────────

class TestProviderUsage:
    def test_empty_usage(self):
        path = _tmp_store()
        with patch("src.rate_monitor._store_path", return_value=path):
            usage = get_provider_usage("openrouter", minutes=60)
            assert usage["total_calls"] == 0
            assert usage["provider"] == "openrouter"
        os.unlink(path)

    def test_usage_counts(self):
        path = _tmp_store()
        with patch("src.rate_monitor._store_path", return_value=path):
            record_api_call("openrouter", success=True)
            record_api_call("openrouter", success=True)
            record_api_call("openrouter", success=False)
            usage = get_provider_usage("openrouter", minutes=60)
            assert usage["total_calls"] == 3
            assert usage["success"] == 2
            assert usage["failed"] == 1
        os.unlink(path)

    def test_usage_includes_limits(self):
        path = _tmp_store()
        with patch("src.rate_monitor._store_path", return_value=path):
            usage = get_provider_usage("openrouter")
            assert usage["rpm_limit"] == 60
            assert usage["daily_limit"] == 5000
        os.unlink(path)


# ── All Usage ─────────────────────────────────────────────

class TestAllUsage:
    def test_returns_all_providers(self):
        path = _tmp_store()
        with patch("src.rate_monitor._store_path", return_value=path):
            all_usage = get_all_usage()
            assert "openrouter" in all_usage
            assert "elevenlabs" in all_usage
            assert "openai" in all_usage
        os.unlink(path)


# ── Rate Alerts ───────────────────────────────────────────

class TestRateAlerts:
    def test_no_alerts_initially(self):
        path = _tmp_store()
        with patch("src.rate_monitor._store_path", return_value=path):
            alerts = get_rate_alerts()
            assert alerts == []
        os.unlink(path)

    def test_alert_on_high_usage(self):
        path = _tmp_store()
        with patch("src.rate_monitor._store_path", return_value=path):
            # CoinGecko has rpm=10, warn at 80% = 8 calls/min
            for i in range(9):
                alert = record_api_call("coingecko")
            # Should trigger alert
            assert alert is not None
            assert alert.provider == "coingecko"
            assert alert.window == "minute"
        os.unlink(path)

    def test_alert_stored(self):
        path = _tmp_store()
        with patch("src.rate_monitor._store_path", return_value=path):
            for i in range(9):
                record_api_call("coingecko")
            alerts = get_rate_alerts(hours=1)
            assert len(alerts) >= 1
        os.unlink(path)


# ── Usage Summary ─────────────────────────────────────────

class TestUsageSummary:
    def test_empty_summary(self):
        path = _tmp_store()
        with patch("src.rate_monitor._store_path", return_value=path):
            summary = get_usage_summary()
            assert "API USAGE" in summary
            assert "Нет API-вызовов" in summary
        os.unlink(path)

    def test_summary_with_calls(self):
        path = _tmp_store()
        with patch("src.rate_monitor._store_path", return_value=path):
            record_api_call("openrouter", latency_ms=100)
            record_api_call("openrouter", latency_ms=200)
            summary = get_usage_summary()
            assert "OpenRouter" in summary
            assert "2 запросов" in summary
        os.unlink(path)

    def test_summary_shows_errors(self):
        path = _tmp_store()
        with patch("src.rate_monitor._store_path", return_value=path):
            record_api_call("openrouter", success=True)
            record_api_call("openrouter", success=False)
            summary = get_usage_summary()
            assert "ошибок" in summary
        os.unlink(path)


# ── Count Calls ───────────────────────────────────────────

class TestCountCalls:
    def test_count_calls_empty(self):
        store = RateMonitorStore()
        count = _count_calls(store, "openrouter", datetime.now() - timedelta(hours=1))
        assert count == 0

    def test_count_calls_filters_provider(self):
        store = RateMonitorStore(calls=[
            ApiCall(provider="openrouter"),
            ApiCall(provider="elevenlabs"),
            ApiCall(provider="openrouter"),
        ])
        count = _count_calls(store, "openrouter", datetime.now() - timedelta(hours=1))
        assert count == 2


# ── Persistence ───────────────────────────────────────────

class TestPersistence:
    def test_load_missing_file(self):
        with patch("src.rate_monitor._store_path", return_value="/tmp/nonexistent_rate_12345.json"):
            store = _load_store()
            assert isinstance(store, RateMonitorStore)
            assert store.calls == []

    def test_load_corrupted_file(self):
        path = _tmp_store()
        with open(path, "w") as f:
            f.write("not json!!!")
        with patch("src.rate_monitor._store_path", return_value=path):
            store = _load_store()
            assert isinstance(store, RateMonitorStore)
        os.unlink(path)

    def test_roundtrip(self):
        path = _tmp_store()
        with patch("src.rate_monitor._store_path", return_value=path):
            record_api_call("openrouter", agent="smm", latency_ms=150)
            record_api_call("elevenlabs", success=False, status_code=429)
            store = _load_store()
            assert len(store.calls) == 2
            assert store.calls[0].provider == "openrouter"
            assert store.calls[1].status_code == 429
        os.unlink(path)
