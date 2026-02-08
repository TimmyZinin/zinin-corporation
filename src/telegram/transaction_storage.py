"""Storage for Tinkoff bank transactions parsed from CSV statements.

Uses persistent_storage (PostgreSQL on Railway, local files in dev).
Data survives container restarts.
"""

import logging
from datetime import datetime
from typing import Optional

from . import persistent_storage as store

logger = logging.getLogger(__name__)

STORAGE_KEY = "tinkoff_transactions"


def save_statement(parsed: dict) -> int:
    """Save parsed CSV statement. Merges with existing data, deduplicates.

    Returns number of new transactions added.
    """
    try:
        existing = store.load(STORAGE_KEY, {"transactions": [], "cards": [], "period": {}})
        if not isinstance(existing, dict):
            existing = {"transactions": [], "cards": [], "period": {}}

        # Build dedup key set from existing transactions
        existing_keys = set()
        for tx in existing.get("transactions", []):
            existing_keys.add(_tx_key(tx))

        # Add only new transactions
        new_count = 0
        for tx in parsed.get("transactions", []):
            key = _tx_key(tx)
            if key not in existing_keys:
                existing.setdefault("transactions", []).append(tx)
                existing_keys.add(key)
                new_count += 1

        # Sort all transactions by date (newest first)
        existing["transactions"] = sorted(
            existing.get("transactions", []),
            key=lambda x: x.get("date", ""),
            reverse=True,
        )

        # Update metadata
        existing["last_updated"] = datetime.now().isoformat()
        existing["total_count"] = len(existing["transactions"])

        # Update cards list
        cards = sorted(set(
            tx["card"] for tx in existing["transactions"] if tx.get("card")
        ))
        existing["cards"] = cards

        # Update period
        dates = [tx["date"] for tx in existing["transactions"] if tx.get("date")]
        if dates:
            existing["period"] = {"start": min(dates), "end": max(dates)}

        store.save(STORAGE_KEY, existing)
        logger.info(f"Saved {new_count} new transactions (total: {existing['total_count']})")
        return new_count

    except Exception as e:
        logger.error(f"Failed to save statement: {e}")
        return 0


def load_transactions(
    limit: int = 50,
    card: Optional[str] = None,
    category: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> list[dict]:
    """Load transactions with optional filters."""
    try:
        data = store.load(STORAGE_KEY, {"transactions": []})
        if not isinstance(data, dict):
            data = {"transactions": []}
        txs = data.get("transactions", [])

        if card:
            txs = [t for t in txs if card in t.get("card", "")]
        if category:
            cat_lower = category.lower()
            txs = [t for t in txs if cat_lower in t.get("category", "").lower()]
        if date_from:
            txs = [t for t in txs if t.get("date", "") >= date_from]
        if date_to:
            txs = [t for t in txs if t.get("date", "") <= date_to]

        return txs[:limit]
    except Exception as e:
        logger.error(f"Failed to load transactions: {e}")
        return []


def get_summary() -> Optional[dict]:
    """Get overall summary of stored transactions."""
    try:
        data = store.load(STORAGE_KEY, {"transactions": []})
        if not isinstance(data, dict):
            return None
        if not data.get("transactions"):
            return None

        txs = data["transactions"]
        income = sum(t["amount"] for t in txs if t.get("op_type") == "credit")
        expenses = sum(abs(t["amount"]) for t in txs if t.get("op_type") in ("debit", "transfer"))
        internal = sum(abs(t["amount"]) for t in txs if t.get("op_type") == "internal_transfer")

        # Category breakdown
        categories: dict[str, float] = {}
        for t in txs:
            if t.get("op_type") in ("debit", "transfer"):
                cat = t.get("category", "Другое") or "Другое"
                categories[cat] = categories.get(cat, 0) + abs(t["amount"])

        top_categories = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:15]

        # Monthly breakdown
        monthly: dict[str, dict] = {}
        for t in txs:
            month = t.get("date", "")[:7]  # YYYY-MM
            if not month:
                continue
            monthly.setdefault(month, {"income": 0, "expenses": 0})
            if t.get("op_type") == "credit":
                monthly[month]["income"] += t["amount"]
            elif t.get("op_type") in ("debit", "transfer"):
                monthly[month]["expenses"] += abs(t["amount"])

        return {
            "total_count": len(txs),
            "period": data.get("period", {}),
            "cards": data.get("cards", []),
            "income": round(income, 2),
            "expenses": round(expenses, 2),
            "internal_transfers": round(internal, 2),
            "net": round(income - expenses, 2),
            "top_categories": top_categories,
            "monthly": dict(sorted(monthly.items())),
            "last_updated": data.get("last_updated", ""),
        }
    except Exception as e:
        logger.error(f"Failed to get summary: {e}")
        return None


def _tx_key(tx: dict) -> str:
    """Generate a deduplication key for a transaction."""
    return f"{tx.get('date', '')}|{tx.get('amount', '')}|{tx.get('description', '')}|{tx.get('card', '')}"
