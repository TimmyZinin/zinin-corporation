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
# Knowledge Sources — business documents for RAG
# ──────────────────────────────────────────────────────────
def _load_knowledge_sources() -> list:
    """Load knowledge sources from knowledge/ directory."""
    knowledge_dir_candidates = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge"),
        "/app/knowledge",
        "knowledge",
    ]
    knowledge_dir = None
    for d in knowledge_dir_candidates:
        if os.path.isdir(d):
            knowledge_dir = d
            break
    if not knowledge_dir:
        logger.info("No knowledge/ directory found — skipping knowledge sources")
        return []
    try:
        from crewai.knowledge.sources import TextFileKnowledgeSource
        md_files = [
            os.path.join(knowledge_dir, f)
            for f in sorted(os.listdir(knowledge_dir))
            if f.endswith((".md", ".txt"))
        ]
        if not md_files:
            logger.info("No .md/.txt files in knowledge/ — skipping")
            return []
        source = TextFileKnowledgeSource(
            file_paths=md_files,
            chunk_size=4000,
            chunk_overlap=200,
        )
        logger.info(f"Loaded knowledge source: {len(md_files)} files from {knowledge_dir}")
        return [source]
    except ImportError:
        logger.warning("crewai.knowledge not available — skipping knowledge sources")
        return []
    except Exception as e:
        logger.warning(f"Failed to load knowledge sources: {e}")
        return []


KNOWLEDGE_SOURCES = _load_knowledge_sources()


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

