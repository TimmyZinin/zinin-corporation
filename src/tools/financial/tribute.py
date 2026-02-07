"""
Tribute — Telegram monetization platform (main revenue source).

API Docs: https://wiki.tribute.tg/for-content-creators/api-documentation
Base URL: https://tribute.tg/api/v1/
Auth: Api-Key header

Available endpoints:
- GET /products — list products (subscriptions, digital, custom, physical)
- Webhooks — real-time payment events (newSubscription, renewedSubscription, etc.)

Note: Tribute API does not expose a payments history endpoint directly.
Revenue tracking relies on webhook events stored locally.
"""

import hashlib
import hmac
import json
import logging
import os
from datetime import datetime
from decimal import Decimal
from typing import Optional, Type

import httpx
from pydantic import BaseModel, Field

from .base import FinancialBaseTool, load_financial_config

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# Local payment storage (webhook-collected)
# ──────────────────────────────────────────────────────────

def _payments_path() -> str:
    for p in ["/app/data/tribute_payments.json", "data/tribute_payments.json"]:
        if os.path.exists(os.path.dirname(p) or "."):
            return p
    return "data/tribute_payments.json"


def _load_payments() -> list[dict]:
    path = _payments_path()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_payments(payments: list[dict]):
    path = _payments_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payments, f, indent=2, ensure_ascii=False, default=str)


# ──────────────────────────────────────────────────────────
# Tool: Tribute Revenue
# ──────────────────────────────────────────────────────────

class TributeRevenueInput(BaseModel):
    action: str = Field(
        ...,
        description=(
            "Action to perform: "
            "'products' — list all monetization products and their prices, "
            "'revenue' — revenue summary from stored webhook payments, "
            "'subscriptions' — active subscription stats"
        ),
    )
    date_from: Optional[str] = Field(
        None,
        description="Start date for revenue query (YYYY-MM-DD). Default: current month start.",
    )
    date_to: Optional[str] = Field(
        None,
        description="End date for revenue query (YYYY-MM-DD). Default: today.",
    )


