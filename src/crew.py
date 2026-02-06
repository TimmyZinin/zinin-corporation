"""
🏢 AI Corporation — Crew Module
Orchestrates the multi-agent system
"""

import os
import yaml
import traceback
from typing import Optional, List
from crewai import Crew, Task, Process

from .agents import (
    create_manager_agent,
    create_accountant_agent,
    create_smm_agent,
    create_automator_agent,
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


def create_task(description: str, expected_output: str, agent) -> Task:
    """Create a task for an agent"""
    return Task(
        description=description,
        expected_output=expected_output,
        agent=agent,
    )


class AICorporation:
    """Main class for AI Corporation crew management"""

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
                return False

            # Create agents
            self.manager = create_manager_agent()
            self.accountant = create_accountant_agent()
            self.smm = create_smm_agent()
            self.automator = create_automator_agent()

            if not all([self.manager, self.accountant, self.automator]):
                return False

            # SMM agent is optional (uses free model, may fail)
            if not self.smm:
                print("WARNING: SMM agent (Yuki) failed to init — continuing without her")

            # Create crew with sequential process (no embeddings needed)
            all_agents = [self.manager, self.accountant, self.automator]
            if self.smm:
                all_agents.append(self.smm)

            self.crew = Crew(
                agents=all_agents,
                process=Process.sequential,
                verbose=True,
                memory=False,
            )

            self._initialized = True
            print("AI Corporation initialized successfully!")
            return True

        except Exception as e:
            print(f"Failed to initialize AI Corporation: {e}")
            traceback.print_exc()
            return False

    @property
    def is_ready(self) -> bool:
        """Check if the corporation is ready"""
        return self._initialized and self.crew is not None

    def execute_task(self, task_description: str, agent_name: str = "manager") -> str:
        """Execute a task with the specified agent"""
        if not self.is_ready:
            return "❌ AI Corporation не инициализирована. Проверьте API ключи."

        agent_map = {
            "manager": self.manager,
            "accountant": self.accountant,
            "smm": self.smm,
            "automator": self.automator,
        }

        agent = agent_map.get(agent_name, self.manager)

        # Build expected output with substance requirement
        expected = (
            "Содержательный, конкретный и полный ответ на русском языке. "
            "Минимум 200 слов. "
            "Включай: конкретные шаги, рекомендации, цифры, примеры. "
            "НЕ останавливайся на приветствии — дай полный ответ по существу вопроса."
        )

        # Wrap the task with explicit instruction
        full_description = (
            f"{task_description}\n\n"
            "ВАЖНО: Дай ПОЛНЫЙ содержательный ответ. "
            "Приветствие — максимум 1 строка, потом СРАЗУ переходи к сути. "
            "Ответ должен содержать конкретные детали, шаги и рекомендации."
        )

        task = create_task(
            description=full_description,
            expected_output=expected,
            agent=agent,
        )

        try:
            crew = Crew(
                agents=[agent],
                tasks=[task],
                process=Process.sequential,
                verbose=True,
                memory=False,
            )
            result = crew.kickoff()
            return str(result)
        except Exception as e:
            return f"❌ Ошибка выполнения: {e}"

    def strategic_review(self) -> str:
        """Run strategic review task"""
        task_desc = """
        Проанализируй текущее состояние AI-корпорации.
        Дай рекомендации по приоритетам на эту неделю.
        Учти: фокус на Крипто и Сборке (приносят деньги).
        """
        return self.execute_task(task_desc, "manager")

    def financial_report(self) -> str:
        """Run full financial report from Amara"""
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
        """Check API budget status from Amara"""
        task_desc = """
        Проверь текущее состояние API бюджетов:

        1. Вызови API Usage Tracker с action='usage' для текущих расходов
        2. Вызови API Usage Tracker с action='alerts' для проверки превышений

        Дай краткий отчёт: кто сколько потратил, есть ли превышения,
        рекомендации по оптимизации.
        """
        return self.execute_task(task_desc, "accountant")

    def subscription_analysis(self) -> str:
        """Analyze subscriptions from Amara"""
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
        """Check integration status from Niraj"""
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


# Singleton instance
_corporation: Optional[AICorporation] = None


def get_corporation() -> AICorporation:
    """Get or create the AI Corporation instance"""
    global _corporation
    if _corporation is None:
        _corporation = AICorporation()
    return _corporation
