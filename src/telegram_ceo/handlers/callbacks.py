"""Callback handlers for CTO improvement proposals and API diagnostics in CEO bot."""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta

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
            old_status = p.get("status")
            p.update(updates)
            p["reviewed_at"] = datetime.now().isoformat()
            # Update stats only if status actually changed
            new_status = updates.get("status")
            if (
                new_status
                and new_status in ("approved", "rejected", "conditions")
                and new_status != old_status
            ):
                data["stats"][new_status] = data["stats"].get(new_status, 0) + 1
            _save_proposals(data)
            return p
    return None


@router.callback_query(F.data.startswith("cto_approve:"))
async def on_cto_approve(callback: CallbackQuery):
    """Approve a CTO improvement proposal and auto-apply changes."""
    proposal_id = callback.data.split(":")[1]
    proposal = _find_and_update_proposal(proposal_id, {"status": "approved"})

    if not proposal:
        await callback.answer("Предложение не найдено", show_alert=True)
        return

    from ...tools.improvement_advisor import _AGENT_LABELS

    target = _AGENT_LABELS.get(proposal.get("target_agent", ""), proposal.get("target_agent", ""))

    # Show "applying..." status
    try:
        await callback.message.edit_text(
            f"⏳ ПРИМЕНЯЮ ИЗМЕНЕНИЯ...\n\n"
            f"📋 {proposal.get('title', '?')}\n"
            f"🎯 Агент: {target}\n\n"
            f"Мартин вносит правки в YAML-конфигурацию...",
            reply_markup=None,
        )
    except Exception as e:
        logger.warning(f"edit_text failed for proposal {proposal_id}: {e}")
    await callback.answer("Одобрено! Применяю...")

    # Auto-apply the proposal
    try:
        from ...tools.proposal_applier import apply_proposal, format_diff_for_telegram

        result = await asyncio.to_thread(apply_proposal, proposal)

        if result["applied"]:
            # Store result in proposal record
            _find_and_update_proposal(proposal_id, {
                "applied_diff": result["diff"],
                "applied_at": datetime.now().isoformat(),
            })
            diff_text = format_diff_for_telegram(result["diff"])
            try:
                await callback.message.edit_text(
                    f"✅ ОДОБРЕНО И ПРИМЕНЕНО\n\n"
                    f"📋 {proposal.get('title', '?')}\n"
                    f"🎯 Агент: {target}\n\n"
                    f"📝 Изменения в YAML:\n"
                    f"<pre>{diff_text}</pre>\n\n"
                    f"💡 {result['message']}",
                    parse_mode="HTML",
                    reply_markup=None,
                )
            except Exception as e:
                logger.warning(f"edit_text with diff failed: {e}")
                # Fallback without HTML formatting
                try:
                    await callback.message.edit_text(
                        f"✅ ОДОБРЕНО И ПРИМЕНЕНО\n\n"
                        f"📋 {proposal.get('title', '?')}\n"
                        f"🎯 Агент: {target}\n\n"
                        f"💡 {result['message']}",
                        reply_markup=None,
                    )
                except Exception:
                    pass
        else:
            # Tool proposals or other non-applicable
            try:
                await callback.message.edit_text(
                    f"✅ ОДОБРЕНО\n\n"
                    f"📋 {proposal.get('title', '?')}\n"
                    f"🎯 Агент: {target}\n\n"
                    f"💡 {result['message']}",
                    reply_markup=None,
                )
            except Exception as e:
                logger.warning(f"edit_text failed: {e}")

    except Exception as apply_err:
        logger.error(f"Failed to apply proposal {proposal_id}: {apply_err}")
        # Store error in proposal record
        _find_and_update_proposal(proposal_id, {
            "apply_error": str(apply_err),
        })
        try:
            await callback.message.edit_text(
                f"✅ ОДОБРЕНО (не применено)\n\n"
                f"📋 {proposal.get('title', '?')}\n"
                f"🎯 Агент: {target}\n\n"
                f"⚠️ Ошибка применения: {str(apply_err)[:500]}\n"
                f"Предложение одобрено, но изменения не внесены автоматически.",
                reply_markup=None,
            )
        except Exception as e:
            logger.warning(f"edit_text failed after apply error: {e}")

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
    try:
        await callback.message.edit_text(
            f"❌ ОТКЛОНЕНО\n\n"
            f"📋 {proposal.get('title', '?')}\n"
            f"🎯 Агент: {target}\n\n"
            f"Предложение отклонено.",
            reply_markup=None,
        )
    except Exception as e:
        logger.warning(f"edit_text failed for proposal {proposal_id}: {e}")
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
    try:
        await callback.message.edit_text(
            f"📝 Введите условия для предложения:\n\n"
            f"📋 {proposal.get('title', '?')}\n"
            f"🎯 Агент: {target}\n\n"
            f"Напишите текст условий — Мартин учтёт их при доработке.",
            reply_markup=None,
        )
    except Exception as e:
        logger.warning(f"edit_text failed for conditions {proposal_id}: {e}")
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

    # Show applied diff if proposal was applied
    applied_diff = proposal.get("applied_diff")
    applied_at = proposal.get("applied_at")
    if applied_diff:
        from ...tools.proposal_applier import format_diff_for_telegram
        diff_text = format_diff_for_telegram(applied_diff, max_len=1500)
        text += f"\n\n✅ Применено: {applied_at or '?'}\n📝 Diff:\n{diff_text}"

    apply_error = proposal.get("apply_error")
    if apply_error:
        text += f"\n\n⚠️ Ошибка применения: {apply_error[:300]}"

    from ..keyboards import proposal_keyboard

    # Truncate to Telegram limit
    if len(text) > 4000:
        text = text[:4000] + "..."

    try:
        await callback.message.edit_text(text, reply_markup=proposal_keyboard(proposal_id))
    except Exception as e:
        logger.warning(f"edit_text failed for detail {proposal_id}: {e}")
    await callback.answer()


