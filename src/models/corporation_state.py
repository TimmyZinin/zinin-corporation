"""
🏢 Zinin Corp — Shared Corporation State

Persistent Pydantic model that aggregates data from all agents.
Saved to disk after each flow run. Readable by any agent or tool.
"""

import json
import logging
import os
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# Sub-models for each department
# ──────────────────────────────────────────────────────────

class FinancialSnapshot(BaseModel):
    """Last known financial state (from Маттиас)."""
    bank_balance_rub: float = 0
    crypto_portfolio_usd: float = 0
    total_revenue_rub: float = 0
    total_expenses_rub: float = 0
    api_costs_usd: float = 0
    mrr_rub: float = 0
    updated_at: str = ""


class TechSnapshot(BaseModel):
    """Last known tech health state (from Мартин)."""
    overall_status: str = "unknown"  # healthy, degraded, critical
    services_up: int = 0
    services_down: int = 0
    services_total: int = 0
    avg_latency_ms: int = 0
    errors_count: int = 0
    updated_at: str = ""


class ContentSnapshot(BaseModel):
    """Last known content metrics (from Юки)."""
    posts_generated: int = 0
    posts_published: int = 0
    linkedin_status: str = "unknown"
    avg_quality_score: float = 0
    updated_at: str = ""


class ProductSnapshot(BaseModel):
    """Last known product health (from Софи)."""
    features_total: int = 0
    features_done: int = 0
    features_in_progress: int = 0
    features_blocked: int = 0
    current_sprint: str = ""
    sprint_progress_pct: int = 0
    updated_at: str = ""


class DecisionRecord(BaseModel):
    """A decision made by CEO."""
    decision: str
    reason: str = ""
    agent: str = "manager"
    timestamp: str = ""


class AlertRecord(BaseModel):
    """An alert that requires attention."""
    severity: str = "info"  # info, warning, critical
    message: str
    source: str = ""
    timestamp: str = ""
    resolved: bool = False


# ──────────────────────────────────────────────────────────
# Main SharedCorporationState
# ──────────────────────────────────────────────────────────

class SharedCorporationState(BaseModel):
    """Persistent corporation-wide state.

    Updated by agents after each task. Persisted to JSON.
    Used by CEO dashboard, strategic reviews, and cross-agent context.
    """

    # Department snapshots
    financial: FinancialSnapshot = Field(default_factory=FinancialSnapshot)
    tech: TechSnapshot = Field(default_factory=TechSnapshot)
    content: ContentSnapshot = Field(default_factory=ContentSnapshot)
    product: ProductSnapshot = Field(default_factory=ProductSnapshot)

    # Corporation-level
    decisions: list[DecisionRecord] = Field(default_factory=list)
    alerts: list[AlertRecord] = Field(default_factory=list)
    last_strategic_review: str = ""
    last_full_report: str = ""

    # Metadata
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = ""
    version: int = 1


# ──────────────────────────────────────────────────────────
# Persistence: load / save / update
# ──────────────────────────────────────────────────────────

def _state_path() -> str:
    for p in ["/app/data/corporation_state.json", "data/corporation_state.json"]:
        parent = os.path.dirname(p)
        if os.path.isdir(parent):
            return p
    os.makedirs("data", exist_ok=True)
    return "data/corporation_state.json"


def load_shared_state() -> SharedCorporationState:
    """Load shared state from disk. Returns default state if file missing."""
    path = _state_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return SharedCorporationState.model_validate(data)
        except Exception as e:
            logger.warning(f"Failed to load shared state: {e}")
    return SharedCorporationState()


def save_shared_state(state: SharedCorporationState):
    """Persist shared state to disk."""
    state.updated_at = datetime.now().isoformat()
    path = _state_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state.model_dump(), f, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"Failed to save shared state: {e}")


def update_financial(snapshot: FinancialSnapshot):
    """Update financial snapshot in shared state."""
    state = load_shared_state()
    snapshot.updated_at = datetime.now().isoformat()
    state.financial = snapshot
    save_shared_state(state)


def update_tech(snapshot: TechSnapshot):
    """Update tech snapshot in shared state."""
    state = load_shared_state()
    snapshot.updated_at = datetime.now().isoformat()
    state.tech = snapshot
    save_shared_state(state)


