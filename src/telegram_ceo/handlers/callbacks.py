"""Callback handlers for CTO improvement proposals in CEO bot."""

import json
import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.types import CallbackQuery

logger = logging.getLogger(__name__)

router = Router()

# State for "conditions" mode — user types conditions text after pressing button
_conditions_state: dict[int, str] = {}  # user_id -> proposal_id


def is_in_conditions_mode(user_id: int) -> bool:
    """Check if user is currently entering conditions for a proposal."""
    return user_id in _conditions_state


def get_conditions_proposal_id(user_id: int) -> str:
    """Get and clear the proposal ID from conditions state."""
    return _conditions_state.pop(user_id, "")


def _find_and_update_proposal(proposal_id: str, updates: dict) -> dict | None:
    """Find proposal by ID, apply updates, save. Returns updated proposal or None."""
    from ...tools.improvement_advisor import _load_proposals, _save_proposals

    data = _load_proposals()
    for p in data.get("proposals", []):
        if p.get("id") == proposal_id:
            p.update(updates)
            p["reviewed_at"] = datetime.now().isoformat()
            # Update stats
            status = updates.get("status")
            if status and status in ("approved", "rejected", "conditions"):
                data["stats"][status] = data["stats"].get(status, 0) + 1
            _save_proposals(data)
            return p
    return None


@router.callback_query(F.data.startswith("cto_approve:"))
async def on_cto_approve(callback: CallbackQuery):
    """Approve a CTO improvement proposal."""
    proposal_id = callback.data.split(":")[1]
    proposal = _find_and_update_proposal(proposal_id, {"status": "approved"})

    if not proposal:
        await callback.answer("Предложение не найдено", show_alert=True)
        return

    from ..keyboards import proposal_keyboard
    from ...tools.improvement_advisor import _AGENT_LABELS

    target = _AGENT_LABELS.get(proposal.get("target_agent", ""), proposal.get("target_agent", ""))
    await callback.message.edit_text(
        f"✅ ОДОБРЕНО\n\n"
        f"📋 {proposal.get('title', '?')}\n"
        f"🎯 Агент: {target}\n\n"
        f"Предложение принято. Мартин учтёт при следующей доработке."
    )
    await callback.answer("Одобрено!")
    logger.info(f"Proposal {proposal_id} approved")


@router.callback_query(F.data.startswith("cto_reject:"))
async def on_cto_reject(callback: CallbackQuery):
    """Reject a CTO improvement proposal."""
    proposal_id = callback.data.split(":")[1]
    proposal = _find_and_update_proposal(proposal_id, {"status": "rejected"})

    if not proposal:
        await callback.answer("Предложение не найдено", show_alert=True)
        return

    from ...tools.improvement_advisor import _AGENT_LABELS

    target = _AGENT_LABELS.get(proposal.get("target_agent", ""), proposal.get("target_agent", ""))
    await callback.message.edit_text(
        f"❌ ОТКЛОНЕНО\n\n"
        f"📋 {proposal.get('title', '?')}\n"
        f"🎯 Агент: {target}\n\n"
        f"Предложение отклонено."
    )
    await callback.answer("Отклонено")
    logger.info(f"Proposal {proposal_id} rejected")


@router.callback_query(F.data.startswith("cto_conditions:"))
async def on_cto_conditions(callback: CallbackQuery):
    """Enter conditions mode — user types conditions text."""
    proposal_id = callback.data.split(":")[1]

    from ...tools.improvement_advisor import _load_proposals, _AGENT_LABELS

    data = _load_proposals()
    proposal = None
    for p in data.get("proposals", []):
        if p.get("id") == proposal_id:
            proposal = p
            break

    if not proposal:
        await callback.answer("Предложение не найдено", show_alert=True)
        return

    _conditions_state[callback.from_user.id] = proposal_id

    target = _AGENT_LABELS.get(proposal.get("target_agent", ""), proposal.get("target_agent", ""))
    await callback.message.edit_text(
        f"📝 Введите условия для предложения:\n\n"
        f"📋 {proposal.get('title', '?')}\n"
        f"🎯 Агент: {target}\n\n"
        f"Напишите текст условий — Мартин учтёт их при доработке."
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cto_detail:"))
async def on_cto_detail(callback: CallbackQuery):
    """Show full proposal details."""
    proposal_id = callback.data.split(":")[1]

    from ...tools.improvement_advisor import _load_proposals, _AGENT_LABELS

    data = _load_proposals()
    proposal = None
    for p in data.get("proposals", []):
        if p.get("id") == proposal_id:
            proposal = p
            break

    if not proposal:
        await callback.answer("Предложение не найдено", show_alert=True)
        return

    target = _AGENT_LABELS.get(proposal.get("target_agent", ""), proposal.get("target_agent", ""))
    type_labels = {"prompt": "📝 Промпт", "tool": "🔧 Инструмент", "model_tier": "🧠 Модель"}
    ptype = type_labels.get(proposal.get("proposal_type", ""), proposal.get("proposal_type", "?"))

    text = (
        f"📋 {proposal.get('title', '?')}\n"
        f"🎯 Агент: {target}\n"
        f"📊 Тип: {ptype}\n"
        f"📈 Уверенность: {proposal.get('confidence_score', 0):.0%}\n\n"
        f"📌 Текущее состояние:\n{proposal.get('current_state', '—')}\n\n"
        f"💡 Предлагаемое изменение:\n{proposal.get('proposed_change', '—')}\n\n"
        f"📝 Описание:\n{proposal.get('description', '—')[:1500]}"
    )

    from ..keyboards import proposal_keyboard

    # Truncate to Telegram limit
    if len(text) > 4000:
        text = text[:4000] + "..."

    await callback.message.edit_text(text, reply_markup=proposal_keyboard(proposal_id))
    await callback.answer()
