"""Bridge between async Telegram and sync CrewAI agents."""

import asyncio
import logging
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class AgentBridge:
    """Async wrapper around AICorporation.execute_task()."""

    _corp = None
    _bot = None
    _chat_id = None
    _loop = None

    @classmethod
    def _get_corp(cls):
        if cls._corp is None:
            print("[Bridge] creating AICorporation (first call)...", flush=True)
            from ..crew import get_corporation
            cls._corp = get_corporation()
            print("[Bridge] AICorporation created", flush=True)
        if not cls._corp.is_ready:
            print("[Bridge] initializing corporation...", flush=True)
            cls._corp.initialize()
            print(f"[Bridge] corporation ready={cls._corp.is_ready}", flush=True)
        return cls._corp

    @classmethod
    def _setup_progress(cls, bot, chat_id: int):
        """Setup progress message sending for the current request."""
        from ..crew import set_progress_callback

        cls._bot = bot
        cls._chat_id = chat_id
        cls._loop = asyncio.get_event_loop()

        def _sync_send_progress(text: str):
            """Send a Telegram message from sync thread via event loop."""
            if cls._bot and cls._chat_id and cls._loop:
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        cls._bot.send_message(cls._chat_id, text),
                        cls._loop,
                    )
                    future.result(timeout=10)
                except Exception as e:
                    logger.warning(f"Progress send failed: {e}")

        set_progress_callback(_sync_send_progress)

    @classmethod
    def _clear_progress(cls):
        """Clear progress callback after request completes."""
        from ..crew import set_progress_callback
        set_progress_callback(None)

    @classmethod
    async def send_to_agent(
        cls,
        message: str,
        agent_name: str = "accountant",
        chat_context: str = "",
        bot=None,
        chat_id: int = None,
    ) -> str:
        """Send a message to a CrewAI agent (runs in thread)."""
        task_desc = message
        if chat_context:
            task_desc = (
                f"{chat_context}\n\n"
                f"---\nНовое сообщение от Тима: {message}"
            )

        if bot and chat_id:
            cls._setup_progress(bot, chat_id)

        def _sync():
            print(f"[Bridge] _sync: agent={agent_name}, msg={message[:60]}", flush=True)
            corp = cls._get_corp()
            print(f"[Bridge] _sync: corp ready, calling execute_task...", flush=True)
            result = corp.execute_task(task_desc, agent_name, use_memory=False)
            print(f"[Bridge] _sync: done, {len(result)} chars", flush=True)
            return result

        try:
            return await asyncio.to_thread(_sync)
        finally:
            cls._clear_progress()

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
    async def run_strategic_review(cls, bot=None, chat_id: int = None) -> str:
        """Run strategic review: Маттиас + Мартин → Алексей synthesis."""
        if bot and chat_id:
            cls._setup_progress(bot, chat_id)

        def _sync():
            corp = cls._get_corp()
            return corp.strategic_review()

        try:
            return await asyncio.to_thread(_sync)
        finally:
            cls._clear_progress()

    @classmethod
    async def run_corporation_report(cls, bot=None, chat_id: int = None) -> str:
        """Run full corporation report: all agents → CEO synthesis."""
        if bot and chat_id:
            cls._setup_progress(bot, chat_id)

        def _sync():
            corp = cls._get_corp()
            return corp.full_corporation_report()

        try:
            return await asyncio.to_thread(_sync)
        finally:
            cls._clear_progress()

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