def update_content(snapshot: ContentSnapshot):
    """Update content snapshot in shared state."""
    state = load_shared_state()
    snapshot.updated_at = datetime.now().isoformat()
    state.content = snapshot
    save_shared_state(state)


def update_product(snapshot: ProductSnapshot):
    """Update product snapshot in shared state."""
    state = load_shared_state()
    snapshot.updated_at = datetime.now().isoformat()
    state.product = snapshot
    save_shared_state(state)


def add_decision(decision: str, reason: str = "", agent: str = "manager"):
    """Record a CEO decision."""
    state = load_shared_state()
    record = DecisionRecord(
        decision=decision,
        reason=reason,
        agent=agent,
        timestamp=datetime.now().isoformat(),
    )
    state.decisions.append(record)
    state.decisions = state.decisions[-50:]  # Keep last 50
    save_shared_state(state)


def add_alert(message: str, severity: str = "info", source: str = ""):
    """Add an alert to shared state."""
    state = load_shared_state()
    record = AlertRecord(
        severity=severity,
        message=message,
        source=source,
        timestamp=datetime.now().isoformat(),
    )
    state.alerts.append(record)
    state.alerts = state.alerts[-100:]  # Keep last 100
    save_shared_state(state)


def resolve_alerts(source: str = ""):
    """Mark alerts from a source as resolved."""
    state = load_shared_state()
    for alert in state.alerts:
        if not source or alert.source == source:
            alert.resolved = True
    save_shared_state(state)


def get_active_alerts() -> list[AlertRecord]:
    """Get unresolved alerts."""
    state = load_shared_state()
    return [a for a in state.alerts if not a.resolved]


def get_corporation_summary() -> str:
    """Get a text summary of corporation state for CEO."""
    state = load_shared_state()

    lines = ["═══ CORPORATION STATE ═══"]

    # Financial
    f = state.financial
    if f.updated_at:
        lines.append(f"\n💰 Финансы (обн. {f.updated_at[:10]}):")
        lines.append(f"  Банк: {f.bank_balance_rub:,.0f} ₽ | Крипто: ${f.crypto_portfolio_usd:,.0f}")
        lines.append(f"  Доход: {f.total_revenue_rub:,.0f} ₽ | Расход: {f.total_expenses_rub:,.0f} ₽")
        lines.append(f"  API: ${f.api_costs_usd:,.2f} | MRR: {f.mrr_rub:,.0f} ₽")
    else:
        lines.append("\n💰 Финансы: нет данных")

    # Tech
    t = state.tech
    if t.updated_at:
        lines.append(f"\n⚙️ Техника (обн. {t.updated_at[:10]}):")
        lines.append(f"  Статус: {t.overall_status} | Сервисы: {t.services_up}/{t.services_total}")
        if t.errors_count:
            lines.append(f"  ❌ Ошибок: {t.errors_count}")
    else:
        lines.append("\n⚙️ Техника: нет данных")

    # Content
    c = state.content
    if c.updated_at:
        lines.append(f"\n📱 Контент (обн. {c.updated_at[:10]}):")
        lines.append(f"  Создано: {c.posts_generated} | Опубликовано: {c.posts_published}")
        lines.append(f"  LinkedIn: {c.linkedin_status} | Качество: {c.avg_quality_score:.1f}")
    else:
        lines.append("\n📱 Контент: нет данных")

    # Product
    p = state.product
    if p.updated_at:
        lines.append(f"\n📋 Продукт (обн. {p.updated_at[:10]}):")
        lines.append(f"  Фичи: {p.features_done}/{p.features_total} done, {p.features_blocked} blocked")
        if p.current_sprint:
            lines.append(f"  Спринт: {p.current_sprint} ({p.sprint_progress_pct}%)")
    else:
        lines.append("\n📋 Продукт: нет данных")

    # Alerts
    active_alerts = [a for a in state.alerts if not a.resolved]
    if active_alerts:
        lines.append(f"\n⚠️ Алерты ({len(active_alerts)}):")
        for a in active_alerts[-5:]:
            icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(a.severity, "🔵")
            lines.append(f"  {icon} {a.message}")

    # Recent decisions
    if state.decisions:
        lines.append(f"\n📝 Последние решения:")
        for d in state.decisions[-3:]:
            lines.append(f"  • {d.decision}")

    return "\n".join(lines)