# ═══════════════════════════════════════════════════════════════
# API Diagnostics — storage + callbacks
# ═══════════════════════════════════════════════════════════════

def _diagnostic_path() -> str:
    """Path to API diagnostics JSON storage."""
    for p in ["/app/data/api_diagnostics.json", "data/api_diagnostics.json"]:
        d = os.path.dirname(p)
        if d and os.path.isdir(d):
            return p
    return "data/api_diagnostics.json"


def _load_diagnostics() -> dict:
    """Load diagnostics data from JSON file."""
    path = _diagnostic_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "diagnostics": [],
        "stats": {"total": 0, "recheck_ok": 0, "recheck_fail": 0, "acknowledged": 0},
        "last_analysis": None,
    }


def _save_diagnostics(data: dict):
    """Save diagnostics data, capped at 100 records."""
    path = _diagnostic_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    data["diagnostics"] = data["diagnostics"][-100:]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _find_diagnostic(diag_id: str) -> dict | None:
    """Find a diagnostic record by ID."""
    data = _load_diagnostics()
    for d in data["diagnostics"]:
        if d.get("id") == diag_id:
            return d
    return None


def _update_diagnostic(diag_id: str, updates: dict):
    """Find diagnostic by ID, apply updates, save."""
    data = _load_diagnostics()
    for d in data["diagnostics"]:
        if d.get("id") == diag_id:
            d.update(updates)
            # Update stats
            status = updates.get("status")
            if status == "recheck_ok":
                data["stats"]["recheck_ok"] = data["stats"].get("recheck_ok", 0) + 1
            elif status == "recheck_fail":
                data["stats"]["recheck_fail"] = data["stats"].get("recheck_fail", 0) + 1
            elif status == "acknowledged":
                data["stats"]["acknowledged"] = data["stats"].get("acknowledged", 0) + 1
            _save_diagnostics(data)
            return d
    return None


