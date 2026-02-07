"""Bridge between async Telegram and sync CrewAI agents."""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class AgentBridge:
    """Async wrapper around AICorporation.execute_task()."""

    _corp = None

    @classmethod
    def _get_corp(cls):
        if cls._corp is None:
            from ..crew import get_corporation
            cls._corp = get_corporation()
        if not cls._corp.is_ready:
            cls._corp.initialize()
        return cls._corp

    @classmethod
    async def send_to_agent(
        cls,
        message: str,
        agent_name: str = "accountant",
        chat_context: str = "",
    ) -> str:
        """Send a message to a CrewAI agent (runs in thread)."""
        task_desc = message
        if chat_context:
            task_desc = (
                f"{chat_context}\n\n"
                f"---\nНовое сообщение от Тима: {message}"
            )

        def _sync():
            corp = cls._get_corp()
            return corp.execute_task(task_desc, agent_name)

        return await asyncio.to_thread(_sync)

    @classmethod
    async def run_financial_report(cls) -> str:
        def _sync():
            corp = cls._get_corp()
            return corp.execute_task(
                "Подготовь полный финансовый отчёт. Используй все доступные инструменты.",
                "accountant",
            )
        return await asyncio.to_thread(_sync)

    @classmethod
    async def run_portfolio_summary(cls) -> str:
        def _sync():
            corp = cls._get_corp()
            return corp.execute_task(
                "Подготовь сводку портфеля. Используй full_portfolio.",
                "accountant",
            )
        return await asyncio.to_thread(_sync)
