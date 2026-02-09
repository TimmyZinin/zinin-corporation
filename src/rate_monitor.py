"""
📡 Zinin Corp — Rate Limit Monitor

Tracks API call counts per provider and time window.
Alerts when usage approaches configured limits.
Persisted to disk as JSON for cross-restart continuity.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Configuration — provider limits
# ──────────────────────────────────────────────────────────

PROVIDER_LIMITS = {
    "openrouter": {
        "name": "OpenRouter",
        "requests_per_minute": 60,
        "requests_per_day": 5000,
        "warn_pct": 80,  # Alert at 80% of limit
    },
    "elevenlabs": {
        "name": "ElevenLabs",
        "requests_per_minute": 20,
        "requests_per_day": 1000,
        "warn_pct": 80,
    },
    "openai": {
        "name": "OpenAI",
        "requests_per_minute": 60,
        "requests_per_day": 10000,
        "warn_pct": 80,
    },
    "coingecko": {
        "name": "CoinGecko",
        "requests_per_minute": 10,
        "requests_per_day": 500,
        "warn_pct": 80,
    },
    "groq": {
        "name": "Groq",
        "requests_per_minute": 30,
        "requests_per_day": 14400,
        "warn_pct": 80,
    },
}


# ──────────────────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────────────────

class ApiCall(BaseModel):
    """A single API call record."""
    provider: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    agent: str = ""
    success: bool = True
    status_code: int = 0
    latency_ms: int = 0


class RateLimitAlert(BaseModel):
    """An alert when approaching rate limits."""
    provider: str
    window: str  # "minute" or "day"
    current: int
    limit: int
    pct: float
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class RateMonitorStore(BaseModel):
    """Persistent store for API call tracking."""
    calls: list[ApiCall] = Field(default_factory=list)
    alerts: list[RateLimitAlert] = Field(default_factory=list)


# ──────────────────────────────────────────────────────────
# Persistence
# ──────────────────────────────────────────────────────────

MAX_CALLS = 10000  # Keep last 10K calls
MAX_ALERTS = 200


def _store_path() -> str:
    for p in ["/app/data/rate_monitor.json", "data/rate_monitor.json"]:
        parent = os.path.dirname(p)
        if os.path.isdir(parent):
            return p
    os.makedirs("data", exist_ok=True)
    return "data/rate_monitor.json"


def _load_store() -> RateMonitorStore:
    path = _store_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return RateMonitorStore.model_validate(data)
        except Exception as e:
            logger.warning(f"Failed to load rate monitor store: {e}")
    return RateMonitorStore()


def _save_store(store: RateMonitorStore):
    path = _store_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(store.model_dump(), f, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"Failed to save rate monitor store: {e}")


# ──────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────

def record_api_call(
    provider: str,
    agent: str = "",
    success: bool = True,
    status_code: int = 200,
    latency_ms: int = 0,
) -> Optional[RateLimitAlert]:
    """Record an API call and check rate limits.

    Returns a RateLimitAlert if usage exceeds warning threshold, else None.
    """
    store = _load_store()

    call = ApiCall(
        provider=provider,
        agent=agent,
        success=success,
        status_code=status_code,
        latency_ms=latency_ms,
    )
    store.calls.append(call)

    # Trim old calls
    if len(store.calls) > MAX_CALLS:
        store.calls = store.calls[-MAX_CALLS:]

    # Check rate limits
    alert = _check_limits(store, provider)
    if alert:
        store.alerts.append(alert)
        if len(store.alerts) > MAX_ALERTS:
            store.alerts = store.alerts[-MAX_ALERTS:]

    _save_store(store)
    return alert


def get_provider_usage(provider: str, minutes: int = 60) -> dict:
    """Get usage stats for a provider over the given time window."""
    store = _load_store()
    cutoff = datetime.now() - timedelta(minutes=minutes)

    calls = []
    for c in store.calls:
        if c.provider != provider:
            continue
        try:
            ts = datetime.fromisoformat(c.timestamp)
            if ts >= cutoff:
                calls.append(c)
        except (ValueError, TypeError):
            continue

    total = len(calls)
    success = sum(1 for c in calls if c.success)
    failed = total - success
    avg_latency = 0
    if calls:
        latencies = [c.latency_ms for c in calls if c.latency_ms > 0]
        avg_latency = sum(latencies) // len(latencies) if latencies else 0

    limits = PROVIDER_LIMITS.get(provider, {})

    return {
        "provider": provider,
        "window_minutes": minutes,
        "total_calls": total,
        "success": success,
        "failed": failed,
        "avg_latency_ms": avg_latency,
        "rpm_limit": limits.get("requests_per_minute", 0),
        "daily_limit": limits.get("requests_per_day", 0),
    }


def get_all_usage(minutes: int = 60) -> dict:
    """Get usage stats for all known providers."""
    result = {}
    for provider in PROVIDER_LIMITS:
        result[provider] = get_provider_usage(provider, minutes)
    return result


def get_rate_alerts(hours: int = 24) -> list[RateLimitAlert]:
    """Get recent rate limit alerts."""
    store = _load_store()
    cutoff = datetime.now() - timedelta(hours=hours)

    alerts = []
    for a in store.alerts:
        try:
            ts = datetime.fromisoformat(a.timestamp)
            if ts >= cutoff:
                alerts.append(a)
        except (ValueError, TypeError):
            continue
    return alerts


def get_usage_summary() -> str:
    """Get a text summary of API usage for CEO dashboard."""
    all_usage = get_all_usage(minutes=60)
    recent_alerts = get_rate_alerts(hours=24)

    lines = ["═══ API USAGE (1h) ═══"]
    for provider, usage in all_usage.items():
        name = PROVIDER_LIMITS[provider]["name"]
        total = usage["total_calls"]
        if total == 0:
            continue
        failed = usage["failed"]
        avg_lat = usage["avg_latency_ms"]
        fail_str = f" | ❌ {failed} ошибок" if failed else ""
        lines.append(f"  {name}: {total} запросов{fail_str} | ~{avg_lat}ms")

    if not any(all_usage[p]["total_calls"] for p in all_usage):
        lines.append("  Нет API-вызовов за последний час")

    if recent_alerts:
        lines.append(f"\n⚠️ Алерты ({len(recent_alerts)}):")
        for a in recent_alerts[-5:]:
            name = PROVIDER_LIMITS.get(a.provider, {}).get("name", a.provider)
            lines.append(f"  🟡 {name}: {a.pct:.0f}% от лимита ({a.window})")

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────

def _check_limits(store: RateMonitorStore, provider: str) -> Optional[RateLimitAlert]:
    """Check if provider usage exceeds warning thresholds."""
    limits = PROVIDER_LIMITS.get(provider)
    if not limits:
        return None

    now = datetime.now()
    warn_pct = limits.get("warn_pct", 80) / 100.0

    # Check per-minute
    minute_ago = now - timedelta(minutes=1)
    minute_calls = _count_calls(store, provider, minute_ago)
    rpm_limit = limits.get("requests_per_minute", 0)
    if rpm_limit and minute_calls >= rpm_limit * warn_pct:
        pct = (minute_calls / rpm_limit) * 100
        return RateLimitAlert(
            provider=provider,
            window="minute",
            current=minute_calls,
            limit=rpm_limit,
            pct=pct,
        )

    # Check per-day
    day_ago = now - timedelta(hours=24)
    day_calls = _count_calls(store, provider, day_ago)
    daily_limit = limits.get("requests_per_day", 0)
    if daily_limit and day_calls >= daily_limit * warn_pct:
        pct = (day_calls / daily_limit) * 100
        return RateLimitAlert(
            provider=provider,
            window="day",
            current=day_calls,
            limit=daily_limit,
            pct=pct,
        )

    return None


def _count_calls(store: RateMonitorStore, provider: str, since: datetime) -> int:
    """Count calls for a provider since a given time."""
    count = 0
    for c in store.calls:
        if c.provider != provider:
            continue
        try:
            ts = datetime.fromisoformat(c.timestamp)
            if ts >= since:
                count += 1
        except (ValueError, TypeError):
            continue
    return count