@router.callback_query(F.data.startswith("api_recheck:"))
async def on_api_recheck(callback: CallbackQuery):
    """Re-run health check for failed APIs and report results."""
    diag_id = callback.data.split(":")[1]
    diagnostic = _find_diagnostic(diag_id)

    if not diagnostic:
        await callback.answer("Диагностика не найдена", show_alert=True)
        return

    # Rate limit: 1 recheck per minute
    last_recheck = diagnostic.get("last_recheck")
    if last_recheck:
        try:
            last_time = datetime.fromisoformat(last_recheck)
            if datetime.now() - last_time < timedelta(minutes=1):
                await callback.answer(
                    "Подождите минуту перед следующей проверкой", show_alert=True
                )
                return
        except (ValueError, TypeError):
            pass

    await callback.answer("🔄 Перепроверяю...")

    from ...tools.tech_tools import _check_single_api, _API_REGISTRY
    import asyncio

    failed_apis = diagnostic.get("failed_apis", [])
    results = {}
    still_failing = []

    for api_key in failed_apis:
        check = await asyncio.to_thread(_check_single_api, api_key)
        results[api_key] = check
        if not check.get("ok"):
            still_failing.append(api_key)

    now = datetime.now()
    recheck_count = diagnostic.get("recheck_count", 0) + 1

    if not still_failing:
        # All recovered
        _update_diagnostic(diag_id, {
            "status": "recheck_ok",
            "recheck_count": recheck_count,
            "last_recheck": now.isoformat(),
        })
        recovered = ", ".join(
            _API_REGISTRY.get(k, {}).get("name", k) for k in failed_apis
        )
        await callback.message.edit_text(
            f"{callback.message.text}\n\n"
            f"✅ ВСЕ API ВОССТАНОВЛЕНЫ!\n"
            f"Мартин: {recovered} — теперь работают."
        )
    else:
        _update_diagnostic(diag_id, {
            "status": "recheck_fail",
            "recheck_count": recheck_count,
            "last_recheck": now.isoformat(),
        })
        still_names = ", ".join(
            _API_REGISTRY.get(k, {}).get("name", k) for k in still_failing
        )
        from ..keyboards import diagnostic_keyboard
        try:
            await callback.message.edit_reply_markup(
                reply_markup=diagnostic_keyboard(diag_id)
            )
        except Exception:
            pass
        await callback.answer(
            f"Проблемы остаются: {still_names[:150]}", show_alert=True
        )

    logger.info(f"API recheck {diag_id}: {len(failed_apis)-len(still_failing)} OK, {len(still_failing)} fail")


@router.callback_query(F.data.startswith("api_detail:"))
async def on_api_detail(callback: CallbackQuery):
    """Show full CTO analysis and per-API details."""
    diag_id = callback.data.split(":")[1]
    diagnostic = _find_diagnostic(diag_id)

    if not diagnostic:
        await callback.answer("Диагностика не найдена", show_alert=True)
        return

    from ...tools.tech_tools import _API_REGISTRY

    lines = [
        f"═══ ДИАГНОСТИКА API ═══",
        f"Время: {diagnostic.get('timestamp', '?')}",
        "",
    ]

    # Per-API details
    for api_key, result in diagnostic.get("results", {}).items():
        api_info = _API_REGISTRY.get(api_key, {})
        icon = "✅" if result.get("ok") else "❌"
        name = api_info.get("name", api_key)
        ms = f" ({result.get('ms', 0)}ms)" if result.get("ms") else ""
        lines.append(f"{icon} {name}{ms}")
        if not result.get("ok"):
            lines.append(f"  Ошибка: {result.get('error', '?')}")
            env_vars = api_info.get("env_vars", [])
            if env_vars:
                lines.append(f"  Env: {', '.join(env_vars)}")

    # CTO analysis
    analysis = diagnostic.get("analysis", "")
    if analysis:
        lines.append("")
        lines.append("💡 АНАЛИЗ МАРТИНА (CTO):")
        lines.append(analysis[:1500])

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "..."

    from ..keyboards import diagnostic_keyboard

    await callback.message.edit_text(text, reply_markup=diagnostic_keyboard(diag_id))
    await callback.answer()


@router.callback_query(F.data.startswith("api_ack:"))
async def on_api_ack(callback: CallbackQuery):
    """Acknowledge diagnostic — mark as handled, remove buttons."""
    diag_id = callback.data.split(":")[1]
    diagnostic = _find_diagnostic(diag_id)

    if not diagnostic:
        await callback.answer("Диагностика не найдена", show_alert=True)
        return

    _update_diagnostic(diag_id, {"status": "acknowledged"})

    await callback.message.edit_text(
        f"{callback.message.text}\n\n"
        f"✅ Принято — проблема отмечена как обработанная."
    )
    await callback.answer("Принято")
    logger.info(f"API diagnostic {diag_id} acknowledged")
