"""
💰 Zinin Corp — Revenue Tracker

Thread-safe JSON persistence for MRR per channel, gap tracking, daily snapshots.
Used by Proactive Planner to generate morning touchpoint actions.
"""

import json
import logging
import os
import threading
from datetime import datetime, date

logger = logging.getLogger(__name__)

_lock = threading.Lock()

# Revenue target
TARGET_MRR = 2500.0
DEADLINE = "2026-03-02"

# Default channels
DEFAULT_CHANNELS = {
    "krmktl": {"name": "Крипто Маркетологи", "mrr": 350.0, "members": 215, "target": 1000.0},
    "sborka": {"name": "СБОРКА", "mrr": 0.0, "members": 0, "target": 800.0},
    "botanica": {"name": "Ботаника", "mrr": 165.0, "members": 3, "target": 600.0},
    "personal": {"name": "Personal Brand", "mrr": 0.0, "members": 0, "target": 500.0},
    "sponsors": {"name": "Sponsors", "mrr": 0.0, "members": 0, "target": 400.0},
}


_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_REVENUE_PATH = os.path.join(_DATA_DIR, "revenue.json")


def _revenue_path() -> str:
    """Get path for revenue JSON file. Uses _REVENUE_PATH module variable (patchable in tests)."""
    return _REVENUE_PATH


def _load_revenue() -> dict:
    path = _revenue_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as e:
            logger.warning(f"Failed to load revenue data: {e}")
    return _default_data()


def _default_data() -> dict:
    return {
        "target_mrr": TARGET_MRR,
        "deadline": DEADLINE,
        "channels": {k: dict(v) for k, v in DEFAULT_CHANNELS.items()},
        "history": [],
        "updated_at": datetime.now().isoformat(),
    }


def _save_revenue(data: dict) -> bool:
    path = _revenue_path()
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        return True
    except Exception as e:
        logger.warning(f"Failed to save revenue data: {e}")
        return False


def get_revenue_summary() -> dict:
    """Get current revenue state: channels, total, target, gap, days_left."""
    with _lock:
        data = _load_revenue()
    channels = data.get("channels", {})
    total_mrr = sum(ch.get("mrr", 0) for ch in channels.values())
    target = data.get("target_mrr", TARGET_MRR)
    gap = max(0, target - total_mrr)
    days_left = get_days_left()
    return {
        "channels": channels,
        "total_mrr": total_mrr,
        "target_mrr": target,
        "gap": gap,
        "days_left": days_left,
        "deadline": data.get("deadline", DEADLINE),
        "updated_at": data.get("updated_at", ""),
    }


def get_gap() -> float:
    """Get current MRR gap to target."""
    summary = get_revenue_summary()
    return summary["gap"]


def get_days_left() -> int:
    """Get days remaining until deadline."""
    try:
        deadline = datetime.strptime(DEADLINE, "%Y-%m-%d").date()
        today = date.today()
        delta = (deadline - today).days
        return max(0, delta)
    except Exception:
        return 0


def get_total_mrr() -> float:
    """Get total current MRR across all channels."""
    summary = get_revenue_summary()
    return summary["total_mrr"]


def update_channel(channel: str, *, mrr: float = None, members: int = None, target: float = None) -> dict:
    """Update a specific channel's MRR and/or members."""
    with _lock:
        data = _load_revenue()
        channels = data.get("channels", {})
        if channel not in channels:
            channels[channel] = {"name": channel, "mrr": 0.0, "members": 0, "target": 0.0}
        if mrr is not None:
            channels[channel]["mrr"] = mrr
        if members is not None:
            channels[channel]["members"] = members
        if target is not None:
            channels[channel]["target"] = target
        data["channels"] = channels
        data["updated_at"] = datetime.now().isoformat()
        _save_revenue(data)
    return channels[channel]


def add_daily_snapshot() -> dict:
    """Add a daily MRR snapshot to history. Returns the snapshot."""
    with _lock:
        data = _load_revenue()
        channels = data.get("channels", {})
        total_mrr = sum(ch.get("mrr", 0) for ch in channels.values())
        snapshot = {
            "date": date.today().isoformat(),
            "total_mrr": total_mrr,
            "channels": {k: v.get("mrr", 0) for k, v in channels.items()},
            "gap": max(0, data.get("target_mrr", TARGET_MRR) - total_mrr),
        }
        history = data.get("history", [])
        # Avoid duplicate snapshots for the same day
        today_str = date.today().isoformat()
        history = [h for h in history if h.get("date") != today_str]
        history.append(snapshot)
        data["history"] = history
        data["updated_at"] = datetime.now().isoformat()
        _save_revenue(data)
    return snapshot