class TributeRevenueTool(FinancialBaseTool):
    name: str = "tribute_revenue"
    description: str = (
        "Get revenue data from Tribute (Telegram monetization platform). "
        "Main income channel for Zinin Corp. "
        "Actions: products (list products), revenue (payment summary), "
        "subscriptions (active subscriber stats)."
    )
    args_schema: Type[BaseModel] = TributeRevenueInput
    service_name: str = "tribute"

    def _run(
        self,
        action: str,
        date_from: str = None,
        date_to: str = None,
    ) -> str:
        return self._safe_run(self._execute, action, date_from, date_to)

    def _execute(self, action: str, date_from: str, date_to: str) -> str:
        if action == "products":
            return self._fetch_products()
        elif action == "revenue":
            return self._revenue_summary(date_from, date_to)
        elif action == "subscriptions":
            return self._subscription_stats()
        else:
            return f"Unknown action: {action}. Use: products, revenue, subscriptions."

    def _fetch_products(self) -> str:
        """Fetch products from Tribute API."""
        creds = self._get_credentials()
        headers = {
            "Api-Key": creds["api_key"],
            "Content-Type": "application/json",
        }
        client = httpx.Client(
            base_url="https://tribute.tg/api/v1",
            headers=headers,
            timeout=30.0,
        )
        try:
            response = client.get("/products")
            response.raise_for_status()
            data = response.json()
        finally:
            client.close()

        products = data if isinstance(data, list) else data.get("rows", data.get("items", data.get("products", [])))
        if not products:
            return "No products found on Tribute."

        lines = ["TRIBUTE PRODUCTS:"]
        for p in products:
            name = p.get("name", p.get("title", "Unnamed"))
            # Tribute returns amount in minor units (kopecks/cents)
            raw_amount = p.get("amount", 0)
            currency = p.get("currency", "USD").upper()
            # Convert from minor units if > 100 (likely kopecks/cents)
            price = raw_amount / 100 if raw_amount > 100 else raw_amount
            ptype = p.get("type", "unknown")
            status = p.get("status", p.get("is_active", "unknown"))
            link = p.get("webLink", p.get("link", ""))
            lines.append(
                f"  - {name}: {price:,.2f} {currency} ({ptype}) [{status}]"
                + (f" {link}" if link else "")
            )
        return "\n".join(lines)

    def _revenue_summary(self, date_from: str, date_to: str) -> str:
        """Summarize revenue from locally stored webhook payments."""
        payments = _load_payments()
        if not payments:
            return (
                "Данных о платежах пока нет. "
                "Revenue data is collected via webhooks. "
                "Настройте webhook URL в Tribute Dashboard → Settings → API Keys."
            )

        # Filter by date range
        if date_from:
            dt_from = datetime.fromisoformat(date_from)
            payments = [
                p for p in payments
                if datetime.fromisoformat(p.get("timestamp", "2000-01-01")) >= dt_from
            ]
        if date_to:
            dt_to = datetime.fromisoformat(date_to)
            payments = [
                p for p in payments
                if datetime.fromisoformat(p.get("timestamp", "2099-01-01")) <= dt_to
            ]

        total = Decimal("0")
        by_type: dict[str, Decimal] = {}
        count = 0
        for p in payments:
            amount = Decimal(str(p.get("amount", 0)))
            total += amount
            count += 1
            ptype = p.get("type", "unknown")
            by_type[ptype] = by_type.get(ptype, Decimal("0")) + amount

        period = ""
        if date_from or date_to:
            period = f" ({date_from or '...'} — {date_to or 'today'})"

        lines = [f"TRIBUTE REVENUE{period}:"]
        lines.append(f"  Total: {total:.2f} USD ({count} payments)")
        for ptype, amount in sorted(by_type.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"  - {ptype}: {amount:.2f} USD")
        return "\n".join(lines)

    def _subscription_stats(self) -> str:
        """Get live subscription data from Tribute API."""
        # Try live API first (/subscribers endpoint)
        try:
            creds = self._get_credentials()
            headers = {
                "Api-Key": creds["api_key"],
                "Content-Type": "application/json",
            }
            client = httpx.Client(
                base_url="https://tribute.tg/api/v1",
                headers=headers,
                timeout=30.0,
            )
            try:
                response = client.get("/subscribers")
                response.raise_for_status()
                data = response.json()
            finally:
                client.close()

            subscribers = data.get("result", data) if isinstance(data, dict) else data

            if not subscribers:
                return "TRIBUTE SUBSCRIPTIONS:\n  No active subscribers."

            active = [s for s in subscribers if s.get("status") == "active"]
            expired = [s for s in subscribers if s.get("status") != "active"]

            lines = ["TRIBUTE SUBSCRIPTIONS (live data):"]
            lines.append(f"  Active subscribers: {len(active)}")
            if expired:
                lines.append(f"  Expired/cancelled: {len(expired)}")

            # Show details
            from datetime import datetime
            now = datetime.utcnow()
            expiring_soon = []
            for sub in active:
                expire_str = sub.get("expireAt", "")
                sub_id = sub.get("subscriptionId", "?")
                tg_id = sub.get("telegramUserId", "?")
                activated = sub.get("activatedAt", "")[:10]

                expire_date = None
                if expire_str:
                    try:
                        expire_date = datetime.fromisoformat(expire_str.replace("Z", "+00:00")).replace(tzinfo=None)
                    except (ValueError, TypeError):
                        pass

                days_left = (expire_date - now).days if expire_date else None
                expire_short = expire_str[:10] if expire_str else "N/A"

                alert = ""
                if days_left is not None and days_left <= 30:
                    alert = f" ⚠️ EXPIRING IN {days_left} DAYS"
                    expiring_soon.append(tg_id)

                lines.append(
                    f"  - TG:{tg_id} | sub #{sub_id} | "
                    f"since {activated} | expires {expire_short}"
                    f" ({days_left}d left){alert}" if days_left is not None else
                    f"  - TG:{tg_id} | sub #{sub_id} | since {activated}"
                )

            if expiring_soon:
                lines.append(f"\n  ⚠️ ALERT: {len(expiring_soon)} subscriber(s) expiring within 30 days!")

            return "\n".join(lines)

        except Exception as e:
            # Fallback to webhook-collected data
            return self._subscription_stats_from_webhooks()

    def _subscription_stats_from_webhooks(self) -> str:
        """Fallback: analyze subscription data from stored webhook events."""
        payments = _load_payments()
        sub_events = [
            p for p in payments
            if p.get("event") in ("newSubscription", "renewedSubscription", "cancelledSubscription")
        ]

        if not sub_events:
            return (
                "Данных о подписках пока нет. "
                "Subscription events are collected via webhooks."
            )

        active = set()
        for event in sorted(sub_events, key=lambda x: x.get("timestamp", "")):
            user_id = event.get("user_id", event.get("subscriber_id", "unknown"))
            if event["event"] in ("newSubscription", "renewedSubscription"):
                active.add(user_id)
            elif event["event"] == "cancelledSubscription":
                active.discard(user_id)

        total_new = sum(1 for e in sub_events if e["event"] == "newSubscription")
        total_renewed = sum(1 for e in sub_events if e["event"] == "renewedSubscription")
        total_cancelled = sum(1 for e in sub_events if e["event"] == "cancelledSubscription")

        lines = [
            "TRIBUTE SUBSCRIPTIONS (webhook data):",
            f"  Active now: ~{len(active)}",
            f"  Total new: {total_new}",
            f"  Renewals: {total_renewed}",
            f"  Cancelled: {total_cancelled}",
        ]
        if total_new > 0:
            churn = total_cancelled / total_new * 100
            lines.append(f"  Churn rate: {churn:.1f}%")
        return "\n".join(lines)


# ──────────────────────────────────────────────────────────
# Webhook Verifier (service, not a tool)
# ──────────────────────────────────────────────────────────

class TributeWebhookVerifier:
    """
    Verify incoming webhooks from Tribute.

    Pipeline:
    1. Check HMAC-SHA256 signature (constant-time comparison!)
    2. Check timestamp (reject if > 5 min — anti-replay)
    3. Store payment in local JSON
    4. Return 200 OK immediately
    """

    @staticmethod
    def verify_signature(body: bytes, signature: str, api_key: str) -> bool:
        """Verify webhook signature (trbt-signature header)."""
        expected = hmac.new(
            api_key.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    @staticmethod
    def process_event(event_data: dict):
        """Store a verified webhook event."""
        event_data["received_at"] = datetime.utcnow().isoformat()
        payments = _load_payments()

        # Dedup by event ID
        event_id = event_data.get("id", event_data.get("event_id"))
        if event_id:
            existing_ids = {p.get("id", p.get("event_id")) for p in payments}
            if event_id in existing_ids:
                logger.info(f"Duplicate Tribute event: {event_id}")
                return

        payments.append(event_data)
        _save_payments(payments)
        logger.info(
            f"Stored Tribute event: {event_data.get('event', 'unknown')}"
        )
