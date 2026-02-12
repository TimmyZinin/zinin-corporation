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
        """Send a message to a CrewAI agent (runs in thread).

        Also tracks delegation as a task in the Shared Task Pool.
        """
        task_desc = message
        if chat_context:
            task_desc = (
                f"{chat_context}\n\n"
                f"---\nНовое сообщение от Тима: {message}"
            )

        if bot and chat_id:
            cls._setup_progress(bot, chat_id)

        # Track in Task Pool
        pool_task = cls._track_delegation(message, agent_name)

        def _sync():
            print(f"[Bridge] _sync: agent={agent_name}, msg={message[:60]}", flush=True)
            corp = cls._get_corp()
            print(f"[Bridge] _sync: corp ready, calling execute_task...", flush=True)
            result = corp.execute_task(task_desc, agent_name, use_memory=True)
            print(f"[Bridge] _sync: done, {len(result)} chars", flush=True)
            return result

        try:
            result = await asyncio.to_thread(_sync)
            cls._complete_delegation(pool_task, result)
            return result
        except Exception as e:
            cls._complete_delegation(pool_task, f"ERROR: {e}")
            raise
        finally:
            cls._clear_progress()

    @classmethod
    def _track_delegation(cls, message: str, agent_name: str):
        """Create a task in the Task Pool for this delegation."""
        try:
            from ..task_pool import create_task
            title = message[:100] + ("..." if len(message) > 100 else "")
            return create_task(
                title=title,
                assignee=agent_name,
                assigned_by="ceo-alexey",
                source="delegation",
            )
        except Exception as e:
            logger.debug(f"Task pool tracking skipped: {e}")
            return None

    @classmethod
    def _complete_delegation(cls, pool_task, result: str):
        """Mark delegation task as complete in the Task Pool."""
        if pool_task is None:
            return
        try:
            from ..task_pool import start_task, complete_task
            start_task(pool_task.id)
            result_preview = result[:500] if result else ""
            complete_task(pool_task.id, result=result_preview)
        except Exception as e:
            logger.debug(f"Task pool completion skipped: {e}")

    @classmethod
    async def run_financial_report(cls) -> str:
        def _sync():
            corp = cls._get_corp()
            return corp.execute_task(
                "Подготовь полный финансовый отчёт.\n"
                "1. Вызови full_portfolio — он сам соберёт данные по банкам, крипте и доходам\n"
                "2. Вызови openrouter_usage для расходов на AI\n"
                "3. НЕ вызывай другие инструменты — full_portfolio уже включает их данные\n"
                "Дай сводку: активы, доходы, расходы на AI, рекомендации.",
                "accountant",
                use_memory=False,
            )
        return await asyncio.to_thread(_sync)

    @classmethod
    async def run_portfolio_summary(cls) -> str:
        def _sync():
            corp = cls._get_corp()
            return corp.execute_task(
                "Подготовь сводку портфеля. Используй full_portfolio.",
                "accountant",
                use_memory=False,
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
    async def run_generate_podcast(cls, topic: str = "", duration_minutes: int = 10) -> str:
        """Generate a podcast script with Yuki (SMM)."""
        def _sync():
            corp = cls._get_corp()
            return corp.generate_podcast(topic=topic, duration_minutes=duration_minutes)
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

    @classmethod
    async def run_generate_design(cls, task: str = "", brand: str = "corporation") -> str:
        """Generate design/visual content with Ryan (Designer)."""
        def _sync():
            corp = cls._get_corp()
            return corp.generate_design(task=task, brand=brand)
        return await asyncio.to_thread(_sync)

    @classmethod
    async def run_api_health_report(cls) -> str:
        """Run comprehensive API health check with Мартин (CTO)."""
        def _sync():
            corp = cls._get_corp()
            return corp.api_health_report()
        return await asyncio.to_thread(_sync)

    @classmethod
    async def run_cto_proposal(cls) -> dict:
        """CTO generates one improvement proposal (for scheduler)."""
        def _sync():
            corp = cls._get_corp()
            return corp.cto_generate_proposal()
        return await asyncio.to_thread(_sync)

    @classmethod
    async def run_linkedin_publish(cls, text: str, image_path: str = "") -> str:
        """Publish to LinkedIn via Yuki's tool."""
        def _sync():
            corp = cls._get_corp()
            task = (
                f"Опубликуй этот пост в LinkedIn. Используй инструмент linkedin_publish.\n\n"
                f"Текст поста:\n{text}\n"
            )
            if image_path:
                task += f"\nПуть к картинке: {image_path}\n"
            return corp.execute_task(task, "smm", use_memory=False)
        return await asyncio.to_thread(_sync)
