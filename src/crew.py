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
)
from .activity_tracker import (
    log_task_start,
    log_task_end,
    log_communication,
    log_communication_end,
)

logger = logging.getLogger(__name__)

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

TASK_WRAPPER = (
    "\n\nВАЖНО: Дай ПОЛНЫЙ содержательный ответ. "
    "Приветствие — максимум 1 строка, потом СРАЗУ переходи к сути. "
    "Ответ должен содержать конкретные детали, шаги и рекомендации.\n\n"
    "⛔ ЗАПРЕТ НА ВЫДУМКИ: НИКОГДА не придумывай цифры, данные, метрики или факты. "
    "Используй ТОЛЬКО реальные данные из инструментов. "
    "Если данных нет — честно скажи: 'У меня нет данных по этому вопросу'. "
    "Ложь КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНА — Тим принимает решения на основе твоих ответов.\n\n"
    "⚡ ДЕЛЕГИРОВАНИЕ: Если задача касается контента/SMM/публикаций — "
    "ВЫЗОВИ инструмент 'Delegate Task' с agent_name='smm'. "
    "Если задача про финансы/бюджет — ВЫЗОВИ 'Delegate Task' с agent_name='accountant'. "
    "Если задача про технику/API — ВЫЗОВИ 'Delegate Task' с agent_name='automator'. "
    "НЕ пиши 'делегирую' или 'поручаю' в тексте — ИСПОЛЬЗУЙ ИНСТРУМЕНТ."
)


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

            if not all([self.manager, self.accountant, self.automator]):
                logger.error("Core agents failed to initialize")
                return False

            # SMM agent is optional
            if not self.smm:
                logger.warning("SMM agent (Юки) failed to init — continuing without her")

            # Create crew with memory enabled
            all_agents = [self.manager, self.accountant, self.automator]
            if self.smm:
                all_agents.append(self.smm)

            self.crew = Crew(
                agents=all_agents,
                process=Process.sequential,
                verbose=True,
                memory=True,
                embedder=EMBEDDER_CONFIG,
            )

            self._initialized = True
            logger.info("Zinin Corp initialized successfully with memory enabled")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Zinin Corp: {e}", exc_info=True)
            return False

    @property
    def is_ready(self) -> bool:
        """Check if the corporation is ready"""
        return self._initialized and self.crew is not None

    def _run_agent(self, agent, task_description: str, agent_name: str = "") -> str:
        """Run a single agent task with memory fallback. Returns result string."""
        full_description = f"{task_description}{TASK_WRAPPER}"
        task = create_task(
            description=full_description,
            expected_output=EXPECTED_OUTPUT,
            agent=agent,
        )
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
            ],
        },
    ]

    def _detect_delegation_need(self, text: str) -> Optional[dict]:
        """Detect if manager task should be auto-delegated to a specialist."""
        text_lower = text.lower()
        for rule in self._DELEGATION_RULES:
            for kw in rule["keywords"]:
                if kw in text_lower:
                    return {"agent_key": rule["agent_key"]}
        return None

    def execute_task(self, task_description: str, agent_name: str = "manager") -> str:
        """Execute a task with the specified agent"""
        if not self.is_ready:
            return "❌ Zinin Corp не инициализирована. Проверьте API ключи."

        agent_map = {
            "manager": self.manager,
            "accountant": self.accountant,
            "smm": self.smm,
            "automator": self.automator,
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
                    logger.info(f"Auto-delegation: manager → {specialist_key}")
                    log_task_start(specialist_key, short_desc)
                    try:
                        specialist_result = self._run_agent(
                            specialist_agent, task_description, specialist_key,
                        )
                        log_task_end(specialist_key, short_desc, success=True)
                    except Exception as e:
                        logger.error(f"Specialist {specialist_key} failed: {e}")
                        log_task_end(specialist_key, short_desc, success=False)
                        specialist_result = f"❌ Ошибка: {e}"

                    # Now pass to CEO for synthesis
                    enriched = (
                        f"{task_description}\n\n"
                        f"--- Результат от специалиста ({specialist_key}) ---\n"
                        f"{specialist_result}\n"
                        f"--- Конец результата ---\n\n"
                        f"Добавь свой краткий комментарий CEO к результату выше. "
                        f"Не повторяй весь результат — дай стратегическую оценку."
                    )
                    log_task_start(agent_name, short_desc)
                    try:
                        ceo_result = self._run_agent(agent, enriched, agent_name)
                        log_task_end(agent_name, short_desc, success=True)
                        return ceo_result
                    except Exception as e:
                        logger.error(f"CEO synthesis failed: {e}")
                        log_task_end(agent_name, short_desc, success=False)
                        # Return specialist result anyway
                        return specialist_result

        # Track: task started
        log_task_start(agent_name, short_desc)

        try:
            result = self._run_agent(agent, task_description, agent_name)
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
        """Run strategic review: Маттиас + Мартин feed data → Алексей synthesizes"""
        if not self.is_ready:
            return "❌ Zinin Corp не инициализирована."

        log_task_start("accountant", "Финансовая сводка (стратобзор)")
        log_task_start("automator", "Проверка систем (стратобзор)")

        task_finance = create_task(
            description=(
                "Подготовь краткую финансовую сводку:\n"
                "1. Вызови Financial Tracker с action='report'\n"
                "2. Вызови Subscription Monitor с action='status'\n"
                "3. Вызови API Usage Tracker с action='usage'\n"
                "Дай сводку: доходы, расходы, MRR, API расходы."
                + TASK_WRAPPER
            ),
            expected_output="Краткая финансовая сводка с реальными данными из инструментов.",
            agent=self.accountant,
        )

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

        task_strategy = create_task(
            description=(
                "На основе финансовых данных от Маттиаса и технического отчёта от Мартина "
                "подготовь стратегический обзор:\n"
                "- Статус каждого проекта\n"
                "- Приоритеты на неделю (фокус на Крипто и Сборке)\n"
                "- Конкретные задачи для каждого агента\n"
                "- Риски и рекомендации"
                + TASK_WRAPPER
            ),
            expected_output=EXPECTED_OUTPUT,
            agent=self.manager,
            context=[task_finance, task_health],
        )

        try:
            crew = Crew(
                agents=[self.accountant, self.automator, self.manager],
                tasks=[task_finance, task_health, task_strategy],
                process=Process.sequential,
                verbose=True,
                memory=True,
                embedder=EMBEDDER_CONFIG,
            )
            result = crew.kickoff()

            # Track completion and communication
            log_task_end("accountant", "Финансовая сводка (стратобзор)", success=True)
            log_task_end("automator", "Проверка систем (стратобзор)", success=True)
            log_communication("accountant", "manager", "Передача финансовых данных для стратобзора")
            log_communication("automator", "manager", "Передача техотчёта для стратобзора")
            log_task_start("manager", "Стратегический обзор (синтез)")
            log_task_end("manager", "Стратегический обзор (синтез)", success=True)
            log_communication_end("accountant")
            log_communication_end("automator")

            return str(result)
        except Exception as e:
            logger.error(f"Strategic review failed: {e}", exc_info=True)
            log_task_end("accountant", "Финансовая сводка (стратобзор)", success=False)
            log_task_end("automator", "Проверка систем (стратобзор)", success=False)
            return f"❌ Ошибка стратегического обзора: {e}"

    def financial_report(self) -> str:
        """Run full financial report from Маттиас"""
        task_desc = """
        Используй свои инструменты для подготовки финансового отчёта:

        1. Вызови Financial Tracker с action='report' для общего отчёта по проектам
        2. Вызови Subscription Monitor с action='status' и action='forecast' для данных по подпискам
        3. Вызови API Usage Tracker с action='usage' и action='alerts' для контроля расходов

        На основе полученных данных подготовь структурированный отчёт:
        - Сводка по доходам и расходам каждого проекта
        - MRR от подписок
        - API расходы по агентам
        - ROI-анализ
        - Рекомендации для CEO
        """
        return self.execute_task(task_desc, "accountant")

    def api_budget_check(self) -> str:
        """Check API budget status from Маттиас"""
        task_desc = """
        Проверь текущее состояние API бюджетов:

        1. Вызови API Usage Tracker с action='usage' для текущих расходов
        2. Вызови API Usage Tracker с action='alerts' для проверки превышений

        Дай краткий отчёт: кто сколько потратил, есть ли превышения,
        рекомендации по оптимизации.
        """
        return self.execute_task(task_desc, "accountant")

    def subscription_analysis(self) -> str:
        """Analyze subscriptions from Маттиас"""
        task_desc = """
        Проанализируй состояние подписок в клубах:

        1. Вызови Subscription Monitor с action='status' для текущих подписчиков
        2. Вызови Subscription Monitor с action='forecast' для прогноза MRR
        3. Вызови Subscription Monitor с action='churn' для анализа оттока

        Дай рекомендации по росту подписчиков и снижению оттока.
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
        tasks = []

        # Track start for all agents
        log_task_start("accountant", "Финансовый отчёт (полный)")
        log_task_start("automator", "Техотчёт (полный)")

        # Task 1: Маттиас — financial report
        task_fin = create_task(
            description=(
                "Подготовь полный финансовый отчёт:\n"
                "1. Financial Tracker action='report'\n"
                "2. Subscription Monitor action='status' и action='forecast'\n"
                "3. API Usage Tracker action='usage' и action='alerts'\n"
                "Включи: доходы, расходы, MRR, API расходы, ROI."
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
                "- Риски и рекомендации"
                + TASK_WRAPPER
            ),
            expected_output=(
                "Полный еженедельный отчёт CEO с данными от всех агентов. "
                "Минимум 400 слов."
            ),
            agent=self.manager,
            context=tasks[:-1] if len(tasks) > 1 else tasks,
        )
        tasks.append(task_ceo)

        try:
            crew = Crew(
                agents=agents,
                tasks=tasks,
                process=Process.sequential,
                verbose=True,
                memory=True,
                embedder=EMBEDDER_CONFIG,
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
