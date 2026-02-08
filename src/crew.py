"""
🏢 Zinin Corp — Crew Module
Orchestrates the multi-agent system
"""

import os
import logging
import yaml
from typing import Optional
from pydantic import BaseModel, Field
from crewai import Crew, Task, Process

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

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Progress callback — set by bridge to send Telegram progress messages
# ──────────────────────────────────────────────────────────
_progress_callback = None


def set_progress_callback(callback):
    """Set a callable(str) that sends progress messages to Telegram."""
    global _progress_callback
    _progress_callback = callback


def _send_progress(text: str):
    """Send a progress message if callback is set."""
    global _progress_callback
    if _progress_callback:
        try:
            _progress_callback(text)
        except Exception as e:
            logger.warning(f"Progress callback failed: {e}")


AGENT_LABELS = {
    "manager": "👑 Алексей",
    "accountant": "🏦 Маттиас",
    "automator": "⚙️ Мартин",
    "smm": "📱 Юки",
    "designer": "🎨 Райан",
}

# ──────────────────────────────────────────────────────────
# Memory configuration — ONNX embedder (free, no API keys)
# ──────────────────────────────────────────────────────────
EMBEDDER_CONFIG = {
    "provider": "onnx",
    "config": {},
}
os.environ.setdefault("CREWAI_STORAGE_DIR", "ai_corporation")


# ──────────────────────────────────────────────────────────
# Pydantic output models for structured responses
# ──────────────────────────────────────────────────────────
class FinancialReport(BaseModel):
    summary: str = Field(description="Краткая сводка финансового состояния")
    total_revenue_rub: float = Field(default=0, description="Общий доход в рублях")
    total_expenses_rub: float = Field(default=0, description="Общие расходы в рублях")
    mrr_rub: float = Field(default=0, description="Ежемесячный повторяющийся доход")
    api_costs_usd: float = Field(default=0, description="Расходы на API в долларах")
    recommendations: list[str] = Field(default_factory=list, description="Рекомендации")


class HealthCheckReport(BaseModel):
    overall_status: str = Field(description="Общий статус: healthy, degraded, critical")
    services_up: int = Field(default=0, description="Сервисов работает")
    services_down: int = Field(default=0, description="Сервисов не работает")
    details: list[str] = Field(default_factory=list, description="Детали по каждому сервису")
    recommendations: list[str] = Field(default_factory=list, description="Рекомендации")


# ──────────────────────────────────────────────────────────
# Task quality wrappers
# ──────────────────────────────────────────────────────────
EXPECTED_OUTPUT = (
    "Содержательный, конкретный и полный ответ на русском языке. "
    "Минимум 200 слов. "
    "Включай: конкретные шаги, рекомендации и примеры. "
    "НЕ останавливайся на приветствии — дай полный ответ по существу вопроса. "
    "⛔ НИКОГДА не выдумывай цифры, данные или факты. Если данных нет — скажи прямо."
)

TASK_WRAPPER_BASE = (
    "\n\nВАЖНО: Дай ПОЛНЫЙ содержательный ответ. "
    "НИКОГДА НЕ ПРЕДСТАВЛЯЙСЯ. Тим знает кто ты. СРАЗУ переходи к сути. "
    "Ответ должен содержать конкретные детали, шаги и рекомендации.\n\n"
    "⛔ ЗАПРЕТ НА ВЫДУМКИ: НИКОГДА не придумывай цифры, данные, метрики или факты. "
    "Используй ТОЛЬКО реальные данные из инструментов. "
    "Если данных нет — честно скажи: 'У меня нет данных по этому вопросу'. "
    "Ложь КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНА — Тим принимает решения на основе твоих ответов."
)

