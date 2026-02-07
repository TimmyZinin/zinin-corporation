"""
🏢 AI Corporation — Agents Module
"""

import os
import logging
import yaml
from typing import Optional
from crewai import Agent, LLM

logger = logging.getLogger(__name__)


def load_agent_config(agent_name: str) -> dict:
    """Load agent configuration from YAML file"""
    paths = [
        f"/app/agents/{agent_name}.yaml",
        f"agents/{agent_name}.yaml",
    ]
    for path in paths:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
    return {}


def create_llm(model: str) -> LLM:
    """Create LLM instance for OpenRouter"""
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    return LLM(
        model=model,
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )


def _load_web_tools() -> list:
    """Load web search tools (shared by multiple agents)"""
    try:
        from .tools.web_tools import WebSearchTool, WebPageReaderTool
        return [WebSearchTool(), WebPageReaderTool()]
    except Exception as e:
        logger.warning(f"Could not load web tools: {e}")
        return []


def create_manager_agent() -> Optional[Agent]:
    """Create the Manager agent with web search"""
    config = load_agent_config("manager")
    if not config:
        logger.error("manager.yaml not found")
        return None

    tools = _load_web_tools()

    try:
        model = config.get("llm", "openrouter/anthropic/claude-sonnet-4")
        llm = create_llm(model)
        return Agent(
            role=config.get("role", "Управленец-Автоматизатор"),
            goal=config.get("goal", "Координировать работу всех агентов"),
            backstory=config.get("backstory", "Ты — CEO AI-корпорации"),
            llm=llm,
            tools=tools,
            verbose=True,
            memory=False,
            allow_delegation=True,
            max_iter=15,
            max_retry_limit=3,
        )
    except Exception as e:
        logger.error(f"Error creating manager: {e}", exc_info=True)
        return None


def create_accountant_agent() -> Optional[Agent]:
    """Create the Accountant (Маттиас) agent with financial tools"""
    config = load_agent_config("accountant")
    if not config:
        logger.error("accountant.yaml not found")
        return None

    try:
        from .tools.financial_tools import (
            FinancialTracker,
            SubscriptionMonitor,
            APIUsageTracker,
        )
        tools = [FinancialTracker(), SubscriptionMonitor(), APIUsageTracker()]
    except Exception as e:
        logger.warning(f"Could not load financial tools: {e}")
        tools = []

    try:
        model = config.get("llm", "openrouter/anthropic/claude-3.5-haiku")
        llm = create_llm(model)
        return Agent(
            role=config.get("role", "CFO Маттиас Бруннер"),
            goal=config.get("goal", "Максимизировать прибыль и контролировать расходы"),
            backstory=config.get("backstory", "Ты — финансовый директор AI-корпорации"),
            llm=llm,
            tools=tools,
            verbose=True,
            memory=False,
            allow_delegation=False,
            max_iter=10,
            max_retry_limit=3,
        )
    except Exception as e:
        logger.error(f"Error creating accountant: {e}", exc_info=True)
        return None


def create_smm_agent() -> Optional[Agent]:
    """Create the SMM (Yuki) agent with content tools"""
    config = load_agent_config("yuki")
    if not config:
        logger.error("yuki.yaml not found")
        return None

    try:
        from .tools.smm_tools import ContentGenerator, YukiMemory, LinkedInPublisherTool
        tools = [ContentGenerator(), YukiMemory(), LinkedInPublisherTool()]
    except Exception as e:
        logger.warning(f"Could not load smm tools: {e}")
        tools = []

    try:
        model = config.get("llm", "openrouter/anthropic/claude-3.5-haiku")
        llm = create_llm(model)
        return Agent(
            role=config.get("role", "SMM-менеджер Юки"),
            goal=config.get("goal", "Создавать высококачественный контент"),
            backstory=config.get("backstory", "Ты — Юки, SMM-менеджер AI-корпорации"),
            llm=llm,
            tools=tools,
            verbose=True,
            memory=False,
            allow_delegation=False,
            max_iter=10,
            max_retry_limit=3,
        )
    except Exception as e:
        logger.error(f"Error creating smm agent: {e}", exc_info=True)
        return None


def create_automator_agent() -> Optional[Agent]:
    """Create the Automator (Мартин) agent with tech tools"""
    config = load_agent_config("automator")
    if not config:
        logger.error("automator.yaml not found")
        return None

    try:
        from .tools.tech_tools import SystemHealthChecker, IntegrationManager
        tools = [SystemHealthChecker(), IntegrationManager()] + _load_web_tools()
    except Exception as e:
        logger.warning(f"Could not load tech tools: {e}")
        tools = _load_web_tools()

    try:
        model = config.get("llm", "openrouter/anthropic/claude-sonnet-4")
        llm = create_llm(model)
        return Agent(
            role=config.get("role", "CTO Мартин Эчеверрия"),
            goal=config.get("goal", "Обеспечивать техническую инфраструктуру"),
            backstory=config.get("backstory", "Ты — технический директор"),
            llm=llm,
            tools=tools,
            verbose=True,
            memory=False,
            allow_delegation=False,
            max_iter=20,
            max_retry_limit=3,
        )
    except Exception as e:
        logger.error(f"Error creating automator: {e}", exc_info=True)
        return None
