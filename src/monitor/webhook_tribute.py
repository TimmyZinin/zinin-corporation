"""
Tribute Webhook Endpoint — POST /webhooks/tribute

Receives subscription events from Tribute (tribute.tg), verifies HMAC signature,
stores events idempotently, auto-updates revenue tracker, notifies CEO/CFO bots.

Multi-project support via ?project= query param:
  - krmktl  → Крипто Маркетологи
  - sborka  → СБОРКА
  - botanica → Ботаника

Env vars (per-project keys, fallback to TRIBUTE_API_KEY):
  TRIBUTE_API_KEY_KRMKTL, TRIBUTE_API_KEY_SBORKA, TRIBUTE_API_KEY_BOTANICA
"""

import json
import logging
import os
from typing import Optional

from starlette.requests import Request
from starlette.responses import JSONResponse

from ..tools.financial.tribute import TributeWebhookVerifier
from .webhook_notifier import notify_ceo, notify_cfo

logger = logging.getLogger(__name__)

# ── Project Configuration ─────────────────────────────────

TRIBUTE_PROJECTS = {
    "krmktl": {
        "env_key": "TRIBUTE_API_KEY_KRMKTL",
        "revenue_channel": "krmktl",
        "display_name": "Крипто Маркетологи",
    },
    "sborka": {
        "env_key": "TRIBUTE_API_KEY_SBORKA",
        "revenue_channel": "sborka",
        "display_name": "СБОРКА",
    },
    "botanica": {
        "env_key": "TRIBUTE_API_KEY_BOTANICA",
        "revenue_channel": "botanica",
        "display_name": "Ботаника",
    },
}

# Events that affect subscription count / MRR
SUBSCRIPTION_EVENTS = {
    "newSubscription",
    "renewedSubscription",
    "cancelledSubscription",
}

# Events that trigger user notifications
NOTIFY_EVENTS = {
    "newSubscription": "🟢 Новая подписка",
    "cancelledSubscription": "🔴 Отмена подписки",
}


# ── Helpers ───────────────────────────────────────────────

def _get_api_key(project: Optional[str]) -> Optional[str]:
    """Get Tribute API key for a project. Falls back to TRIBUTE_API_KEY."""
    if project and project in TRIBUTE_PROJECTS:
        key = os.getenv(TRIBUTE_PROJECTS[project]["env_key"], "")
        if key:
            return key
    return os.getenv("TRIBUTE_API_KEY", "") or None


def _try_all_keys(body: bytes, signature: str) -> Optional[str]:
    """Try signature verification against all project keys. Returns matched project or None."""
    for project_key, config in TRIBUTE_PROJECTS.items():
        api_key = os.getenv(config["env_key"], "")
        if api_key and TributeWebhookVerifier.verify_signature(body, signature, api_key):
            return project_key
    # Fallback to default key
    default_key = os.getenv("TRIBUTE_API_KEY", "")
    if default_key and TributeWebhookVerifier.verify_signature(body, signature, default_key):
        return "__default__"
    return None


def _get_revenue_channel(project: Optional[str], event_data: dict) -> Optional[str]:
    """Determine revenue channel from project key or event payload."""
    if project and project in TRIBUTE_PROJECTS:
        return TRIBUTE_PROJECTS[project]["revenue_channel"]
    # Try to infer from event payload (channel_name field)
    channel_name = event_data.get("channel_name", "").lower()
    for key, config in TRIBUTE_PROJECTS.items():
        if key in channel_name or config["display_name"].lower() in channel_name:
            return config["revenue_channel"]
    return None


def _get_display_name(project: Optional[str]) -> str:
    """Get human-readable project name."""
    if project and project in TRIBUTE_PROJECTS:
        return TRIBUTE_PROJECTS[project]["display_name"]
    return project or "Unknown"


# ── Revenue Auto-Update ──────────────────────────────────

def _update_revenue_from_event(event_data: dict, channel: str):
    """Recalculate channel MRR after a subscription event."""
    try:
        from ..revenue_tracker import recalculate_channel_from_events
        result = recalculate_channel_from_events(channel)
        logger.info(
            "Revenue auto-updated for %s: MRR=$%.2f, members=%d",
            channel,
            result.get("mrr", 0),
            result.get("members", 0),
        )
    except ImportError:
        logger.warning("revenue_tracker not available, skipping auto-update")
    except Exception as e:
        logger.error("Revenue auto-update error for %s: %s", channel, e)