def get_history(days: int = 7) -> list[dict]:
    """Get last N days of MRR snapshots."""
    with _lock:
        data = _load_revenue()
    return data.get("history", [])[-days:]


def format_revenue_summary() -> str:
    """Format revenue summary for Telegram with emoji progress bar."""
    summary = get_revenue_summary()
    total = summary["total_mrr"]
    target = summary["target_mrr"]
    gap = summary["gap"]
    days = summary["days_left"]

    # Progress bar
    pct = min(100, int(total / target * 100)) if target > 0 else 0
    filled = pct // 10
    bar = "█" * filled + "░" * (10 - filled)

    lines = [
        f"💰 Revenue Tracker",
        f"",
        f"MRR: ${total:,.0f} / ${target:,.0f}",
        f"[{bar}] {pct}%",
        f"Gap: ${gap:,.0f} | {days} дней",
        f"",
    ]

    for key, ch in summary["channels"].items():
        name = ch.get("name", key)
        mrr = ch.get("mrr", 0)
        ch_target = ch.get("target", 0)
        members = ch.get("members", 0)
        ch_pct = int(mrr / ch_target * 100) if ch_target > 0 else 0
        icon = "✅" if ch_pct >= 80 else "🟡" if ch_pct >= 30 else "🔴"
        lines.append(f"{icon} {name}: ${mrr:,.0f}/${ch_target:,.0f} ({ch_pct}%) — {members} чел.")

    return "\n".join(lines)


def recalculate_channel_from_events(channel: str) -> dict:
    """
    Recalculate a channel's MRR from stored Tribute webhook events.

    Loads tribute_payments from persistent_storage, filters by _channel tag,
    counts active subscribers, estimates MRR.

    Returns: {"mrr": float, "members": int, "events_counted": int}
    """
    try:
        from src.tools.financial.tribute import _load_payments
    except ImportError:
        logger.warning("tribute module not available")
        return {"mrr": 0.0, "members": 0, "events_counted": 0}

    payments = _load_payments()
    if not payments:
        return {"mrr": 0.0, "members": 0, "events_counted": 0}

    # Filter by channel
    channel_events = [
        p for p in payments
        if p.get("_channel") == channel
        and p.get("event") in ("newSubscription", "renewedSubscription", "cancelledSubscription")
    ]

    if not channel_events:
        return {"mrr": 0.0, "members": 0, "events_counted": 0}

    # Build active subscriber set (ordered by timestamp)
    active_subs: dict[str, float] = {}  # user_id -> last known price
    for event in sorted(channel_events, key=lambda x: x.get("received_at", x.get("timestamp", ""))):
        user_id = str(
            event.get("telegram_user_id",
            event.get("user_id",
            event.get("subscriber_id", "unknown")))
        )
        event_type = event.get("event", "")

        if event_type in ("newSubscription", "renewedSubscription"):
            # Extract subscription price
            raw_amount = event.get("amount", event.get("price", 0))
            currency = event.get("currency", "USD").upper()
            # Tribute may return minor units (kopecks/cents)
            amount = float(raw_amount)
            if amount > 1000 and currency in ("RUB", "KZT"):
                # Likely already in major units for RUB
                pass
            elif amount > 100:
                amount = amount / 100  # Convert cents to dollars

            # Convert RUB to USD (~$1 = 90 RUB)
            if currency == "RUB":
                amount = amount / 90.0

            active_subs[user_id] = amount
        elif event_type == "cancelledSubscription":
            active_subs.pop(user_id, None)

    members = len(active_subs)
    mrr = sum(active_subs.values())

    # Update revenue tracker
    update_channel(channel, mrr=round(mrr, 2), members=members)

    logger.info(
        "Recalculated %s: MRR=$%.2f, members=%d from %d events",
        channel, mrr, members, len(channel_events),
    )

    return {"mrr": round(mrr, 2), "members": members, "events_counted": len(channel_events)}


def seed_revenue_data() -> bool:
    """Seed initial revenue data if file doesn't exist."""
    path = _revenue_path()
    if os.path.exists(path):
        return False
    with _lock:
        data = _default_data()
        return _save_revenue(data)
