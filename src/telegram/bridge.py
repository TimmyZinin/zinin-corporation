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
            logger.info("AgentBridge: creating AICorporation (first call)...")
            from ..crew import get_corporation
            cls._corp = get_corporation()
        if not cls._corp.is_ready:
            logger.info("AgentBridge: initializing corporation...")
            cls._corp.initialize()
            logger.info(f"AgentBridge: corporation ready={cls._corp.is_ready}")
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
            logger.info(f"AgentBridge._sync: agent={agent_name}, msg={message[:60]}")
            corp = cls._get_corp()
            logger.info(f"AgentBridge._sync: corp ready, calling execute_task...")
            result = corp.execute_task(task_desc, agent_name, use_memory=False)
            logger.info(f"AgentBridge._sync: done, {len(result)} chars")
            return result

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

    @classmethod
    async def run_strategic_review(cls) -> str:
        """Run strategic review: Маттиас + Мартин → Алексей synthesis."""
        def _sync():
            corp = cls._get_corp()
            return corp.strategic_review()
        return await asyncio.to_thread(_sync)

    @classmethod
    async def run_corporation_report(cls) -> str:
        """Run full corporation report: all agents → CEO synthesis."""
        def _sync():
            corp = cls._get_corp()
            return corp.full_corporation_report()
        return await asyncio.to_thread(_sync)

    @classmethod
    async def run_generate_post(cls, topic: str = "", author: str = "kristina") -> str:
        """Generate a LinkedIn post with Yuki (SMM)."""
        def _sync():
            corp = cls._get_corp()
            return corp.generate_post(topic=topic, author=author)
        return await asyncio.to_thread(_sync)

    @classmethod
    async def run_content_review(cls, content: str) -> str:
        """Review content with Yuki (SMM)."""
        def _sync():
            corp = cls._get_corp()
            return corp.content_review(content)
        return await asyncio.to_thread(_sync)

    @classmethod
    async def run_linkedin_status(cls) -> str:
        """Check LinkedIn status with Yuki (SMM)."""
        def _sync():
            corp = cls._get_corp()
            return corp.linkedin_status()
        return await asyncio.to_thread(_sync)