# Short format for Telegram chat (accountant, automator)
EXPECTED_OUTPUT_SHORT = (
    "КОРОТКИЙ ответ на русском. Максимум 3-5 предложений. "
    "Таблицы и числа вместо длинных абзацев. "
    "Формат: факт → цифра → вывод. Без воды. "
    "⛔ НИКОГДА не выдумывай цифры. Если данных нет — скажи прямо."
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


# ── Template phrases that indicate fabrication or lazy responses ──
_TEMPLATE_PHRASES = [
    "я запущу", "начинаю проверку", "сейчас проверю", "давайте проверим",
    "начинаю анализ", "приступаю к", "сейчас подготовлю",
    "предлагаю следующее", "рекомендую обратить",
    "к сожалению, у меня нет доступа", "я не могу получить",
    "добрый день, я", "привет, я алексей", "меня зовут",
    "как ваш ceo", "как cfo", "как cto", "позвольте представиться",
]

# ── Data indicators: signs that response contains real tool output ──
_DATA_INDICATORS = [
    "$", "₽", "%", "rub", "usd", "api", "http", "error", "ok",
    "✅", "❌", "⚠️", "📊", "📈", "📉",
]


def _has_template_phrases(text: str) -> list[str]:
    """Return list of found template phrases in text."""
    lower = text.lower()
    return [p for p in _TEMPLATE_PHRASES if p in lower]


def _has_data_indicators(text: str) -> bool:
    """Check if text contains indicators of real tool-sourced data."""
    lower = text.lower()
    return any(ind in lower for ind in _DATA_INDICATORS)


def _manager_guardrail(task_output) -> tuple[bool, str]:
    """Guardrail for manager: reject too-short, template-heavy, or data-free answers."""
    try:
        text = task_output.raw if hasattr(task_output, 'raw') else str(task_output)
    except Exception:
        text = str(task_output) if task_output else ""
    # 1. Minimum length
    if len(text) < 100:
        return (False,
                "Ответ слишком короткий. Ты ОБЯЗАН вызвать инструмент Delegate Task "
                "для делегации задачи специалисту, получить результат и включить его в ответ. "
                "НЕ пиши 'делегирую' — ВЫЗОВИ Action: Delegate Task.")
    # 2. Template phrases (fabrication check)
    found = _has_template_phrases(text)
    if found and len(text) < 300:
        return (False,
                f"Ответ содержит шаблонные фразы ({', '.join(found[:3])}). "
                "Это признак фабрикации. ВЫЗОВИ свои инструменты и дай КОНКРЕТНЫЙ "
                "ответ с реальными данными. НЕ описывай что собираешься делать — СДЕЛАЙ.")
    return (True, text)


def _specialist_guardrail(task_output) -> tuple[bool, str]:
    """Guardrail for specialists: reject too-short, fabricated, or data-free answers."""
    try:
        text = task_output.raw if hasattr(task_output, 'raw') else str(task_output)
    except Exception:
        text = str(task_output) if task_output else ""
    # 1. Minimum length
    if len(text) < 150:
        return (False,
                "Ответ слишком короткий. Ты ОБЯЗАН ВЫЗВАТЬ свои инструменты и вернуть "
                "результат с РЕАЛЬНЫМИ данными. НЕ пиши 'запускаю' или 'начинаю' — "
                "ИСПОЛЬЗУЙ Action: <название инструмента> ПРЯМО СЕЙЧАС.")
    # 2. Template phrases (fabrication check)
    found = _has_template_phrases(text)
    if found and not _has_data_indicators(text):
        return (False,
                f"Ответ содержит шаблонные фразы ({', '.join(found[:3])}) "
                "без реальных данных. ВЫЗОВИ свои инструменты, получи РЕАЛЬНЫЕ данные "
                "и включи их в ответ. Цифры, статусы, URL — что угодно конкретное.")
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
    """Main class for Zinin Corp crew management.

    Since Sprint 2, orchestration is done via CorporationFlow (src/flows.py).
    This class remains as the public API and backward-compat layer.
    """

    def __init__(self):
        self.config = load_crew_config()
        self.manager = None
        self.accountant = None
        self.smm = None
        self.automator = None
        self.designer = None
        self.crew = None
        self._initialized = False
        self._pool = None  # flows._AgentPool ref

    def initialize(self) -> bool:
        """Initialize all agents via the shared AgentPool and crew"""
        try:
            from .flows import get_agent_pool
            pool = get_agent_pool()
            if not pool.is_ready:
                logger.error("Agent pool failed to initialize")
                return False

            # Expose agents as instance attrs for backward compat
            self.manager = pool.get("manager")
            self.accountant = pool.get("accountant")
            self.smm = pool.get("smm")
            self.automator = pool.get("automator")
            self.designer = pool.get("designer")
            self._pool = pool

            if not all([self.manager, self.accountant, self.automator]):
                logger.error("Core agents failed to initialize")
                return False

            # Create crew reference for backward compat (is_ready check)
            all_agents = [a for a in [self.manager, self.accountant, self.automator,
                                       self.smm, self.designer] if a]
            self.crew = Crew(
                agents=all_agents,
                process=Process.sequential,
                verbose=True,
                memory=False,
            )

            self._initialized = True
            logger.info("Zinin Corp initialized successfully (Flow-based)")
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
        # Use short output for accountant/automator in Telegram chat, long for manager/reports
        output_fmt = EXPECTED_OUTPUT_SHORT if agent_name in ("accountant", "automator") else EXPECTED_OUTPUT
        task = create_task(
            description=full_description,
            expected_output=output_fmt,
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
            crew_kwargs = {
                "agents": [agent],
                "tasks": [task],
                "process": Process.sequential,
                "verbose": True,
                "memory": True,
                "embedder": EMBEDDER_CONFIG,
            }
            if KNOWLEDGE_SOURCES:
                crew_kwargs["knowledge_sources"] = KNOWLEDGE_SOURCES
            crew = Crew(**crew_kwargs)
            return str(crew.kickoff())
        except Exception as e:
            logger.warning(f"_run_agent({agent_name}) memory failed: {e}, retrying without memory")
            task_retry = create_task(
                description=full_description,
                expected_output=output_fmt,
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

    def execute_task(self, task_description: str, agent_name: str = "manager",
                     use_memory: bool = True) -> str:
        """Execute a task via CorporationFlow."""
        if not self.is_ready:
            return "❌ Zinin Corp не инициализирована. Проверьте API ключи."

        from .flows import run_task
        return run_task(task_description, agent_name, use_memory)

    # ──────────────────────────────────────────────────────────
    # Multi-agent tasks with context passing
    # ──────────────────────────────────────────────────────────

    def strategic_review(self) -> str:
        """Run strategic review via CorporationFlow."""
        if not self.is_ready:
            return "❌ Zinin Corp не инициализирована."

        from .flows import run_strategic_review
        return run_strategic_review()

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

    def cto_generate_proposal(self) -> dict:
        """CTO generates one improvement proposal for an agent. Called by scheduler."""
        if not self.is_ready:
            return {"error": "Corporation not initialized"}

        task_desc = (
            "Проведи проактивный анализ агентов корпорации.\n\n"
            "1. Используй Agent Improvement Advisor с action='analyze_all' — "
            "он сам выберет агента, который давно не анализировался.\n"
            "2. Верни ПОЛНЫЙ результат от инструмента без изменений.\n\n"
            "НЕ пиши 'начинаю анализ' — ВЫЗОВИ ИНСТРУМЕНТ ПРЯМО СЕЙЧАС."
        )
        try:
            result = self._run_agent(
                self.automator, task_desc, "automator",
                use_memory=False,
            )
            return {"result": result}
        except Exception as e:
            logger.error(f"CTO proposal generation failed: {e}")
            return {"error": str(e)}

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
        """Full weekly report via CorporationFlow."""
        if not self.is_ready:
            return "❌ Zinin Corp не инициализирована."

        from .flows import run_full_report
        return run_full_report()


# Singleton instance
_corporation: Optional[AICorporation] = None


def get_corporation() -> AICorporation:
    """Get or create the Zinin Corp instance"""
    global _corporation
    if _corporation is None:
        _corporation = AICorporation()
    return _corporation