# Delegation instructions — ONLY for CEO (manager)
TASK_WRAPPER_DELEGATION = (
    "\n\n⚡ ДЕЛЕГИРОВАНИЕ: Если задача касается контента/SMM/публикаций — "
    "ВЫЗОВИ инструмент 'Delegate Task' с agent_name='smm'. "
    "Если задача про финансы/бюджет — ВЫЗОВИ 'Delegate Task' с agent_name='accountant'. "
    "Если задача про технику/API — ВЫЗОВИ 'Delegate Task' с agent_name='automator'. "
    "Если задача про дизайн/картинки/визуал/инфографику/видео — ВЫЗОВИ 'Delegate Task' с agent_name='designer'. "
    "НЕ пиши 'делегирую' или 'поручаю' в тексте — ИСПОЛЬЗУЙ ИНСТРУМЕНТ."
)

# Specialist reminder — for non-manager agents
TASK_WRAPPER_SPECIALIST = (
    "\n\n⚡ ИСПОЛЬЗУЙ СВОИ ИНСТРУМЕНТЫ. Ты — специалист. "
    "Не делегируй задачу другим — выполни её сам, вызывая свои инструменты. "
    "Верни конкретный результат с данными из инструментов."
)

# Combined wrappers
TASK_WRAPPER = TASK_WRAPPER_BASE + TASK_WRAPPER_DELEGATION  # for manager
TASK_WRAPPER_AGENT = TASK_WRAPPER_BASE + TASK_WRAPPER_SPECIALIST  # for specialists


def load_crew_config() -> dict:
    """Load crew configuration from YAML file"""
    paths = [
        "/app/crews/corporation.yaml",
        "crews/corporation.yaml",
    ]
    for path in paths:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
    return {}


def _manager_guardrail(task_output) -> tuple[bool, str]:
    """Guardrail for manager: reject too-short answers or missing delegation results."""
    try:
        text = task_output.raw if hasattr(task_output, 'raw') else str(task_output)
    except Exception:
        text = str(task_output) if task_output else ""
    # If agent wrote less than 100 chars, reject — force tool usage
    if len(text) < 100:
        return (False,
                "Ответ слишком короткий. Ты ОБЯЗАН вызвать инструмент Delegate Task "
                "для делегации задачи специалисту, получить результат и включить его в ответ. "
                "НЕ пиши 'делегирую' — ВЫЗОВИ Action: Delegate Task.")
    return (True, text)


def create_task(description: str, expected_output: str, agent, context=None,
                output_pydantic=None, tools=None, guardrail=None) -> Task:
    """Create a task for an agent"""
    kwargs = {
        "description": description,
        "expected_output": expected_output,
        "agent": agent,
    }
    if context:
        kwargs["context"] = context
    if output_pydantic:
        kwargs["output_pydantic"] = output_pydantic
    if tools:
        kwargs["tools"] = tools
    if guardrail:
        kwargs["guardrail"] = guardrail
        kwargs["guardrail_max_retries"] = 3
    return Task(**kwargs)


