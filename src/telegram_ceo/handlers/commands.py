"""CEO Telegram command handlers (/start, /help, /review, /report, /status, /delegate, /content, /linkedin)."""

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
        "/task <заголовок> — Создать задачу\n"
        "/tasks — Сводка задач\n"
        "/content <тема> — Юки готовит пост для LinkedIn\n"
        "/linkedin — Статус LinkedIn от Юки\n"
        "/delegate <агент> <задача> — Делегировать задачу\n"
        "/help — Справка\n\n"
        "Можете написать любой вопрос — я отвечу как CEO "
        "и при необходимости привлеку специалистов (включая Юки для контента).",
    )


@router.message(Command("review"))
async def cmd_review(message: Message):
    await run_with_typing(
        message,
        AgentBridge.run_strategic_review(bot=message.bot, chat_id=message.chat.id),
        "📋 Готовлю стратегический обзор... (60–120 сек)",
    )


@router.message(Command("report"))
async def cmd_report(message: Message):
    await run_with_typing(
        message,
        AgentBridge.run_corporation_report(bot=message.bot, chat_id=message.chat.id),
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


@router.message(Command("content"))
async def cmd_content(message: Message):
    """Ask Yuki to generate a LinkedIn post: /content AI-агенты в бизнесе."""
    text = message.text or ""
    parts = text.split(maxsplit=1)
    topic = parts[1] if len(parts) > 1 else ""

    if not topic:
        await message.answer(
            "Формат: /content <тема поста>\n\n"
            "Пример: /content AI-агенты в бизнесе\n"
            "Пример: /content карьерный рост в IT"
        )
        return

    await run_with_typing(
        message,
        AgentBridge.run_generate_post(topic=topic),
        f"✍️ Юки готовит пост на тему: {topic[:50]}... (30–60 сек)",
    )


@router.message(Command("linkedin"))
async def cmd_linkedin(message: Message):
    """Check LinkedIn integration status via Yuki."""
    await run_with_typing(
        message,
        AgentBridge.run_linkedin_status(),
        "📱 Юки проверяет статус LinkedIn... (20–40 сек)",
    )


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
        AgentBridge.send_to_agent(task_text, agent_name=agent_key, bot=message.bot, chat_id=message.chat.id),
        f"📨 Делегирую задачу → {agent_key}... (30–60 сек)",
    )


@router.message(Command("test"))
async def cmd_test(message: Message):
    """Quick diagnostic — tests bridge without LLM."""
    import time
    lines = ["Диагностика CEO бота:\n"]

    # Test 1: Bridge import
    t0 = time.time()
    try:
        from ...telegram.bridge import AgentBridge
        lines.append(f"1. Bridge import: OK ({time.time()-t0:.1f}s)")
    except Exception as e:
        lines.append(f"1. Bridge import: FAIL ({e})")

    # Test 2: Corp creation
    t0 = time.time()
    try:
        corp = AgentBridge._get_corp()
        lines.append(f"2. Corporation: ready={corp.is_ready} ({time.time()-t0:.1f}s)")
        lines.append(f"   Manager: {corp.manager is not None}")
        lines.append(f"   SMM (Yuki): {corp.smm is not None}")
    except Exception as e:
        lines.append(f"2. Corporation: FAIL ({e})")

    # Test 3: Activity tracker
    try:
        statuses = get_all_statuses()
        lines.append(f"3. Activity tracker: {len(statuses)} agents")
    except Exception as e:
        lines.append(f"3. Activity tracker: FAIL ({e})")

    lines.append(f"\nВсё ОК — можно писать текстовые сообщения.")
    await message.answer("\n".join(lines))


@router.message(Command("task"))
async def cmd_task(message: Message):
    """Create a task or show task menu: /task <title> or /task."""
    text = message.text or ""
    parts = text.split(maxsplit=1)
    title = parts[1] if len(parts) > 1 else ""

    if not title:
        from ..keyboards import task_menu_keyboard
        from ...task_pool import format_pool_summary
        summary = format_pool_summary()
        await message.answer(summary, reply_markup=task_menu_keyboard(), parse_mode="HTML")
        return

    from ...task_pool import create_task, suggest_assignee, format_task_summary
    task = create_task(title, source="telegram", assigned_by="tim")

    suggestion = suggest_assignee(task.tags)
    text_parts = [format_task_summary(task)]
    if suggestion:
        best_agent, confidence = suggestion[0]
        text_parts.append(f"\n💡 Рекомендация: <b>{best_agent}</b> ({confidence:.0%})")

    from ..keyboards import task_detail_keyboard
    await message.answer(
        "\n".join(text_parts),
        reply_markup=task_detail_keyboard(task.id, task.status.value),
        parse_mode="HTML",
    )


@router.message(Command("tasks"))
async def cmd_tasks(message: Message):
    """Show task pool summary with all active tasks."""
    from ...task_pool import get_all_tasks, format_task_summary, format_pool_summary, TaskStatus

    tasks = get_all_tasks()
    if not tasks:
        await message.answer("📋 Task Pool пуст. Создайте задачу: /task <заголовок>")
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

    from ..keyboards import task_menu_keyboard
    await message.answer(text, reply_markup=task_menu_keyboard(), parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Алексей Воронов — CEO Zinin Corp\n\n"
        "Текст → Алексей отвечает как CEO (с авто-делегацией)\n\n"
        "Стратегия:\n"
        "/review — Стратегический обзор (Маттиас + Мартин → Алексей)\n"
        "/report — Полный отчёт (все агенты включая Юки → синтез)\n"
        "/status — Статус агентов (мгновенно)\n\n"
        "Контент (Юки SMM):\n"
        "/content <тема> — Юки генерирует пост для LinkedIn\n"
        "/linkedin — Статус LinkedIn-интеграции\n\n"
        "Задачи (Task Pool v2.3):\n"
        "/task <заголовок> — Создать задачу (auto-tag + suggest)\n"
        "/task — Меню Task Pool\n"
        "/tasks — Сводка всех задач\n\n"
        "Делегация:\n"
        "/delegate <агент> <задача> — Прямая делегация\n"
        "/help — Эта справка\n\n"
        "Агенты: accountant (Маттиас), automator (Мартин), smm (Юки)"
    )
