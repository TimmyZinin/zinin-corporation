"""CEO Telegram command handlers (/start, /help, /review, /report, /status, /delegate)."""

import logging

from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from ...telegram.bridge import AgentBridge
from ...telegram.formatters import format_for_telegram
from ...telegram.handlers.commands import run_with_typing
from ...activity_tracker import get_all_statuses, get_agent_task_count, AGENT_NAMES

logger = logging.getLogger(__name__)
router = Router()

VALID_AGENTS = {"accountant", "automator", "smm", "manager"}


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Алексей Воронов — CEO Zinin Corp\n\n"
        "Добрый день, Тим. Я Алексей, генеральный директор корпорации.\n\n"
        "Команды:\n"
        "/review — Стратегический обзор\n"
        "/report — Полный отчёт корпорации\n"
        "/status — Статус агентов\n"
        "/delegate <агент> <задача> — Делегировать задачу\n"
        "/help — Справка\n\n"
        "Можете написать любой вопрос — я отвечу как CEO "
        "и при необходимости привлеку специалистов.",
    )


@router.message(Command("review"))
async def cmd_review(message: Message):
    await run_with_typing(
        message,
        AgentBridge.run_strategic_review(),
        "📋 Готовлю стратегический обзор... (60–120 сек)",
    )


@router.message(Command("report"))
async def cmd_report(message: Message):
    await run_with_typing(
        message,
        AgentBridge.run_corporation_report(),
        "📊 Готовлю полный отчёт корпорации... (90–180 сек)",
    )


@router.message(Command("status"))
async def cmd_status(message: Message):
    """Show agent statuses — no LLM call, instant response."""
    statuses = get_all_statuses()
    agent_labels = {
        "manager": "Алексей (CEO)",
        "accountant": "Маттиас (CFO)",
        "automator": "Мартин (CTO)",
        "smm": "Юки (SMM)",
    }

    lines = ["Статус агентов Zinin Corp:\n"]
    for key, label in agent_labels.items():
        s = statuses.get(key, {})
        status = s.get("status", "idle")
        tasks_24h = get_agent_task_count(key, hours=24)
        queued = s.get("queued_tasks", 0)

        status_emoji = {"working": "🟢", "idle": "⚪", "queued": "🟡"}.get(status, "⚪")
        line = f"{status_emoji} {label} — {status}"
        if tasks_24h:
            line += f", задач за 24ч: {tasks_24h}"
        if queued:
            line += f", в очереди: {queued}"
        lines.append(line)

    await message.answer("\n".join(lines))


@router.message(Command("delegate"))
async def cmd_delegate(message: Message):
    """Delegate a task to a specific agent: /delegate accountant бюджет на Q1."""
    text = message.text or ""
    parts = text.split(maxsplit=2)

    if len(parts) < 3:
        await message.answer(
            "Формат: /delegate <агент> <задача>\n"
            "Агенты: accountant, automator, smm\n\n"
            "Пример: /delegate accountant Подготовь бюджет на Q1"
        )
        return

    agent_key = parts[1].lower()
    task_text = parts[2]

    if agent_key not in VALID_AGENTS:
        await message.answer(
            f"Неизвестный агент: {agent_key}\n"
            f"Доступные: {', '.join(sorted(VALID_AGENTS - {'manager'}))}"
        )
        return

    await run_with_typing(
        message,
        AgentBridge.send_to_agent(task_text, agent_name=agent_key),
        f"📨 Делегирую задачу → {agent_key}... (30–60 сек)",
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Алексей Воронов — CEO Zinin Corp\n\n"
        "Текст → Алексей отвечает как CEO (с авто-делегацией)\n\n"
        "/review — Стратегический обзор (Маттиас + Мартин → Алексей)\n"
        "/report — Полный отчёт (все агенты → синтез)\n"
        "/status — Статус агентов (мгновенно)\n"
        "/delegate <агент> <задача> — Прямая делегация\n"
        "/help — Эта справка\n\n"
        "Агенты: accountant (Маттиас), automator (Мартин), smm (Юки)"
    )
