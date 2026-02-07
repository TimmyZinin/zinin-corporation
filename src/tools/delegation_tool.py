"""
🔄 Zinin Corp — Delegation Tool

Allows the CEO agent (Alexey) to delegate tasks to other agents
during task execution. This is a CrewAI BaseTool that calls
execute_task() on the target agent and returns the result.
"""

import logging
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Agent registry for validation and descriptions
DELEGATABLE_AGENTS = {
    "accountant": {
        "name": "Маттиас",
        "role": "CFO",
        "skills": "финансы, бюджет, P&L, ROI, подписки, API расходы, криптопортфель",
    },
    "smm": {
        "name": "Юки",
        "role": "Head of SMM",
        "skills": "контент-план, LinkedIn посты, копирайтинг, публикации, SMM стратегия",
    },
    "automator": {
        "name": "Мартин",
        "role": "CTO",
        "skills": "техника, API, деплой, интеграции, webhook, cron, мониторинг систем",
    },
}


class DelegateTaskInput(BaseModel):
    agent_name: str = Field(
        ...,
        description=(
            "Ключ агента для делегации. Доступные агенты: "
            "accountant (Маттиас — финансы), "
            "smm (Юки — контент и LinkedIn), "
            "automator (Мартин — техника и API)"
        ),
    )
    task_description: str = Field(
        ...,
        description=(
            "Подробное описание задачи на русском языке. "
            "Включи контекст и конкретные требования."
        ),
    )


class DelegateTaskTool(BaseTool):
    name: str = "Delegate Task"
    description: str = (
        "Делегировать задачу другому агенту команды и получить результат. "
        "Используй когда задача относится к специализации другого агента:\n"
        "• accountant (Маттиас) — финансы, бюджет, P&L, подписки, API расходы\n"
        "• smm (Юки) — контент-план, LinkedIn посты, копирайтинг, публикации\n"
        "• automator (Мартин) — техника, API, деплой, интеграции, мониторинг\n\n"
        "Инструмент выполнит задачу через указанного агента и вернёт результат."
    )
    args_schema: Type[BaseModel] = DelegateTaskInput

    def _run(self, agent_name: str, task_description: str) -> str:
        """Execute delegation to another agent."""
        # Validate agent name
        agent_name = agent_name.strip().lower()
        if agent_name not in DELEGATABLE_AGENTS:
            available = ", ".join(
                f"{k} ({v['name']})" for k, v in DELEGATABLE_AGENTS.items()
            )
            return (
                f"❌ Агент '{agent_name}' не найден. "
                f"Доступные агенты: {available}"
            )

        agent_info = DELEGATABLE_AGENTS[agent_name]

        # Lazy import to avoid circular dependency
        try:
            from src.crew import get_corporation
        except ImportError:
            from crew import get_corporation

        corp = get_corporation()
        if not corp or not corp.is_ready:
            return "❌ Корпорация не инициализирована. Невозможно делегировать."

        logger.info(
            f"CEO делегирует задачу → {agent_info['name']} ({agent_info['role']}): "
            f"{task_description[:80]}..."
        )

        try:
            result = corp.execute_task(task_description, agent_name)
            return (
                f"✅ Ответ от {agent_info['name']} ({agent_info['role']}):\n\n"
                f"{result}"
            )
        except Exception as e:
            logger.error(f"Delegation to {agent_name} failed: {e}")
            return (
                f"❌ Ошибка делегации к {agent_info['name']}: "
                f"{type(e).__name__}: {str(e)[:200]}"
            )
