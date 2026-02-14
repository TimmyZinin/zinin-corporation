"""Callback handlers for CTO proposals, API diagnostics, Task Pool, and Gallery in CEO bot."""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery

from ...error_handler import format_error_for_user

logger = logging.getLogger(__name__)

router = Router()

# State for "conditions" mode — user types conditions text after pressing button
_conditions_state: dict[int, str] = {}  # user_id -> proposal_id

# State for "new task" mode — user types task title after pressing button
_new_task_state: set[int] = set()  # user_ids waiting for task title


def is_in_new_task_mode(user_id: int) -> bool:
    """Check if user is currently entering a new task title."""
    return user_id in _new_task_state


def consume_new_task_mode(user_id: int) -> bool:
    """Clear new-task mode and return True if was active."""
    return _new_task_state.discard(user_id) is None and user_id not in _new_task_state


# ═══════════════════════════════════════════════════════════════
# Task Pool callbacks
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "task_new")
async def on_task_new(callback: CallbackQuery):
    """Enter new task mode — user types title next."""
    _new_task_state.add(callback.from_user.id)
    await callback.message.edit_text("📝 Напишите заголовок задачи:")
    await callback.answer()


@router.callback_query(F.data == "task_all")
async def on_task_all(callback: CallbackQuery):
    """Show all active tasks."""
    from ...task_pool import get_all_tasks, format_task_summary, format_pool_summary, TaskStatus
    from ..keyboards import task_menu_keyboard

    tasks = get_all_tasks()
    if not tasks:
        await callback.message.edit_text(
            "📋 Task Pool пуст",
            reply_markup=task_menu_keyboard(),
        )
        await callback.answer()
        return

    active = [t for t in tasks if t.status != TaskStatus.DONE]
    done_count = sum(1 for t in tasks if t.status == TaskStatus.DONE)

    lines = [format_pool_summary(), ""]
    for t in sorted(active, key=lambda x: x.priority):
        lines.append(format_task_summary(t))
        lines.append("")
    if done_count:
        lines.append(f"✅ Завершённых: {done_count}")

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "..."

    try:
        await callback.message.edit_text(text, reply_markup=task_menu_keyboard(), parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=task_menu_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("task_filter:"))
async def on_task_filter(callback: CallbackQuery):
    """Filter tasks by status."""
    from ...task_pool import get_tasks_by_status, TaskStatus, format_task_summary
    from ..keyboards import task_menu_keyboard

    status_str = callback.data.split(":")[1]
    try:
        status = TaskStatus(status_str)
    except ValueError:
        await callback.answer("Неизвестный статус", show_alert=True)
        return

    tasks = get_tasks_by_status(status)
    if not tasks:
        await callback.message.edit_text(
            f"Нет задач со статусом {status_str}",
            reply_markup=task_menu_keyboard(),
        )
        await callback.answer()
        return

    lines = [f"📋 Задачи — {status_str} ({len(tasks)})\n"]
    for t in sorted(tasks, key=lambda x: x.priority):
        lines.append(format_task_summary(t))
        lines.append("")

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "..."

    try:
        await callback.message.edit_text(text, reply_markup=task_menu_keyboard(), parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=task_menu_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("task_detail:"))
