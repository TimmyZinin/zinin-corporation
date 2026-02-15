"""Typed CallbackData factories for CEO bot inline keyboards.

Uses aiogram's CallbackData for type-safe callback routing
instead of raw string matching with F.data.startswith().
"""

from aiogram.filters.callback_data import CallbackData


class TaskCB(CallbackData, prefix="task"):
    """Task Pool callbacks: new, all, filter, detail, assign, start, done, block, delete."""
    action: str
    id: str = ""
    agent: str = ""


class EscCB(CallbackData, prefix="esc"):
    """Escalation callbacks: extend, create, split, manual."""
    action: str
    id: str = ""


class CtoCB(CallbackData, prefix="cto"):
    """CTO proposal callbacks: approve, reject, conditions, detail."""
    action: str
    id: str = ""


class ApiCB(CallbackData, prefix="api"):
    """API diagnostic callbacks: recheck, detail, ack."""
    action: str
    id: str = ""


class ActionCB(CallbackData, prefix="action"):
    """Proactive action callbacks: launch, skip."""
    action: str
    id: str = ""


class EveningCB(CallbackData, prefix="evening"):
    """Evening review callbacks: approve, adjust."""
    action: str


class GalleryCB(CallbackData, prefix="gal"):
    """Gallery callbacks: ok, no, fwd, page, noop."""
    action: str
    id: str = ""


class VoiceBrainCB(CallbackData, prefix="vb"):
    """Voice brain dump callbacks: confirm, correct, cancel."""
    action: str


class ApprovalCB(CallbackData, prefix="approve"):
    """Approval gate callbacks: yes, no, edit."""
    action: str
    id: str = ""


class SubMenuCB(CallbackData, prefix="sub"):
    """Sub-menu callbacks: content_post, content_calendar, etc."""
    menu: str
    action: str
