"""CEO Telegram command handlers (/start, /help, /review, /report, /status, /delegate, /content, /linkedin, /gallery)."""

import logging
import os

from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from ...telegram.bridge import AgentBridge
from ...telegram.formatters import format_for_telegram
from ...telegram.handlers.commands import run_with_typing
from ...activity_tracker import get_all_statuses, get_agent_task_count, AGENT_NAMES

logger = logging.getLogger(__name__)
router = Router()

VALID_AGENTS = {"accountant", "automator", "smm", "manager", "designer", "cpo"}


@router.message(CommandStart())
async def cmd_start(message: Message):
    from ..keyboards import main_reply_keyboard
    await message.answer(
        "Алексей Воронов — CEO Zinin Corp\n\n"
        "Добрый день, Тим. Я Алексей, генеральный директор корпорации.\n\n"
        "Используйте кнопки внизу или команды:\n"
        "/review — Стратегический обзор\n"
        "/report — Полный отчёт корпорации\n"
        "/status — Статус агентов\n"
        "/analytics — Аналитика API и агентов\n"
        "/task — Задачи\n"
        "/content <тема> — Пост для LinkedIn\n"
        "/gallery — Галерея изображений\n"
        "/help — Справка\n\n"
        "Можете написать любой вопрос или отправить голосовое сообщение.",
        reply_markup=main_reply_keyboard(),
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
        "designer": "Райан (Designer)",
        "cpo": "Софи (CPO)",
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
            "Агенты: accountant, automator, smm, designer, cpo\n\n"
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

    from ...task_pool import create_task, suggest_assignee, format_task_summary, ESCALATION_THRESHOLD
    task = create_task(title, source="telegram", assigned_by="tim")

    suggestion = suggest_assignee(task.tags)
    text_parts = [format_task_summary(task)]

    # Escalation: if no good match, show escalation keyboard
    if not suggestion or suggestion[0][1] < ESCALATION_THRESHOLD:
        max_conf = suggestion[0][1] if suggestion else 0
        text_parts.append(f"\n⚠️ Нет подходящего агента (max confidence: {max_conf:.0%})")
        from ..keyboards import escalation_keyboard
        await message.answer(
            "\n".join(text_parts),
            reply_markup=escalation_keyboard(task.id),
            parse_mode="HTML",
        )
    else:
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


@router.message(Command("route"))
async def cmd_route(message: Message):
    """Explicit agent routing: /route cto check API status."""
    text = message.text or ""
    parts = text.split(maxsplit=2)

    if len(parts) < 3:
        await message.answer(
            "Формат: /route <агент> <задача>\n"
            "Агенты: accountant (CFO), automator (CTO), smm, designer, cpo\n\n"
            "Пример: /route cto Проверь статус API"
        )
        return

    agent_alias = parts[1].lower()
    task_text = parts[2]

    # Resolve alias to agent key
    alias_map = {
        "ceo": "manager", "алексей": "manager", "manager": "manager",
        "cfo": "accountant", "маттиас": "accountant", "accountant": "accountant",
        "cto": "automator", "мартин": "automator", "automator": "automator",
        "smm": "smm", "юки": "smm",
        "designer": "designer", "райан": "designer",
        "cpo": "cpo", "софи": "cpo",
    }
    agent_key = alias_map.get(agent_alias)

    if not agent_key:
        await message.answer(
            f"Неизвестный агент: {agent_alias}\n"
            f"Доступные: ceo, cfo, cto, smm, designer, cpo"
        )
        return

    await run_with_typing(
        message,
        AgentBridge.send_to_agent(task_text, agent_name=agent_key, bot=message.bot, chat_id=message.chat.id),
        f"📨 Маршрутизация → {agent_key}... (30–60 сек)",
    )


@router.message(Command("analytics"))
async def cmd_analytics(message: Message):
    """Show analytics report — no LLM call, instant data aggregation."""
    from ...analytics import format_analytics_report
    text = message.text or ""
    parts = text.split(maxsplit=1)
    hours = 24
    if len(parts) > 1:
        try:
            hours = int(parts[1])
            hours = max(1, min(hours, 168))
        except ValueError:
            pass

    report = format_analytics_report(hours)
    if len(report) > 4000:
        report = report[:4000] + "..."
    await message.answer(report)


@router.message(Command("calendar"))
async def cmd_calendar(message: Message):
    """Show content calendar — weekly plan + overdue items."""
    from ...content_calendar import format_week_plan, format_today_plan, get_today, seed_sborka_launch
    today_entries = get_today()
    if not today_entries:
        # Check if calendar is empty
        week_text = format_week_plan()
        if "Нет записей" in week_text:
            await message.answer(
                "📅 Контент-календарь пуст.\n\n"
                "Заполнить план запуска СБОРКИ (5 постов, 14-18 февраля)?",
            )
            return

    today_text = format_today_plan()
    week_text = format_week_plan()
    text = f"{today_text}\n\n{'─' * 30}\n\n{week_text}"
    if len(text) > 4000:
        text = text[:4000] + "..."
    await message.answer(text, parse_mode="HTML")


@router.message(Command("gallery"))
async def cmd_gallery(message: Message):
    """Show image gallery with approve/reject controls."""
    from ...image_registry import get_gallery, STATUS_PENDING
    from ..keyboards import gallery_keyboard

    # Parse page from args
    args = (message.text or "").split()
    page = 0
    if len(args) > 1:
        try:
            page = max(0, int(args[1]) - 1)
        except ValueError:
            pass

    gallery = get_gallery(limit=5, page=page)
    images = gallery["images"]
    total = gallery["total"]
    pages = gallery["pages"]

    if not images:
        await message.answer("🖼 Галерея пуста — нет изображений.")
        return

    pending = sum(1 for img in images if img.get("status") == STATUS_PENDING)
    header = f"🖼 Галерея ({total} изобр., стр. {page + 1}/{pages})"
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

    # Send text + keyboard for first pending image
    first_pending = next((img for img in images if img.get("status") == STATUS_PENDING), None)
    kb = gallery_keyboard(
        image_id=first_pending["id"] if first_pending else "",
        page=page,
        pages=pages,
    )
    await message.answer("\n".join(lines), reply_markup=kb, parse_mode="HTML")

    # Send actual image file for first pending
    if first_pending:
        img_path = first_pending.get("path", "")
        if img_path and os.path.exists(img_path):
            from aiogram.types import FSInputFile
            await message.answer_photo(FSInputFile(img_path))


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Алексей Воронов — CEO Zinin Corp\n\n"
        "Текст → Алексей отвечает как CEO (с авто-делегацией)\n\n"
        "Стратегия:\n"
        "/review — Стратегический обзор (Маттиас + Мартин → Алексей)\n"
        "/report — Полный отчёт (все агенты включая Юки → синтез)\n"
        "/status — Статус агентов (мгновенно)\n"
        "/analytics [часы] — Аналитика API и агентов (мгновенно)\n\n"
        "Контент (Юки SMM):\n"
        "/content <тема> — Юки генерирует пост для LinkedIn\n"
        "/linkedin — Статус LinkedIn-интеграции\n"
        "/calendar — Контент-календарь (план на неделю)\n\n"
        "Задачи (Task Pool v2.3):\n"
        "/task <заголовок> — Создать задачу (auto-tag + suggest)\n"
        "/task — Меню Task Pool\n"
        "/tasks — Сводка всех задач\n\n"
        "Дизайн (Райан):\n"
        "/gallery — Галерея изображений (approve/reject/forward)\n\n"
        "Делегация:\n"
        "/delegate <агент> <задача> — Прямая делегация\n"
        "/route <агент> <задача> — Маршрутизация к агенту (алиасы: ceo, cfo, cto, smm, designer, cpo)\n"
        "/help — Эта справка\n\n"
        "Агенты: accountant (Маттиас), automator (Мартин), smm (Юки), designer (Райан), cpo (Софи)"
    )
