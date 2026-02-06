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
            self.automator = create_automator_agent()

            if not all([self.manager, self.accountant, self.automator]):
                return False

            # Create crew with sequential process (no embeddings needed)
            self.crew = Crew(
                agents=[self.manager, self.accountant, self.automator],
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
            "automator": self.automator,
        }

        agent = agent_map.get(agent_name, self.manager)

        task = create_task(
            description=task_description,
            expected_output="Детальный ответ на задачу",
            agent=agent,
        )

        try:
            result = self.crew.kickoff(tasks=[task])
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
        """Run financial report task"""
        task_desc = """
        Подготовь еженедельный финансовый отчёт.
        Включи: MRR, расходы на API, прогноз на месяц.
        """
        return self.execute_task(task_desc, "accountant")

    def system_health_check(self) -> str:
        """Run system health check task"""
        task_desc = """
        Проверь работоспособность всех интеграций.
        Убедись что публикации работают.
        Залогируй любые ошибки.
        """
        return self.execute_task(task_desc, "automator")


# Singleton instance
_corporation: Optional[AICorporation] = None


def get_corporation() -> AICorporation:
    """Get or create the AI Corporation instance"""
    global _corporation
    if _corporation is None:
        _corporation = AICorporation()
    return _corporation
