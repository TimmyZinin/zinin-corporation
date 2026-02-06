"""
🏢 AI Corporation — Agents Module
Defines and configures all AI agents for the corporation
"""

import os
import yaml
from typing import Optional
from crewai import Agent
from crewai.tools import (
    FileReadTool,
    FileWriterTool,
    DirectoryReadTool,
)


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


def create_manager_agent() -> Optional[Agent]:
    """Create the Manager (Управленец) agent"""
    config = load_agent_config("manager")
    if not config:
        return None

    # Define tools for Manager
    tools = [
        FileReadTool(),
        FileWriterTool(),
        DirectoryReadTool(),
    ]

    return Agent(
        role=config.get("role", "Управленец-Автоматизатор"),
        goal=config.get("goal", "Координировать работу всех агентов"),
        backstory=config.get("backstory", "Ты — CEO AI-корпорации"),
        llm=config.get("llm", "openrouter/anthropic/claude-sonnet-4-20250514"),
        verbose=config.get("verbose", True),
        memory=config.get("memory", True),
        allow_delegation=config.get("allow_delegation", True),
        max_iter=config.get("max_iter", 15),
        max_rpm=config.get("max_rpm", 10),
        tools=tools,
    )


def create_accountant_agent() -> Optional[Agent]:
    """Create the Accountant (Бухгалтер) agent"""
    config = load_agent_config("accountant")
    if not config:
        return None

    tools = [
        FileReadTool(),
        FileWriterTool(),
    ]

    return Agent(
        role=config.get("role", "Бухгалтер-аналитик"),
        goal=config.get("goal", "Вести финансовый учёт AI-корпорации"),
        backstory=config.get("backstory", "Ты — финансовый директор"),
        llm=config.get("llm", "openrouter/anthropic/claude-3-5-haiku-latest"),
        verbose=config.get("verbose", True),
        memory=config.get("memory", True),
        allow_delegation=config.get("allow_delegation", False),
        max_iter=config.get("max_iter", 10),
        max_rpm=config.get("max_rpm", 15),
        tools=tools,
    )


def create_automator_agent() -> Optional[Agent]:
    """Create the Automator (Автоматизатор) agent"""
    config = load_agent_config("automator")
    if not config:
        return None

    tools = [
        FileReadTool(),
        FileWriterTool(),
        DirectoryReadTool(),
    ]

    return Agent(
        role=config.get("role", "Автоматизатор-интегратор"),
        goal=config.get("goal", "Настраивать технические интеграции"),
        backstory=config.get("backstory", "Ты — технический директор"),
        llm=config.get("llm", "openrouter/anthropic/claude-sonnet-4-20250514"),
        verbose=config.get("verbose", True),
        memory=config.get("memory", True),
        allow_delegation=config.get("allow_delegation", False),
        max_iter=config.get("max_iter", 15),
        max_rpm=config.get("max_rpm", 10),
        tools=tools,
    )


def get_all_agents() -> dict:
    """Get all configured agents"""
    return {
        "manager": create_manager_agent(),
        "accountant": create_accountant_agent(),
        "automator": create_automator_agent(),
    }
