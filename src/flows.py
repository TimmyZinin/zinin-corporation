"""
🏢 Zinin Corp — Corporation Flow
CrewAI Flows orchestration layer for the multi-agent system.

Replaces direct Crew instantiation with a structured Flow[CorporationState].
Each flow run has typed Pydantic state, deterministic routing, and optional persistence.
"""

import logging
from typing import Optional
from pydantic import BaseModel, Field
from crewai import Crew, Task, Process
from crewai.flow.flow import Flow, start, listen, router

from .agents import (
    create_manager_agent,
    create_accountant_agent,
    create_smm_agent,
    create_automator_agent,
    create_designer_agent,
)
from .activity_tracker import (
    log_task_start,
    log_task_end,
    log_communication,
    log_communication_end,
)
from .crew import (
    EMBEDDER_CONFIG,
    KNOWLEDGE_SOURCES,
    AGENT_LABELS,
    EXPECTED_OUTPUT,
    EXPECTED_OUTPUT_SHORT,
    TASK_WRAPPER,
    TASK_WRAPPER_AGENT,
    create_task,
    _manager_guardrail,
    _specialist_guardrail,
    _send_progress,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# Pydantic State Models
# ──────────────────────────────────────────────────────────

class AgentResult(BaseModel):
    """Result from a single agent run."""
    agent_name: str = ""
    success: bool = True
    output: str = ""
    error: str = ""


class CorporationState(BaseModel):
    """Shared state for all flow runs."""
    # Input
    task_description: str = ""
    agent_name: str = "manager"
    use_memory: bool = True
    flow_type: str = ""  # "single", "delegated", "strategic_review", "full_report"

    # Routing
    delegation_target: str = ""  # specialist agent key for auto-delegation

    # Agent results
    specialist_result: AgentResult = Field(default_factory=AgentResult)
    accountant_result: AgentResult = Field(default_factory=AgentResult)
    automator_result: AgentResult = Field(default_factory=AgentResult)
    smm_result: AgentResult = Field(default_factory=AgentResult)
    manager_result: AgentResult = Field(default_factory=AgentResult)

    # Final output
    final_output: str = ""


# ──────────────────────────────────────────────────────────
# Agent Pool (shared across flow instances, lazy-initialized)
# ──────────────────────────────────────────────────────────

class _AgentPool:
    """Lazy-initialized agent pool. Created once, reused by all flow runs."""

    def __init__(self):
        self._agents = {}
        self._initialized = False

    def initialize(self) -> bool:
        import os
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            logger.error("OPENROUTER_API_KEY not set")
            return False

        self._agents["manager"] = create_manager_agent()
        self._agents["accountant"] = create_accountant_agent()
        self._agents["automator"] = create_automator_agent()
        self._agents["smm"] = create_smm_agent()
        self._agents["designer"] = create_designer_agent()

        core_ok = all(self._agents.get(k) for k in ("manager", "accountant", "automator"))
        if not core_ok:
            logger.error("Core agents failed to initialize")
            return False

        if not self._agents.get("smm"):
            logger.warning("SMM agent (Юки) failed to init — continuing without her")
        if not self._agents.get("designer"):
            logger.warning("Designer agent (Райан) failed to init — continuing without him")

        self._initialized = True
        logger.info("Agent pool initialized")
        return True

    @property
    def is_ready(self) -> bool:
        return self._initialized

    def get(self, name: str):
        return self._agents.get(name)

    def all_agents(self) -> list:
        return [a for a in self._agents.values() if a is not None]


_pool = _AgentPool()


def get_agent_pool() -> _AgentPool:
    """Get or initialize the global agent pool."""
    if not _pool.is_ready:
        _pool.initialize()
    return _pool


# ──────────────────────────────────────────────────────────
# Helper: run a single agent as Crew (preserves existing logic)
# ──────────────────────────────────────────────────────────

def _run_agent_crew(agent, task_description: str, agent_name: str = "",
                    use_memory: bool = True, guardrail=None) -> str:
    """Run a single agent task with memory fallback. Returns result string.
    Extracted from AICorporation._run_agent for reuse in flows.
    """
    # Reset agent state
    agent.agent_executor = None
    agent.tools_results = []
    if hasattr(agent, '_times_executed'):
        agent._times_executed = 0

    wrapper = TASK_WRAPPER if agent_name == "manager" else TASK_WRAPPER_AGENT
    full_description = f"{task_description}{wrapper}"
    output_fmt = EXPECTED_OUTPUT_SHORT if agent_name in ("accountant", "automator") else EXPECTED_OUTPUT

    task = create_task(
        description=full_description,
        expected_output=output_fmt,
        agent=agent,
        guardrail=guardrail,
    )

    if not use_memory:
        crew = Crew(
            agents=[agent], tasks=[task],
            process=Process.sequential, verbose=True, memory=False,
        )
        return str(crew.kickoff())

    try:
        crew_kwargs = {
            "agents": [agent], "tasks": [task],
            "process": Process.sequential, "verbose": True,
            "memory": True, "embedder": EMBEDDER_CONFIG,
        }
        if KNOWLEDGE_SOURCES:
            crew_kwargs["knowledge_sources"] = KNOWLEDGE_SOURCES
        crew = Crew(**crew_kwargs)
        return str(crew.kickoff())
    except Exception as e:
        logger.warning(f"_run_agent_crew({agent_name}) memory failed: {e}, retrying without memory")
        task_retry = create_task(
            description=full_description,
            expected_output=output_fmt,
            agent=agent,
        )
        crew_fallback = Crew(
            agents=[agent], tasks=[task_retry],
            process=Process.sequential, verbose=True, memory=False,
        )
        result = crew_fallback.kickoff()
        return f"⚠️ _(восстановлено)_\n\n{result}"


# ──────────────────────────────────────────────────────────
# Delegation detection (extracted from AICorporation)
# ──────────────────────────────────────────────────────────

_DELEGATION_RULES = [
    {"agent_key": "smm", "keywords": [
        "контент", "пост", "публикац", "linkedin", "копирайт",
        "smm", "соцсет", "социальн", "контент-план",
    ]},
    {"agent_key": "accountant", "keywords": [
        "бюджет", "финанс", "p&l", "расход", "доход", "прибыл",
        "подписк", "roi", "портфел", "баланс", "выписк",
    ]},
    {"agent_key": "automator", "keywords": [
        "деплой", "api", "webhook", "интеграц", "мониторинг",
        "сервер", "docker", "railway", "техническ",
        "здоровье api", "health check", "статус api", "api status",
        "промпт агент", "создай агент", "новый агент",
        "улучшен", "proposal", "предложен", "improvement",
        "модельный аудит", "model audit", "саморефлекс",
    ]},
    {"agent_key": "designer", "keywords": [
        "дизайн", "картинк", "изображен", "визуал", "инфографик",
        "баннер", "лого", "график", "диаграмм", "chart",
        "image", "видео", "video", "обложк",
    ]},
]

_DESIGNER_PRIORITY_KEYWORDS = [
    "картинк", "изображен", "баннер", "инфографик", "визуал",
    "лого", "диаграмм", "обложк", "image", "chart",
    "видео", "video", "дизайн",
]


def detect_delegation(text: str) -> Optional[str]:
    """Detect if task should be auto-delegated. Returns agent_key or None."""
    text_lower = text.lower()
    for kw in _DESIGNER_PRIORITY_KEYWORDS:
        if kw in text_lower:
            return "designer"
    for rule in _DELEGATION_RULES:
        for kw in rule["keywords"]:
            if kw in text_lower:
                return rule["agent_key"]
    return None


# ──────────────────────────────────────────────────────────
# CorporationFlow — main Flow class
# ──────────────────────────────────────────────────────────

class CorporationFlow(Flow[CorporationState]):
    """Flow-based orchestration for Zinin Corp.

    Flow types:
      - "single": run one agent directly
      - "delegated": specialist → CEO synthesis
      - "strategic_review": accountant + automator [+ smm] → CEO
      - "full_report": accountant + automator [+ smm] → CEO (comprehensive)
    """

    # ── Step 1: classify task ──
    @start()
    def classify_task(self):
        """Determine flow type and routing."""
        pool = get_agent_pool()
        if not pool.is_ready:
            self.state.final_output = "❌ Zinin Corp не инициализирована. Проверьте API ключи."
            self.state.flow_type = "error"
            return "error"

        ft = self.state.flow_type
        if ft in ("strategic_review", "full_report"):
            return ft

        # Single-agent or manager with delegation
        if self.state.agent_name == "manager":
            target = detect_delegation(self.state.task_description)
            if target and pool.get(target):
                self.state.delegation_target = target
                self.state.flow_type = "delegated"
                return "delegated"

        self.state.flow_type = "single"
        return "single"

    # ── Step 2: route ──
    @router(classify_task)
    def route(self):
        return self.state.flow_type

    # ── Single agent execution ──
    @listen("single")
    def run_single_agent(self):
        """Run a single agent task directly."""
        pool = get_agent_pool()
        agent = pool.get(self.state.agent_name) or pool.get("manager")
        agent_name = self.state.agent_name

        short_desc = self.state.task_description.strip()[:100].split("\n")[0]
        if "---\nНовое сообщение от Тима:" in self.state.task_description:
            short_desc = self.state.task_description.split("---\nНовое сообщение от Тима:")[-1].strip()[:100].split("\n")[0]

        log_task_start(agent_name, short_desc)
        grl = _manager_guardrail if agent_name == "manager" else _specialist_guardrail

        try:
            result = _run_agent_crew(
                agent, self.state.task_description, agent_name,
                use_memory=self.state.use_memory, guardrail=grl,
            )
            log_task_end(agent_name, short_desc, success=True)
            self.state.final_output = result
        except Exception as e:
            logger.error(f"Single agent failed for {agent_name}: {e}", exc_info=True)
            log_task_end(agent_name, short_desc, success=False)
            self.state.final_output = f"❌ Ошибка выполнения: {e}"

        return self.state.final_output

    # ── Delegated: specialist → CEO ──
    @listen("delegated")
    def run_specialist(self):
        """Run specialist agent, then pass result to CEO for synthesis."""
        pool = get_agent_pool()
        specialist_key = self.state.delegation_target
        specialist_agent = pool.get(specialist_key)

        short_desc = self.state.task_description.strip()[:100].split("\n")[0]
        if "---\nНовое сообщение от Тима:" in self.state.task_description:
            short_desc = self.state.task_description.split("---\nНовое сообщение от Тима:")[-1].strip()[:100].split("\n")[0]

        spec_label = AGENT_LABELS.get(specialist_key, specialist_key)
        logger.info(f"Auto-delegation: manager → {specialist_key}")
        _send_progress(f"{spec_label} готовит данные...")

        log_task_start(specialist_key, short_desc)
        try:
            specialist_result = _run_agent_crew(
                specialist_agent, self.state.task_description, specialist_key,
                use_memory=self.state.use_memory, guardrail=_specialist_guardrail,
            )
            log_task_end(specialist_key, short_desc, success=True)
            self.state.specialist_result = AgentResult(
                agent_name=specialist_key, success=True, output=specialist_result,
            )
        except Exception as e:
            logger.error(f"Specialist {specialist_key} failed: {e}")
            log_task_end(specialist_key, short_desc, success=False)
            self.state.specialist_result = AgentResult(
                agent_name=specialist_key, success=False, error=str(e),
            )

        # CEO synthesis
        _send_progress(f"{spec_label} → 👑 Алексей: передача данных")
        manager_agent = pool.get("manager")
        spec_output = self.state.specialist_result.output or f"❌ Ошибка: {self.state.specialist_result.error}"
        enriched = (
            f"{self.state.task_description}\n\n"
            f"--- Результат от специалиста ({specialist_key}) ---\n"
            f"{spec_output}\n"
            f"--- Конец результата ---\n\n"
            f"НИКОГДА НЕ ПРЕДСТАВЛЯЙСЯ. СРАЗУ к делу.\n"
            f"Добавь свой краткий комментарий CEO к результату выше. "
            f"Не повторяй весь результат — дай стратегическую оценку."
        )

        log_task_start("manager", short_desc)
        try:
            ceo_result = _run_agent_crew(
                manager_agent, enriched, "manager",
                use_memory=self.state.use_memory, guardrail=_manager_guardrail,
            )
            log_task_end("manager", short_desc, success=True)
            self.state.final_output = ceo_result
        except Exception as e:
            logger.error(f"CEO synthesis failed: {e}")
            log_task_end("manager", short_desc, success=False)
            self.state.final_output = spec_output

        return self.state.final_output

    # ── Strategic review: accountant + automator [+ smm] → CEO ──
    @listen("strategic_review")
    def run_strategic_review(self):
        """Multi-agent strategic review."""
        pool = get_agent_pool()
        has_smm = pool.get("smm") is not None

        log_task_start("accountant", "Финансовая сводка (стратобзор)")
        log_task_start("automator", "Проверка систем (стратобзор)")
        if has_smm:
            log_task_start("smm", "Контент-сводка (стратобзор)")

        _send_progress(
            "📋 Стратегический обзор запущен\n"
            "🏦 Маттиас готовит финансовую сводку...\n"
            "⚙️ Мартин проверяет системы..."
            + ("\n📱 Юки готовит контент-сводку..." if has_smm else "")
        )

        # Build multi-agent crew with context passing
        agents = []
        tasks = []

        accountant = pool.get("accountant")
        automator = pool.get("automator")
        for a in [accountant, automator]:
            a.agent_executor = None
            a.tools_results = []
            if hasattr(a, '_times_executed'):
                a._times_executed = 0

        task_finance = create_task(
            description=(
                "Подготовь краткую финансовую сводку:\n"
                "1. Используй full_portfolio для общей картины\n"
                "2. Используй openrouter_usage, elevenlabs_usage, openai_usage для расходов на AI\n"
                "3. Используй tribute_revenue для доходов\n"
                "Дай сводку: активы, доходы, расходы на AI."
                + TASK_WRAPPER
            ),
            expected_output="Краткая финансовая сводка с реальными данными из инструментов.",
            agent=accountant,
        )
        tasks.append(task_finance)
        agents.append(accountant)

        task_health = create_task(
            description=(
                "Проверь здоровье систем:\n"
                "1. Вызови System Health Checker с action='status'\n"
                "2. Вызови Integration Manager с action='list'\n"
                "Дай сводку: что работает, что нет."
                + TASK_WRAPPER
            ),
            expected_output="Краткий отчёт о состоянии систем и интеграций.",
            agent=automator,
        )
        tasks.append(task_health)
        agents.append(automator)

        if has_smm:
            smm = pool.get("smm")
            smm.agent_executor = None
            task_smm = create_task(
                description=(
                    "Подготовь краткую сводку по контенту и SMM:\n"
                    "1. Используй Yuki Memory с action='get_stats' для статистики генераций\n"
                    "2. Используй LinkedIn Publisher с action='status' для статуса LinkedIn\n"
                    "Дай сводку: что опубликовано, что запланировано, статус LinkedIn."
                    + TASK_WRAPPER
                ),
                expected_output="Краткая контент-сводка с данными из инструментов.",
                agent=smm,
            )
            tasks.append(task_smm)
            agents.append(smm)

        # CEO synthesis
        context_agents = "Маттиаса, Мартина" + (" и Юки" if has_smm else "")
        manager = pool.get("manager")
        manager.agent_executor = None
        task_strategy = create_task(
            description=(
                f"На основе данных от {context_agents} "
                "подготовь стратегический обзор:\n"
                "- Статус каждого проекта\n"
                "- Приоритеты на неделю\n"
                "- Конкретные задачи для каждого агента\n"
                "- Риски и рекомендации\n\n"
                "⛔ НЕ ПИШИ 'запускаю сбор данных'. "
                f"Данные от {context_agents} уже ПОЛУЧЕНЫ. "
                "Проанализируй их и дай КОНКРЕТНЫЙ стратегический обзор."
                + TASK_WRAPPER
            ),
            expected_output=EXPECTED_OUTPUT,
            agent=manager,
            context=tasks,
            guardrail=_manager_guardrail,
        )
        tasks.append(task_strategy)
        agents.append(manager)

        # Progress messages
        if has_smm:
            step_msgs = [
                "✅ 🏦 Маттиас: финансовая сводка готова\n⚙️ Мартин работает...",
                "✅ ⚙️ Мартин: техотчёт готов\n📱 Юки работает...",
                "✅ 📱 Юки: контент-сводка готова\n👑 Алексей анализирует...",
                None,
            ]
        else:
            step_msgs = [
                "✅ 🏦 Маттиас: финансовая сводка готова\n⚙️ Мартин работает...",
                "✅ ⚙️ Мартин: техотчёт готов\n👑 Алексей анализирует...",
                None,
            ]
        step_idx = [0]

        def _on_task_done(output):
            idx = step_idx[0]
            step_idx[0] += 1
            if idx < len(step_msgs) and step_msgs[idx]:
                _send_progress(step_msgs[idx])

        try:
            crew = Crew(
                agents=agents, tasks=tasks,
                process=Process.sequential, verbose=True,
                memory=False, task_callback=_on_task_done,
            )
            result = crew.kickoff()

            log_task_end("accountant", "Финансовая сводка (стратобзор)", success=True)
            log_task_end("automator", "Проверка систем (стратобзор)", success=True)
            log_communication("accountant", "manager", "Передача финансовых данных")
            log_communication("automator", "manager", "Передача техотчёта")
            if has_smm:
                log_task_end("smm", "Контент-сводка (стратобзор)", success=True)
                log_communication("smm", "manager", "Передача контент-сводки")
            log_task_start("manager", "Стратегический обзор (синтез)")
            log_task_end("manager", "Стратегический обзор (синтез)", success=True)
            log_communication_end("accountant")
            log_communication_end("automator")
            if has_smm:
                log_communication_end("smm")

            self.state.final_output = str(result)
        except Exception as e:
            logger.error(f"Strategic review failed: {e}", exc_info=True)
            log_task_end("accountant", "Финансовая сводка (стратобзор)", success=False)
            log_task_end("automator", "Проверка систем (стратобзор)", success=False)
            self.state.final_output = f"❌ Ошибка стратегического обзора: {e}"

        return self.state.final_output

    # ── Full corporation report ──
    @listen("full_report")
    def run_full_report(self):
        """Full weekly report: all agents → CEO synthesis."""
        pool = get_agent_pool()
        has_smm = pool.get("smm") is not None

        log_task_start("accountant", "Финансовый отчёт (полный)")
        log_task_start("automator", "Техотчёт (полный)")
        _send_progress(
            "📊 Полный отчёт корпорации запущен\n"
            "🏦 Маттиас готовит финансовый отчёт...\n"
            "⚙️ Мартин проверяет системы...\n"
            "📱 Юки готовит отчёт по контенту..."
        )

        agents = []
        tasks = []

        accountant = pool.get("accountant")
        automator = pool.get("automator")
        manager = pool.get("manager")
        for a in [accountant, automator, manager]:
            a.agent_executor = None
            a.tools_results = []
            if hasattr(a, '_times_executed'):
                a._times_executed = 0

        task_fin = create_task(
            description=(
                "Подготовь полный финансовый отчёт:\n"
                "1. full_portfolio — общая картина активов\n"
                "2. tribute_revenue — доходы от подписок\n"
                "3. openrouter_usage, elevenlabs_usage, openai_usage — расходы на AI\n"
                "Включи: активы, доходы, расходы на AI + Claude Code $200/мес."
                + TASK_WRAPPER
            ),
            expected_output="Полный финансовый отчёт с данными из инструментов.",
            agent=accountant,
        )
        tasks.append(task_fin)
        agents.append(accountant)

        task_tech = create_task(
            description=(
                "Проведи полную проверку систем:\n"
                "1. System Health Checker action='status'\n"
                "2. Integration Manager action='list'\n"
                "Включи: статус каждого сервиса, время отклика, ошибки."
                + TASK_WRAPPER
            ),
            expected_output="Полный технический отчёт с реальными данными.",
            agent=automator,
        )
        tasks.append(task_tech)
        agents.append(automator)

        if has_smm:
            smm = pool.get("smm")
            smm.agent_executor = None
            log_task_start("smm", "Отчёт по контенту (полный)")
            task_smm = create_task(
                description=(
                    "Подготовь отчёт по контенту:\n"
                    "1. Yuki Memory action='get_stats'\n"
                    "2. LinkedIn Publisher action='status'\n"
                    "Включи: кол-во генераций, публикаций, статус LinkedIn."
                    + TASK_WRAPPER
                ),
                expected_output="Краткий отчёт по контенту и LinkedIn.",
                agent=smm,
            )
            tasks.append(task_smm)
            agents.append(smm)

        task_ceo = create_task(
            description=(
                "На основе данных от всех агентов подготовь еженедельный отчёт для Тима:\n"
                "- Общее состояние корпорации\n"
                "- Финансовые показатели (от Маттиаса)\n"
                "- Техническое здоровье (от Мартина)\n"
                "- Контент и публикации (от Юки)\n"
                "- Приоритеты на следующую неделю\n"
                "- Конкретные задачи для каждого агента\n"
                "- Риски и рекомендации\n\n"
                "⛔ НЕ ПИШИ 'запускаю сбор данных'. "
                "Данные от агентов уже ПОЛУЧЕНЫ. "
                "Проанализируй их и дай КОНКРЕТНЫЙ отчёт."
                + TASK_WRAPPER
            ),
            expected_output="Полный еженедельный отчёт CEO. Минимум 400 слов.",
            agent=manager,
            context=tasks[:-1] if len(tasks) > 1 else tasks,
            guardrail=_manager_guardrail,
        )
        tasks.append(task_ceo)
        agents.append(manager)

        # Progress messages
        report_steps = [
            "✅ 🏦 Маттиас: финансовый отчёт готов\n⚙️ Мартин работает...",
            ("✅ ⚙️ Мартин: техотчёт готов\n📱 Юки работает..." if has_smm
             else "✅ ⚙️ Мартин: техотчёт готов\n👑 Алексей анализирует..."),
            ("✅ 📱 Юки: контент-отчёт готов\n👑 Алексей готовит синтез..." if has_smm
             else None),
            None,
        ]
        step_idx = [0]

        def _on_report_done(output):
            idx = step_idx[0]
            step_idx[0] += 1
            if idx < len(report_steps) and report_steps[idx]:
                _send_progress(report_steps[idx])

        try:
            crew = Crew(
                agents=agents, tasks=tasks,
                process=Process.sequential, verbose=True,
                memory=False, task_callback=_on_report_done,
            )
            result = crew.kickoff()

            log_task_end("accountant", "Финансовый отчёт (полный)", success=True)
            log_task_end("automator", "Техотчёт (полный)", success=True)
            if has_smm:
                log_task_end("smm", "Отчёт по контенту (полный)", success=True)
                log_communication("smm", "manager", "Передача контент-отчёта")

            log_communication("accountant", "manager", "Передача финотчёта")
            log_communication("automator", "manager", "Передача техотчёта")
            log_task_start("manager", "Еженедельный отчёт CEO (синтез)")
            log_task_end("manager", "Еженедельный отчёт CEO (синтез)", success=True)

            for agent_key in ["accountant", "automator", "smm"]:
                log_communication_end(agent_key)

            self.state.final_output = str(result)
        except Exception as e:
            logger.error(f"Full corporation report failed: {e}", exc_info=True)
            log_task_end("accountant", "Финансовый отчёт (полный)", success=False)
            log_task_end("automator", "Техотчёт (полный)", success=False)
            if has_smm:
                log_task_end("smm", "Отчёт по контенту (полный)", success=False)
            self.state.final_output = f"❌ Ошибка при формировании отчёта: {e}"

        return self.state.final_output

    # ── Error handler ──
    @listen("error")
    def handle_error(self):
        return self.state.final_output


# ──────────────────────────────────────────────────────────
# Public API — drop-in replacements for AICorporation methods
# ──────────────────────────────────────────────────────────

def run_task(task_description: str, agent_name: str = "manager",
             use_memory: bool = True) -> str:
    """Execute a task through the CorporationFlow. Drop-in for execute_task()."""
    flow = CorporationFlow()
    flow.kickoff(inputs={
        "task_description": task_description,
        "agent_name": agent_name,
        "use_memory": use_memory,
    })
    return flow.state.final_output


def run_strategic_review() -> str:
    """Run strategic review through the CorporationFlow."""
    flow = CorporationFlow()
    flow.kickoff(inputs={
        "flow_type": "strategic_review",
    })
    return flow.state.final_output


def run_full_report() -> str:
    """Run full corporation report through the CorporationFlow."""
    flow = CorporationFlow()
    flow.kickoff(inputs={
        "flow_type": "full_report",
    })
    return flow.state.final_output