# ── Notification ─────────────────────────────────────────

async def _send_notifications(event_data: dict, project: Optional[str], channel: Optional[str]):
    """Send Telegram notifications for important events."""
    event_type = event_data.get("event", "")
    if event_type not in NOTIFY_EVENTS:
        return

    label = NOTIFY_EVENTS[event_type]
    display = _get_display_name(project)
    sub_name = event_data.get("subscription_name", "")
    amount = event_data.get("amount", 0)
    currency = event_data.get("currency", "USD")
    user_id = event_data.get("telegram_user_id", event_data.get("user_id", "?"))

    # Get current MRR for context
    mrr_line = ""
    try:
        from ..revenue_tracker import get_revenue_summary
        summary = get_revenue_summary()
        total_mrr = summary.get("total_mrr", 0)
        mrr_line = f"\nMRR: <code>${total_mrr:,.0f}</code>"
    except Exception:
        pass

    msg = (
        f"{label}\n"
        f"<b>{display}</b>"
        + (f" — {sub_name}" if sub_name else "")
        + f"\nUser: <code>{user_id}</code>"
        + (f"\nAmount: {amount} {currency}" if amount else "")
        + mrr_line
    )

    # Notify both CEO and CFO (fire-and-forget, don't block webhook response)
    try:
        await notify_ceo(msg)
    except Exception as e:
        logger.warning("CEO notification failed: %s", e)
    try:
        await notify_cfo(msg)
    except Exception as e:
        logger.warning("CFO notification failed: %s", e)


# ── Main Endpoint ────────────────────────────────────────

async def tribute_webhook(request: Request) -> JSONResponse:
    """
    POST /webhooks/tribute?project=krmktl

    Process:
    1. Read body + trbt-signature header
    2. Verify HMAC-SHA256 signature
    3. Parse JSON payload
    4. Store event (idempotent, dedup by event_id)
    5. Auto-update revenue tracker (for subscription events)
    6. Send Telegram notifications (for new/cancelled)
    7. Return 200 OK
    """
    # 1. Read body and signature
    try:
        body = await request.body()
    except Exception:
        return JSONResponse({"error": "failed to read body"}, status_code=400)

    signature = request.headers.get("trbt-signature", "")
    if not signature:
        return JSONResponse({"error": "missing trbt-signature header"}, status_code=400)

    # 2. Verify signature
    project = request.query_params.get("project", "")

    if project:
        api_key = _get_api_key(project)
        if not api_key:
            return JSONResponse({"error": f"no API key for project '{project}'"}, status_code=400)
        if not TributeWebhookVerifier.verify_signature(body, signature, api_key):
            return JSONResponse({"error": "invalid signature"}, status_code=401)
    else:
        # Try all project keys
        matched = _try_all_keys(body, signature)
        if not matched:
            return JSONResponse({"error": "invalid signature"}, status_code=401)
        if matched != "__default__":
            project = matched

    # 3. Parse JSON
    try:
        event_data = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return JSONResponse({"error": "invalid JSON body"}, status_code=422)

    if not isinstance(event_data, dict):
        return JSONResponse({"error": "expected JSON object"}, status_code=422)

    event_type = event_data.get("event", "unknown")
    event_id = event_data.get("id", event_data.get("event_id", ""))

    logger.info(
        "Tribute webhook: event=%s id=%s project=%s",
        event_type, event_id, project or "auto",
    )

    # 4. Tag with channel and store (idempotent)
    channel = _get_revenue_channel(project, event_data)
    if channel:
        event_data["_channel"] = channel

    TributeWebhookVerifier.process_event(event_data)

    # 5. Auto-update revenue (for subscription events)
    if event_type in SUBSCRIPTION_EVENTS and channel:
        _update_revenue_from_event(event_data, channel)

    # 6. Send notifications (async, non-blocking for response)
    await _send_notifications(event_data, project, channel)

    # 7. Return OK
    return JSONResponse({"ok": True, "event": event_type})