class AICorporation:
    """Main class for Zinin Corp crew management"""

    def __init__(self):
        self.config = load_crew_config()
        self.manager = None
        self.accountant = None
        self.smm = None
        self.automator = None
        self.designer = None
        self.crew = None
        self._initialized = False

    def initialize(self) -> bool:
        """Initialize all agents and crew"""
        try:
            # Check API key
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                logger.error("OPENROUTER_API_KEY not set")
                return False

            # Create agents
            self.manager = create_manager_agent()
            self.accountant = create_accountant_agent()
            self.smm = create_smm_agent()
            self.automator = create_automator_agent()
            self.designer = create_designer_agent()

            if not all([self.manager, self.accountant, self.automator]):
                logger.error("Core agents failed to initialize")
                return False

            # SMM agent is optional
            if not self.smm:
                logger.warning("SMM agent (Юки) failed to init — continuing without her")

            # Designer agent is optional
            if not self.designer:
                logger.warning("Designer agent (Райан) failed to init — continuing without him")

            # Create crew with memory enabled
            all_agents = [self.manager, self.accountant, self.automator]
            if self.smm:
                all_agents.append(self.smm)
            if self.designer:
                all_agents.append(self.designer)

            self.crew = Crew(
                agents=all_agents,
                process=Process.sequential,
                verbose=True,
                memory=False,
            )

            self._initialized = True
            logger.info("Zinin Corp initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Zinin Corp: {e}", exc_info=True)
            return False

    @property
    def is_ready(self) -> bool:
        """Check if the corporation is ready"""
        return self._initialized and self.crew is not None

    def _run_agent(self, agent, task_description: str, agent_name: str = "",
                    use_memory: bool = True, guardrail=None) -> str:
        """Run a single agent task with memory fallback. Returns result string."""
        # CRITICAL: Reset agent state to prevent accumulation between runs.
        # CrewAgentExecutor.messages never gets cleared between runs,
        # causing context to grow indefinitely (380K+ tokens).
        agent.agent_executor = None
        agent.tools_results = []
        if hasattr(agent, '_times_executed'):
            agent._times_executed = 0

        wrapper = TASK_WRAPPER if agent_name == "manager" else TASK_WRAPPER_AGENT
        full_description = f"{task_description}{wrapper}"
        task = create_task(
            description=full_description,
            expected_output=EXPECTED_OUTPUT,
            agent=agent,
            guardrail=guardrail,
        )
        if not use_memory:
            crew = Crew(
                agents=[agent],
                tasks=[task],
                process=Process.sequential,
                verbose=True,
                memory=False,
            )
            return str(crew.kickoff())
        try:
            crew = Crew(
                agents=[agent],
                tasks=[task],
                process=Process.sequential,
                verbose=True,
                memory=True,
                embedder=EMBEDDER_CONFIG,
            )
            return str(crew.kickoff())
        except Exception as e:
            logger.warning(f"_run_agent({agent_name}) memory failed: {e}, retrying without memory")
            task_retry = create_task(
                description=full_description,
                expected_output=EXPECTED_OUTPUT,
                agent=agent,
            )
            crew_fallback = Crew(
                agents=[agent],
                tasks=[task_retry],
                process=Process.sequential,
                verbose=True,
                memory=False,
            )
            result = crew_fallback.kickoff()
            return f"⚠️ _(восстановлено)_\n\n{result}"

    # ── Auto-delegation keywords ──────────────────────────
    _DELEGATION_RULES = [
        {
            "agent_key": "smm",
            "keywords": [
                "контент", "пост", "публикац", "linkedin", "копирайт",
                "smm", "соцсет", "социальн", "контент-план",
            ],
        },
        {
            "agent_key": "accountant",
            "keywords": [
                "бюджет", "финанс", "p&l", "расход", "доход", "прибыл",
                "подписк", "roi", "портфел", "баланс", "выписк",
            ],
        },
        {
            "agent_key": "automator",
            "keywords": [
                "деплой", "api", "webhook", "интеграц", "мониторинг",
                "сервер", "docker", "railway", "техническ",
                "здоровье api", "health check", "статус api", "api status",
                "промпт агент", "создай агент", "новый агент",
            ],
        },
        {
            "agent_key": "designer",
            "keywords": [
                "дизайн", "картинк", "изображен", "визуал", "инфографик",
                "баннер", "лого", "график", "диаграмм", "chart",
                "image", "видео", "video", "обложк",
            ],
        },
    ]

    # Keywords that force designer even if other agent keywords are present
    _DESIGNER_PRIORITY_KEYWORDS = [
        "картинк", "изображен", "баннер", "инфографик", "визуал",
        "лого", "диаграмм", "обложк", "image", "chart",
        "видео", "video", "дизайн",
    ]

    def _detect_delegation_need(self, text: str) -> Optional[dict]:
        """Detect if manager task should be auto-delegated to a specialist.

        Designer keywords take priority over SMM when both match,
        because 'создай изображение для поста' is a design task, not SMM.
        """
        text_lower = text.lower()

        # Check if designer priority keywords are present — they override SMM
        for kw in self._DESIGNER_PRIORITY_KEYWORDS:
            if kw in text_lower:
                return {"agent_key": "designer"}

        for rule in self._DELEGATION_RULES:
            for kw in rule["keywords"]:
                if kw in text_lower:
                    return {"agent_key": rule["agent_key"]}
        return None

    def execute_task(self, task_description: str, agent_name: str = "manager",
                     use_memory: bool = True) -> str:
        """Execute a task with the specified agent"""
        if not self.is_ready:
            return "❌ Zinin Corp не инициализирована. Проверьте API ключи."

        agent_map = {
            "manager": self.manager,
            "accountant": self.accountant,
            "smm": self.smm,
            "automator": self.automator,
            "designer": self.designer,
        }

        agent = agent_map.get(agent_name, self.manager)
        # Extract actual user message when context is present
        if "---\nНовое сообщение от Тима:" in task_description:
            short_desc = task_description.split("---\nНовое сообщение от Тима:")[-1].strip()[:100].split("\n")[0]
        else:
            short_desc = task_description.strip()[:100].split("\n")[0]

        # ── Auto-delegation for manager ──
        # If the task is clearly for a specialist, run specialist first,
        # then pass result to CEO for synthesis.
        if agent_name == "manager":
            delegation = self._detect_delegation_need(task_description)
            if delegation:
                specialist_key = delegation["agent_key"]
                specialist_agent = agent_map.get(specialist_key)
                if specialist_agent:
                    spec_label = AGENT_LABELS.get(specialist_key, specialist_key)
                    logger.info(f"Auto-delegation: manager → {specialist_key}")
                    _send_progress(f"{spec_label} готовит данные...")
                    log_task_start(specialist_key, short_desc)
                    try:
                        specialist_result = self._run_agent(
                            specialist_agent, task_description, specialist_key,
                            use_memory=use_memory,
                        )
                        log_task_end(specialist_key, short_desc, success=True)
                    except Exception as e:
                        logger.error(f"Specialist {specialist_key} failed: {e}")
                        log_task_end(specialist_key, short_desc, success=False)
                        specialist_result = f"❌ Ошибка: {e}"

                    _send_progress(f"{spec_label} → 👑 Алексей: передача данных")

                    # Now pass to CEO for synthesis
                    enriched = (
                        f"{task_description}\n\n"
                        f"--- Результат от специалиста ({specialist_key}) ---\n"
                        f"{specialist_result}\n"
                        f"--- Конец результата ---\n\n"
                        f"НИКОГДА НЕ ПРЕДСТАВЛЯЙСЯ. СРАЗУ к делу.\n"
                        f"Добавь свой краткий комментарий CEO к результату выше. "
                        f"Не повторяй весь результат — дай стратегическую оценку."
                    )
                    log_task_start(agent_name, short_desc)
                    try:
                        ceo_result = self._run_agent(
                            agent, enriched, agent_name,
                            use_memory=use_memory,
                            guardrail=_manager_guardrail,
                        )
                        log_task_end(agent_name, short_desc, success=True)
                        return ceo_result
                    except Exception as e:
                        logger.error(f"CEO synthesis failed: {e}")
                        log_task_end(agent_name, short_desc, success=False)
                        # Return specialist result anyway
                        return specialist_result

        # Track: task started
        log_task_start(agent_name, short_desc)

        # Add guardrail for CEO to prevent empty/introduction-only responses
        grl = _manager_guardrail if agent_name == "manager" else None

        try:
            result = self._run_agent(agent, task_description, agent_name,
                                        use_memory=use_memory, guardrail=grl)
            log_task_end(agent_name, short_desc, success=True)
            return result
        except Exception as e:
            logger.error(f"Task failed for {agent_name}: {e}", exc_info=True)
            log_task_end(agent_name, short_desc, success=False)
            return f"❌ Ошибка выполнения: {e}"

    # ──────────────────────────────────────────────────────────
    # Multi-agent tasks with context passing
    # ──────────────────────────────────────────────────────────

    def strategic_review(self) -> str:
        """Run strategic review: Маттиас + Мартин + Юки feed data → Алексей synthesizes"""
        if not self.is_ready:
            return "❌ Zinin Corp не инициализирована."

        has_smm = self.smm is not None

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

        agents = [self.accountant, self.automator]
        # Reset all agent state to prevent accumulation
        for a in agents:
            a.agent_executor = None
            a.tools_results = []
            if hasattr(a, '_times_executed'):
                a._times_executed = 0

        tasks = []

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
            agent=self.accountant,
        )
        tasks.append(task_finance)

        task_health = create_task(
            description=(
                "Проверь здоровье систем:\n"
                "1. Вызови System Health Checker с action='status'\n"
                "2. Вызови Integration Manager с action='list'\n"
                "Дай сводку: что работает, что нет."
                + TASK_WRAPPER
            ),
            expected_output="Краткий отчёт о состоянии систем и интеграций.",
            agent=self.automator,
        )
        tasks.append(task_health)

        # Task 3: Юки — content/SMM status (if available)
        if has_smm:
            self.smm.agent_executor = None
            task_smm = create_task(
                description=(
                    "Подготовь краткую сводку по контенту и SMM:\n"
                    "1. Используй Yuki Memory с action='get_stats' для статистики генераций\n"
                    "2. Используй LinkedIn Publisher с action='status' для статуса LinkedIn\n"
                    "Дай сводку: что опубликовано, что запланировано, статус LinkedIn."
                    + TASK_WRAPPER
                ),
                expected_output="Краткая контент-сводка с данными из инструментов.",
                agent=self.smm,
            )
            tasks.append(task_smm)
            agents.append(self.smm)

        # CEO synthesis with data from all agents
        context_agents = "Маттиаса, Мартина" + (" и Юки" if has_smm else "")
        task_strategy = create_task(
            description=(
                f"На основе данных от {context_agents} "
                "подготовь стратегический обзор:\n"
                "- Статус каждого проекта\n"
                "- Приоритеты на неделю (фокус на Крипто и Сборке)\n"
                "- Контент и публикации (от Юки)\n"
                "- Конкретные задачи для каждого агента\n"
                "- Риски и рекомендации\n\n"
                "⛔ НЕ ПИШИ 'запускаю сбор данных' или 'начинаю сбор информации'. "
                f"Данные от {context_agents} уже ПОЛУЧЕНЫ и переданы тебе в контексте. "
                "Проанализируй их и дай КОНКРЕТНЫЙ стратегический обзор."
                + TASK_WRAPPER
            ),
            expected_output=EXPECTED_OUTPUT,
            agent=self.manager,
            context=tasks,
            guardrail=_manager_guardrail,
        )
        tasks.append(task_strategy)
        agents.append(self.manager)

        # Progress messages after each step
        if has_smm:
            _step_messages = [
                "✅ 🏦 Маттиас: финансовая сводка готова\n⚙️ Мартин работает...",
                "✅ ⚙️ Мартин: техотчёт готов\n📱 Юки работает...",
                "✅ 📱 Юки: контент-сводка готова\n🏦→👑 Маттиас передаёт данные Алексею\n⚙️→👑 Мартин передаёт данные Алексею\n📱→👑 Юки передаёт данные Алексею\n👑 Алексей анализирует...",
                None,
            ]
        else:
            _step_messages = [
                "✅ 🏦 Маттиас: финансовая сводка готова\n⚙️ Мартин работает...",
                "✅ ⚙️ Мартин: техотчёт готов\n🏦→👑 Маттиас передаёт данные Алексею\n⚙️→👑 Мартин передаёт данные Алексею\n👑 Алексей анализирует...",
                None,
            ]
        _step_idx = [0]

        def _on_task_done(output):
            idx = _step_idx[0]
            _step_idx[0] += 1
            if idx < len(_step_messages) and _step_messages[idx]:
                _send_progress(_step_messages[idx])

        try:
            crew = Crew(
                agents=agents,
                tasks=tasks,
                process=Process.sequential,
                verbose=True,
                memory=False,
                task_callback=_on_task_done,
            )
            result = crew.kickoff()

            # Track completion and communication
            log_task_end("accountant", "Финансовая сводка (стратобзор)", success=True)
            log_task_end("automator", "Проверка систем (стратобзор)", success=True)
            log_communication("accountant", "manager", "Передача финансовых данных для стратобзора")
            log_communication("automator", "manager", "Передача техотчёта для стратобзора")
            if has_smm:
                log_task_end("smm", "Контент-сводка (стратобзор)", success=True)
                log_communication("smm", "manager", "Передача контент-сводки для стратобзора")
            log_task_start("manager", "Стратегический обзор (синтез)")
            log_task_end("manager", "Стратегический обзор (синтез)", success=True)
            log_communication_end("accountant")
            log_communication_end("automator")
            if has_smm:
                log_communication_end("smm")

            return str(result)
        except Exception as e:
            logger.error(f"Strategic review failed: {e}", exc_info=True)
            log_task_end("accountant", "Финансовая сводка (стратобзор)", success=False)
            log_task_end("automator", "Проверка систем (стратобзор)", success=False)
            return f"❌ Ошибка стратегического обзора: {e}"

    def financial_report(self) -> str:
        """Run full financial report from Маттиас"""
        task_desc = """
        Подготовь полный финансовый отчёт:

        1. Вызови full_portfolio — он сам соберёт данные по банкам, крипте и доходам
        2. Вызови openrouter_usage для расходов на AI
        3. НЕ вызывай другие инструменты — full_portfolio уже включает их данные

        Структура отчёта:
        - Сводка по активам (крипто + банки)
        - Доходы
        - Расходы на AI (+ Claude Code $200/мес фиксированная)
        - Рекомендации
        """
        return self.execute_task(task_desc, "accountant")

    def api_budget_check(self) -> str:
        """Check API budget status from Маттиас"""
        task_desc = """
        Проверь расходы на AI API:

        1. Используй openrouter_usage для расходов OpenRouter
        2. Используй elevenlabs_usage для расходов ElevenLabs
        3. Используй openai_usage для расходов OpenAI
        4. Учти Claude Code $200/мес (фиксированная подписка)

        Дай краткий отчёт: расходы по каждому сервису, общая сумма,
        рекомендации по оптимизации.
        """
        return self.execute_task(task_desc, "accountant")

    def subscription_analysis(self) -> str:
        """Analyze subscriptions from Маттиас"""
        task_desc = """
        Проанализируй доходы от подписок:

        1. Используй tribute_revenue для данных о подписках Tribute
        2. Дай сводку: активные подписки, MRR, рекомендации по росту.
        """
        return self.execute_task(task_desc, "accountant")

    def system_health_check(self) -> str:
        """Run system health check task"""
        task_desc = """
        Проведи полную проверку системы:

        1. Вызови System Health Checker с action='status' для общего состояния
        2. Вызови System Health Checker с action='agents' для проверки агентов
        3. Вызови System Health Checker с action='errors' для списка ошибок
        4. Вызови Integration Manager с action='list' для проверки интеграций

        Дай структурированный отчёт: что работает, что нет, рекомендации.
        """
        return self.execute_task(task_desc, "automator")

    def api_health_report(self) -> str:
        """Run comprehensive API health check from Мартин"""
        task_desc = """
        Проведи полную проверку здоровья ВСЕХ API:

        1. Вызови API Health Monitor с action='full_check' — это проверит ВСЕ API
        2. Проанализируй результаты
        3. Дай отчёт по каждой категории: финансовые API, AI API, платформы
        4. Укажи время отклика (latency) для каждого API
        5. Если есть проблемы — дай конкретные рекомендации по исправлению

        Структура отчёта:
        - Общий статус (healthy/degraded/critical)
        - Финансовые API (T-Bank, Moralis, Helius, TonAPI, CoinGecko, Tribute, Forex, Eventum)
        - AI API (OpenRouter, ElevenLabs, OpenAI, Groq)
        - Платформы (LinkedIn, Railway)
        - Рекомендации
        """
        return self.execute_task(task_desc, "automator")

    def integration_status(self) -> str:
        """Check integration status from Мартин"""
        task_desc = """
        Проверь статус всех интеграций:

        1. Вызови Integration Manager с action='list' для списка всех интеграций
        2. Вызови Integration Manager с action='list_cron' для cron-задач

        Дай краткий отчёт по каждой интеграции и рекомендации.
        """
        return self.execute_task(task_desc, "automator")

    def generate_post(self, topic: str = "", author: str = "kristina") -> str:
        """Generate a post with Yuki"""
        if not self.smm:
            return "❌ Юки не инициализирована. Проверьте конфигурацию."
        task_desc = f"""
        Сгенерируй пост для LinkedIn.

        1. Используй Yuki Memory с action='get_brand_voice' для загрузки профиля автора
        2. Используй Yuki Memory с action='get_forbidden' для списка запрещённых фраз
        3. Используй Content Generator с action='generate', topic='{topic or "карьерный рост"}', author='{author}'
        4. Если score < 0.8 — используй Content Generator с action='refine'
        5. Используй Yuki Memory с action='record_generation' для сохранения результата

        Верни финальный текст поста.
        """
        return self.execute_task(task_desc, "smm")

    def generate_podcast(self, topic: str = "", duration_minutes: int = 10) -> str:
        """Generate a podcast script with Yuki"""
        if not self.smm:
            return "❌ Юки не инициализирована. Проверьте конфигурацию."
        task_desc = f"""
        Сгенерируй сценарий подкаста.

        1. Используй Podcast Script Generator с topic='{topic or "AI и бизнес"}', duration_minutes={duration_minutes}
        2. Верни ТОЛЬКО текст сценария (всё что после --- в ответе инструмента).

        НЕ ДОБАВЛЯЙ ничего от себя. Верни сценарий как есть.
        """
        return self.execute_task(task_desc, "smm")

    def generate_design(self, task: str = "", brand: str = "corporation") -> str:
        """Generate design/visual content with Ryan (Designer)"""
        if not self.designer:
            return "❌ Райан не инициализирован. Проверьте конфигурацию."
        task_desc = f"""
        Выполни дизайн-задачу.

        1. Если нужна картинка — используй Image Generator с prompt='{task or "современный баннер для AI корпорации"}', brand='{brand}'
        2. Если нужна инфографика — используй Infographic Builder
        3. Если нужен график — используй Chart Generator
        4. Если нужно видео — используй Video Creator

        Задача: {task or "Создай визуал для AI Corporation"}
        Бренд: {brand}

        Верни результат с путями к созданным файлам.
        """
        return self.execute_task(task_desc, "designer")

    def content_review(self, content: str) -> str:
        """Review content with Yuki"""
        if not self.smm:
            return "❌ Юки не инициализирована. Проверьте конфигурацию."
        task_desc = f"""
        Оцени и критикуй этот пост:

        1. Используй Content Generator с action='critique', content=(текст ниже)
        2. Используй Yuki Memory с action='get_rules' для проверки по правилам
        3. Дай рекомендации по улучшению

        ТЕКСТ ДЛЯ ОЦЕНКИ:
        {content[:2000]}
        """
        return self.execute_task(task_desc, "smm")

    def linkedin_status(self) -> str:
        """Check LinkedIn integration status"""
        if not self.smm:
            return "❌ Юки не инициализирована. Проверьте конфигурацию."
        task_desc = """
        Проверь статус LinkedIn:

        1. Используй LinkedIn Publisher с action='status' для общего статуса
        2. Используй LinkedIn Publisher с action='check_token' для проверки токена
        3. Используй Yuki Memory с action='get_stats' для статистики генераций

        Дай краткий отчёт.
        """
        return self.execute_task(task_desc, "smm")

    def full_corporation_report(self) -> str:
        """Full weekly report: all agents contribute, Алексей synthesizes."""
        if not self.is_ready:
            return "❌ Zinin Corp не инициализирована."

        agents = [self.accountant, self.automator, self.manager]
        # Reset all agent state to prevent accumulation
        for a in agents:
            a.agent_executor = None
            a.tools_results = []
            if hasattr(a, '_times_executed'):
                a._times_executed = 0
        tasks = []

        # Track start for all agents
        log_task_start("accountant", "Финансовый отчёт (полный)")
        log_task_start("automator", "Техотчёт (полный)")
        _send_progress(
            "📊 Полный отчёт корпорации запущен\n"
            "🏦 Маттиас готовит финансовый отчёт...\n"
            "⚙️ Мартин проверяет системы...\n"
            "📱 Юки готовит отчёт по контенту..."
        )

        # Task 1: Маттиас — financial report
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
            agent=self.accountant,
        )
        tasks.append(task_fin)

        # Task 2: Мартин — system health
        task_tech = create_task(
            description=(
                "Проведи полную проверку систем:\n"
                "1. System Health Checker action='status'\n"
                "2. Integration Manager action='list'\n"
                "Включи: статус каждого сервиса, время отклика, ошибки."
                + TASK_WRAPPER
            ),
            expected_output="Полный технический отчёт с реальными данными.",
            agent=self.automator,
        )
        tasks.append(task_tech)

        # Task 3: Yuki — content stats (if available)
        if self.smm:
            self.smm.agent_executor = None
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
                agent=self.smm,
            )
            tasks.append(task_smm)
            agents.insert(2, self.smm)

        # Task 4: Алексей — synthesis with context from all
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
                "⛔ НЕ ПИШИ 'запускаю сбор данных' или 'начинаю сбор информации'. "
                "Данные от агентов уже ПОЛУЧЕНЫ и переданы тебе в контексте. "
                "Проанализируй их и дай КОНКРЕТНЫЙ отчёт."
                + TASK_WRAPPER
            ),
            expected_output=(
                "Полный еженедельный отчёт CEO с данными от всех агентов. "
                "Минимум 400 слов."
            ),
            agent=self.manager,
            context=tasks[:-1] if len(tasks) > 1 else tasks,
            guardrail=_manager_guardrail,
        )
        tasks.append(task_ceo)

        # Progress messages after each step
        has_smm = self.smm is not None
        _report_steps = [
            "✅ 🏦 Маттиас: финансовый отчёт готов\n⚙️ Мартин работает...",
            ("✅ ⚙️ Мартин: техотчёт готов\n📱 Юки работает..." if has_smm
             else "✅ ⚙️ Мартин: техотчёт готов\n👑 Алексей анализирует..."),
            ("✅ 📱 Юки: контент-отчёт готов\n"
             "🏦→👑 Маттиас передаёт данные Алексею\n"
             "⚙️→👑 Мартин передаёт данные Алексею\n"
             "📱→👑 Юки передаёт данные Алексею\n"
             "👑 Алексей готовит синтез..." if has_smm
             else None),
            None,
        ]
        _report_idx = [0]

        def _on_report_task_done(output):
            idx = _report_idx[0]
            _report_idx[0] += 1
            if idx < len(_report_steps) and _report_steps[idx]:
                _send_progress(_report_steps[idx])

        try:
            crew = Crew(
                agents=agents,
                tasks=tasks,
                process=Process.sequential,
                verbose=True,
                memory=False,
                task_callback=_on_report_task_done,
            )
            result = crew.kickoff()

            # Track completion and communication
            log_task_end("accountant", "Финансовый отчёт (полный)", success=True)
            log_task_end("automator", "Техотчёт (полный)", success=True)
            if self.smm:
                log_task_end("smm", "Отчёт по контенту (полный)", success=True)
                log_communication("smm", "manager", "Передача контент-отчёта для CEO")

            log_communication("accountant", "manager", "Передача финотчёта для CEO")
            log_communication("automator", "manager", "Передача техотчёта для CEO")
            log_task_start("manager", "Еженедельный отчёт CEO (синтез)")
            log_task_end("manager", "Еженедельный отчёт CEO (синтез)", success=True)

            # Clear communication flags
            for agent_key in ["accountant", "automator", "smm"]:
                log_communication_end(agent_key)

            return str(result)
        except Exception as e:
            logger.error(f"Full corporation report failed: {e}", exc_info=True)
            log_task_end("accountant", "Финансовый отчёт (полный)", success=False)
            log_task_end("automator", "Техотчёт (полный)", success=False)
            if self.smm:
                log_task_end("smm", "Отчёт по контенту (полный)", success=False)
            return f"❌ Ошибка при формировании отчёта: {e}"


# Singleton instance
_corporation: Optional[AICorporation] = None


def get_corporation() -> AICorporation:
    """Get or create the Zinin Corp instance"""
    global _corporation
    if _corporation is None:
        _corporation = AICorporation()
    return _corporation