async def on_task_detail(callback: CallbackQuery):
    """Show task detail with action buttons."""
    from ...task_pool import get_task, format_task_summary
    from ..keyboards import task_detail_keyboard

    task_id = callback.data.split(":")[1]
    task = get_task(task_id)
    if not task:
        await callback.answer("Задача не найдена", show_alert=True)
        return

    text = format_task_summary(task)
    if task.result:
        text += f"\n\n📝 Результат: {task.result[:500]}"

    try:
        await callback.message.edit_text(
            text,
            reply_markup=task_detail_keyboard(task_id, task.status.value),
            parse_mode="HTML",
        )
    except Exception:
        await callback.message.answer(
            text,
            reply_markup=task_detail_keyboard(task_id, task.status.value),
            parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(F.data.startswith("task_assign:"))
async def on_task_assign(callback: CallbackQuery):
    """Show agent selection keyboard."""
    from ...task_pool import get_task, suggest_assignee
    from ..keyboards import task_assign_keyboard

    task_id = callback.data.split(":")[1]
    task = get_task(task_id)
    if not task:
        await callback.answer("Задача не найдена", show_alert=True)
        return

    suggestion = suggest_assignee(task.tags)
    text = f"👤 Назначить: <b>{task.title}</b>\n"
    if suggestion:
        rec = ", ".join(f"{a} ({c:.0%})" for a, c in suggestion[:3])
        text += f"💡 Рекомендация: {rec}"

    try:
        await callback.message.edit_text(
            text, reply_markup=task_assign_keyboard(task_id), parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(
            text, reply_markup=task_assign_keyboard(task_id), parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("task_do_assign:"))
async def on_task_do_assign(callback: CallbackQuery):
    """Actually assign task to selected agent."""
    from ...task_pool import assign_task, format_task_summary
    from ..keyboards import task_detail_keyboard

    parts = callback.data.split(":")
    task_id = parts[1]
    agent_key = parts[2]

    task = assign_task(task_id, assignee=agent_key, assigned_by="ceo-alexey")
    if not task:
        await callback.answer("Не удалось назначить", show_alert=True)
        return

    text = f"✅ Назначено → {agent_key}\n\n{format_task_summary(task)}"
    try:
        await callback.message.edit_text(
            text,
            reply_markup=task_detail_keyboard(task_id, task.status.value),
            parse_mode="HTML",
        )
    except Exception:
        await callback.message.answer(
            text,
            reply_markup=task_detail_keyboard(task_id, task.status.value),
            parse_mode="HTML",
        )
    await callback.answer(f"Назначено: {agent_key}")


@router.callback_query(F.data.startswith("task_start:"))
async def on_task_start(callback: CallbackQuery):
    """Start a task: ASSIGNED → IN_PROGRESS."""
    from ...task_pool import start_task, format_task_summary
    from ..keyboards import task_detail_keyboard

    task_id = callback.data.split(":")[1]
    task = start_task(task_id)
    if not task:
        await callback.answer("Не удалось начать задачу", show_alert=True)
        return

    text = f"▶️ В работе!\n\n{format_task_summary(task)}"
    try:
        await callback.message.edit_text(
            text,
            reply_markup=task_detail_keyboard(task_id, task.status.value),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await callback.answer("В работе")


@router.callback_query(F.data.startswith("task_done:"))
async def on_task_done(callback: CallbackQuery):
    """Complete a task: IN_PROGRESS → DONE."""
    from ...task_pool import complete_task, format_task_summary

    task_id = callback.data.split(":")[1]
    task = complete_task(task_id)
    if not task:
        await callback.answer("Не удалось завершить", show_alert=True)
        return

    text = f"✅ Завершено!\n\n{format_task_summary(task)}"
    try:
        await callback.message.edit_text(text, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer("Завершено")


@router.callback_query(F.data.startswith("task_block:"))
async def on_task_block(callback: CallbackQuery):
    """Block a task."""
    from ...task_pool import block_task, format_task_summary
    from ..keyboards import task_detail_keyboard

    task_id = callback.data.split(":")[1]
    task = block_task(task_id)
    if not task:
        await callback.answer("Не удалось заблокировать", show_alert=True)
        return

    text = f"🚫 Заблокировано\n\n{format_task_summary(task)}"
    try:
        await callback.message.edit_text(
            text,
            reply_markup=task_detail_keyboard(task_id, task.status.value),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await callback.answer("Заблокировано")


@router.callback_query(F.data.startswith("task_delete:"))
async def on_task_delete(callback: CallbackQuery):
    """Delete a task from the pool."""
    from ...task_pool import delete_task
    from ..keyboards import task_menu_keyboard

    task_id = callback.data.split(":")[1]
    ok = delete_task(task_id)
    if not ok:
        await callback.answer("Задача не найдена", show_alert=True)
        return

    try:
        await callback.message.edit_text(
            f"🗑 Задача {task_id} удалена",
            reply_markup=task_menu_keyboard(),
        )
    except Exception:
        pass
    await callback.answer("Удалено")


# ═══════════════════════════════════════════════════════════════
# Escalation callbacks (when no agent matches task tags)
# ═══════════════════════════════════════════════════════════════

# State for split-task mode
_split_task_state: dict[int, str] = {}  # user_id → task_id


def is_in_split_mode(user_id: int) -> bool:
    return user_id in _split_task_state


@router.callback_query(F.data.startswith("esc_extend:"))
async def on_esc_extend(callback: CallbackQuery):
    """Suggest extending the closest agent's prompt with new tags."""
    from ...task_pool import get_task, suggest_assignee, AGENT_TAGS

    task_id = callback.data.split(":")[1]
    task = get_task(task_id)
    if not task:
        await callback.answer("Задача не найдена", show_alert=True)
        return

    suggestions = suggest_assignee(task.tags)
    if suggestions:
        agent, conf = suggestions[0]
        existing = set(AGENT_TAGS.get(agent, []))
        new_tags = [t for t in task.tags if t not in existing]
        text = (
            f"🔧 <b>Расширить промпт</b>\n\n"
            f"Ближайший агент: <b>{agent}</b> ({conf:.0%})\n"
            f"Новые теги для добавления: {', '.join(new_tags) or '—'}\n\n"
            f"Добавьте эти теги в <code>agents/{agent}.yaml</code> "
            f"и <code>src/task_pool.py:AGENT_TAGS</code>"
        )
    else:
        text = (
            "🔧 <b>Расширить промпт</b>\n\n"
            "Нет подходящих агентов. Рассмотрите создание нового агента."
        )

    try:
        await callback.message.edit_text(text, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("esc_create:"))
async def on_esc_create(callback: CallbackQuery):
    """Suggest creating a new agent for unmatched task tags."""
    from ...task_pool import get_task

    task_id = callback.data.split(":")[1]
    task = get_task(task_id)
    if not task:
        await callback.answer("Задача не найдена", show_alert=True)
        return

    tags_str = ", ".join(task.tags) if task.tags else "—"
    text = (
        f"🤖 <b>Создать нового агента</b>\n\n"
        f"Задача: {task.title}\n"
        f"Теги: {tags_str}\n\n"
        f"Шаблон для нового агента:\n"
        f"<code>agents/new_agent.yaml</code>\n"
        f"role: \"New Agent\"\n"
        f"goal: \"...\"\n"
        f"tags: [{tags_str}]\n\n"
        f"Создайте агента и добавьте его теги в AGENT_TAGS."
    )

    try:
        await callback.message.edit_text(text, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("esc_split:"))
async def on_esc_split(callback: CallbackQuery):
    """Enter split-task mode — user types subtask titles."""
    task_id = callback.data.split(":")[1]
    _split_task_state[callback.from_user.id] = task_id
    await callback.message.edit_text(
        "✂️ Разделить задачу — введите подзадачи (каждая с новой строки):"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("esc_manual:"))
async def on_esc_manual(callback: CallbackQuery):
    """Fallback to standard agent assignment keyboard."""
    from ..keyboards import task_assign_keyboard

    task_id = callback.data.split(":")[1]
    text = "👤 Выберите агента для ручного назначения:"

    try:
        await callback.message.edit_text(
            text, reply_markup=task_assign_keyboard(task_id)
        )
    except Exception:
        await callback.message.answer(
            text, reply_markup=task_assign_keyboard(task_id)
        )
    await callback.answer()


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


# ── Proactive System callbacks ───────────────────────────────────────────────

# State for evening adjust mode
_evening_adjust_state: set[int] = set()


def is_in_evening_adjust_mode(user_id: int) -> bool:
    """Check if user is in evening adjustment text input mode."""
    return user_id in _evening_adjust_state


def consume_evening_adjust_mode(user_id: int) -> bool:
    """Clear evening adjust mode, return True if was active."""
    if user_id in _evening_adjust_state:
        _evening_adjust_state.discard(user_id)
        return True
    return False


@router.callback_query(F.data.startswith("action_launch:"))
async def on_action_launch(callback: CallbackQuery):
    """Launch an action from the proactive planner."""
    action_id = callback.data.split(":")[1]

    try:
        from ...proactive_planner import get_action, set_action_status, get_next_pending_action, AGENT_METHOD_MAP
        from ...telegram.bridge import AgentBridge
        from ...telegram.formatters import format_for_telegram
        from ..keyboards import action_keyboard

        action = get_action(action_id)
        if not action:
            await callback.answer("Действие не найдено или истекло", show_alert=True)
            return

        set_action_status(action_id, "launched")
        await callback.message.edit_text(
            f"🚀 Запускаю: {action.title}\n⏳ Работаю..."
        )
        await callback.answer("Запуск...")

        # Route to appropriate AgentBridge method
        method_name = AGENT_METHOD_MAP.get(action.agent_method, "send_to_agent")
        kwargs = action.method_kwargs or {}

        try:
            if method_name == "send_to_agent":
                result = await asyncio.wait_for(
                    AgentBridge.send_to_agent(
                        message=kwargs.get("message", action.title),
                        agent_name=action.target_agent,
                    ),
                    timeout=120,
                )
            elif hasattr(AgentBridge, method_name):
                method = getattr(AgentBridge, method_name)
                result = await asyncio.wait_for(method(**kwargs), timeout=120)
            else:
                result = await asyncio.wait_for(
                    AgentBridge.send_to_agent(
                        message=action.title,
                        agent_name=action.target_agent,
                    ),
                    timeout=120,
                )

            set_action_status(action_id, "completed")

            # Send any images found in result, then text
            from ..image_sender import send_images_from_response
            result_text = await send_images_from_response(
                callback.message.bot, callback.message.chat.id, str(result)
            )
            for chunk in format_for_telegram(result_text):
                await callback.message.answer(chunk)

            # Suggest next action
            next_action = get_next_pending_action()
            if next_action:
                await callback.message.answer(
                    f"📋 Следующее действие:",
                )
                await callback.message.answer(
                    f"{'🔴' if next_action.priority <= 1 else '🟡' if next_action.priority == 2 else '🟢'} {next_action.title}",
                    reply_markup=action_keyboard(next_action.id),
                )
            else:
                await callback.message.answer("✅ Все действия выполнены!")

        except asyncio.TimeoutError:
            logger.warning(f"Action {action_id} timed out after 120s")
            set_action_status(action_id, "pending")
            await callback.message.answer(
                f"⏱ Действие не выполнено за 120 сек. Попробуйте снова."
            )
        except Exception as e:
            logger.error(f"Action launch error: {e}", exc_info=True)
            set_action_status(action_id, "pending")  # Return to pending on failure
            await callback.message.answer(f"❌ Ошибка: {format_error_for_user(e)}")

    except Exception as e:
        logger.error(f"Action launch handler error: {e}", exc_info=True)
        await callback.answer(f"Ошибка: {format_error_for_user(e)[:100]}", show_alert=True)


@router.callback_query(F.data.startswith("action_skip:"))
async def on_action_skip(callback: CallbackQuery):
    """Skip an action from the proactive planner."""
    action_id = callback.data.split(":")[1]

    try:
        from ...proactive_planner import get_action, set_action_status, get_next_pending_action
        from ..keyboards import action_keyboard

        action = get_action(action_id)
        if not action:
            await callback.answer("Действие не найдено", show_alert=True)
            return

        set_action_status(action_id, "skipped")
        await callback.message.edit_text(
            f"⏭ Пропущено: {action.title}"
        )
        await callback.answer("Пропущено")

        # Suggest next action
        next_action = get_next_pending_action()
        if next_action:
            await callback.message.answer(
                f"{'🔴' if next_action.priority <= 1 else '🟡' if next_action.priority == 2 else '🟢'} {next_action.title}",
                reply_markup=action_keyboard(next_action.id),
            )

    except Exception as e:
        logger.error(f"Action skip error: {e}", exc_info=True)
        await callback.answer(f"Ошибка: {format_error_for_user(e)[:100]}", show_alert=True)


@router.callback_query(F.data == "evening_approve")
async def on_evening_approve(callback: CallbackQuery):
    """Approve the evening plan."""
    await callback.message.edit_text(
        f"{callback.message.text}\n\n"
        f"✅ План на завтра утверждён."
    )
    await callback.answer("План утверждён")
    logger.info("Evening plan approved")


@router.callback_query(F.data == "evening_adjust")
async def on_evening_adjust(callback: CallbackQuery):
    """Enter evening adjustment mode — user types corrections."""
    user_id = callback.from_user.id
    _evening_adjust_state.add(user_id)
    await callback.message.edit_text(
        f"{callback.message.text}\n\n"
        f"✏️ Напиши, что изменить в плане на завтра:"
    )
    await callback.answer("Жду корректировки")


# ── Gallery callbacks ────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("gal_ok:"))
async def on_gallery_approve(callback: CallbackQuery):
    """Approve an image in the gallery."""
    image_id = callback.data.split(":", 1)[1]
    from ...image_registry import update_status, STATUS_APPROVED
    entry = update_status(image_id, STATUS_APPROVED)
    if entry:
        await callback.message.edit_text(
            f"{callback.message.text}\n\n✅ Изображение {image_id} одобрено"
        )
        await callback.answer("Одобрено")
    else:
        await callback.answer("Изображение не найдено", show_alert=True)


@router.callback_query(F.data.startswith("gal_no:"))
async def on_gallery_reject(callback: CallbackQuery):
    """Reject an image in the gallery."""
    image_id = callback.data.split(":", 1)[1]
    from ...image_registry import update_status, STATUS_REJECTED
    entry = update_status(image_id, STATUS_REJECTED)
    if entry:
        await callback.message.edit_text(
            f"{callback.message.text}\n\n❌ Изображение {image_id} отклонено"
        )
        await callback.answer("Отклонено")
    else:
        await callback.answer("Изображение не найдено", show_alert=True)


@router.callback_query(F.data.startswith("gal_fwd:"))
async def on_gallery_forward(callback: CallbackQuery):
    """Forward an image to Yuki (mark as forwarded)."""
    image_id = callback.data.split(":", 1)[1]
    from ...image_registry import forward_to_agent, update_status, STATUS_APPROVED
    entry = forward_to_agent(image_id, "smm")
    if entry:
        update_status(image_id, STATUS_APPROVED)
        await callback.message.edit_text(
            f"{callback.message.text}\n\n📱 Изображение {image_id} → Юки (одобрено + переслано)"
        )
        await callback.answer("Переслано Юки")
    else:
        await callback.answer("Изображение не найдено", show_alert=True)


@router.callback_query(F.data.startswith("gal_page:"))
async def on_gallery_page(callback: CallbackQuery):
    """Navigate gallery pages."""
    page = int(callback.data.split(":", 1)[1])
    from ...image_registry import get_gallery, STATUS_PENDING
    from ..keyboards import gallery_keyboard

    gallery = get_gallery(limit=5, page=page)
    images = gallery["images"]
    pages = gallery["pages"]

    if not images:
        await callback.answer("Страница пуста")
        return

    pending = sum(1 for img in images if img.get("status") == STATUS_PENDING)
    header = f"🖼 Галерея ({gallery['total']} изобр., стр. {page + 1}/{pages})"
    if pending:
        header += f" | ⏳ {pending} на утверждении"

    lines = [header, ""]
    for img in images:
        status_icon = {"pending": "⏳", "approved": "✅", "rejected": "❌"}.get(
            img.get("status", ""), "❓"
        )
        agent = img.get("source_agent", "?")
        style = img.get("style", "auto")
        topic = img.get("topic", "")[:40]
        img_id = img.get("id", "")
        lines.append(f"{status_icon} <code>{img_id}</code> [{agent}/{style}] {topic}")

    first_pending = next((img for img in images if img.get("status") == STATUS_PENDING), None)
    kb = gallery_keyboard(
        image_id=first_pending["id"] if first_pending else "",
        page=page,
        pages=pages,
    )

    await callback.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "gal_noop")
async def on_gallery_noop(callback: CallbackQuery):
    """No-op for page counter button."""
    await callback.answer()


# ── Voice Brain Dump callbacks ───────────────────────────────────────────────

@router.callback_query(F.data == "vb_confirm")
async def on_vb_confirm(callback: CallbackQuery):
    """Confirm voice brain dump — create tasks from parsed data."""
    from ..voice_brain_state import get_voice_brain_session, end_voice_brain_session
    from ..keyboards import task_menu_keyboard

    user_id = callback.from_user.id
    session = get_voice_brain_session(user_id)
    if not session:
        await callback.answer("Сессия истекла", show_alert=True)
        return

    end_voice_brain_session(user_id)

    if session.parsed_tasks:
        # Tasks already created by parse_brain_dump — just show result
        count = len(session.parsed_tasks)
        try:
            await callback.message.edit_text(
                f"✅ Создано {count} задач в Task Pool",
                reply_markup=task_menu_keyboard(),
            )
        except Exception:
            await callback.message.answer(
                f"✅ Создано {count} задач в Task Pool",
                reply_markup=task_menu_keyboard(),
            )
        await callback.answer(f"Создано {count} задач")
    elif session.proposals:
        # Create tasks from proposals
        from ...task_pool import create_task

        created = []
        for p in session.proposals:
            if len(p.get("text", "")) >= 5:
                task = create_task(p["text"], source="voice_proposal", assigned_by="tim")
                created.append(task)

        count = len(created)
        try:
            await callback.message.edit_text(
                f"✅ Создано {count} задач из предложений",
                reply_markup=task_menu_keyboard(),
            )
        except Exception:
            await callback.message.answer(
                f"✅ Создано {count} задач из предложений",
                reply_markup=task_menu_keyboard(),
            )
        await callback.answer(f"Создано {count} задач")
    else:
        try:
            await callback.message.edit_text("📝 Принято. Нет задач для создания.")
        except Exception:
            pass
        await callback.answer("Принято")


@router.callback_query(F.data == "vb_correct")
async def on_vb_correct(callback: CallbackQuery):
    """Enter voice brain dump correction mode."""
    from ..voice_brain_state import is_in_voice_brain_mode, can_iterate

    user_id = callback.from_user.id
    if not is_in_voice_brain_mode(user_id):
        await callback.answer("Сессия истекла", show_alert=True)
        return

    if not can_iterate(user_id):
        from ..voice_brain_state import end_voice_brain_session
        end_voice_brain_session(user_id)
        await callback.answer("Лимит уточнений достигнут", show_alert=True)
        return

    try:
        await callback.message.edit_text(
            "✏️ Отправьте уточнение текстом или голосом:",
            reply_markup=None,
        )
    except Exception:
        await callback.message.answer("✏️ Отправьте уточнение текстом или голосом:")
    await callback.answer()


@router.callback_query(F.data == "vb_cancel")
async def on_vb_cancel(callback: CallbackQuery):
    """Cancel voice brain dump session."""
    from ..voice_brain_state import end_voice_brain_session

    end_voice_brain_session(callback.from_user.id)
    try:
        await callback.message.edit_text("🚫 Голосовой дамп отменён.")
    except Exception:
        pass
    await callback.answer("Отменено")


# ── Sub-menu callbacks ───────────────────────────────────────────────────────

# State for new content post mode
_new_content_state: set[int] = set()


def is_in_new_content_mode(user_id: int) -> bool:
    return user_id in _new_content_state


@router.callback_query(F.data == "sub_content_post")
async def on_sub_content_post(callback: CallbackQuery):
    """Enter content post mode — user types topic next."""
    _new_content_state.add(callback.from_user.id)
    try:
        await callback.message.edit_text("📝 Напишите тему для поста:")
    except Exception:
        await callback.message.answer("📝 Напишите тему для поста:")
    await callback.answer()


@router.callback_query(F.data == "sub_content_calendar")
async def on_sub_content_calendar(callback: CallbackQuery):
    """Show content calendar."""
    from .commands import cmd_calendar
    await cmd_calendar(callback.message)
    await callback.answer()


@router.callback_query(F.data == "sub_content_linkedin")
async def on_sub_content_linkedin(callback: CallbackQuery):
    """Show LinkedIn status."""
    from .commands import cmd_linkedin
    await cmd_linkedin(callback.message)
    await callback.answer()


@router.callback_query(F.data == "sub_status_agents")
async def on_sub_status_agents(callback: CallbackQuery):
    """Show agent statuses."""
    from .commands import cmd_status
    await cmd_status(callback.message)
    await callback.answer()


@router.callback_query(F.data == "sub_status_tasks")
async def on_sub_status_tasks(callback: CallbackQuery):
    """Show task pool."""
    from .commands import cmd_tasks
    await cmd_tasks(callback.message)
    await callback.answer()


@router.callback_query(F.data == "sub_status_revenue")
async def on_sub_status_revenue(callback: CallbackQuery):
    """Show revenue summary (rule-based, no LLM)."""
    import json as _json
    revenue_path = None
    for p in ["/app/data/revenue.json", "data/revenue.json"]:
        if os.path.exists(p):
            revenue_path = p
            break

    if not revenue_path or not os.path.exists(revenue_path):
        await callback.message.answer("💰 Данные о revenue пока отсутствуют.")
        await callback.answer()
        return

    try:
        with open(revenue_path, "r", encoding="utf-8") as f:
            data = _json.load(f)
        mrr = data.get("current_mrr", 0)
        target = data.get("target_mrr", 2500)
        gap = target - mrr
        channels = data.get("channels", {})

        lines = [f"💰 Revenue Summary\n"]
        lines.append(f"MRR: ${mrr:.0f} / ${target:.0f} (gap: ${gap:.0f})")
        if channels:
            lines.append("")
            for ch_name, ch_data in channels.items():
                ch_mrr = ch_data.get("mrr", 0)
                lines.append(f"  {ch_name}: ${ch_mrr:.0f}")

        await callback.message.answer("\n".join(lines))
    except Exception as e:
        await callback.message.answer(f"💰 Ошибка чтения revenue: {e}")
    await callback.answer()
