"""
🏢 AI Corporation — Agents Module
"""

import os
import yaml
import traceback
from typing import Optional
from crewai import Agent, LLM


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


def create_manager_agent() -> Optional[Agent]:
    """Create the Manager agent"""
    config = load_agent_config("manager")
    if not config:
        print("ERROR: manager.yaml not found")
        return None

    try:
        model = config.get("llm", "openrouter/anthropic/claude-sonnet-4")
        llm = create_llm(model)
        return Agent(
            role=config.get("role", "Управленец-Автоматизатор"),
            goal=config.get("goal", "Координировать работу всех агентов"),
            backstory=config.get("backstory", "Ты — CEO AI-корпорации"),
            llm=llm,
            verbose=True,
            memory=False,
            allow_delegation=True,
            max_iter=15,
        )
    except Exception as e:
        print(f"ERROR creating manager: {e}")
        traceback.print_exc()
        return None


def create_accountant_agent() -> Optional[Agent]:
    """Create the Accountant agent"""
    config = load_agent_config("accountant")
    if not config:
        print("ERROR: accountant.yaml not found")
        return None

    try:
        model = config.get("llm", "openrouter/anthropic/claude-3.5-haiku")
        llm = create_llm(model)
        return Agent(
            role=config.get("role", "Бухгалтер-аналитик"),
            goal=config.get("goal", "Вести финансовый учёт AI-корпорации"),
            backstory=config.get("backstory", "Ты — финансовый директор"),
            llm=llm,
            verbose=True,
            memory=False,
            allow_delegation=False,
            max_iter=10,
        )
    except Exception as e:
        print(f"ERROR creating accountant: {e}")
        traceback.print_exc()
        return None


def create_automator_agent() -> Optional[Agent]:
    """Create the Automator agent"""
    config = load_agent_config("automator")
    if not config:
        print("ERROR: automator.yaml not found")
        return None

    try:
        model = config.get("llm", "openrouter/anthropic/claude-sonnet-4")
        llm = create_llm(model)
        return Agent(
            role=config.get("role", "Автоматизатор-интегратор"),
            goal=config.get("goal", "Настраивать технические интеграции"),
            backstory=config.get("backstory", "Ты — технический директор"),
            llm=llm,
            verbose=True,
            memory=False,
            allow_delegation=False,
            max_iter=15,
        )
    except Exception as e:
        print(f"ERROR creating automator: {e}")
        traceback.print_exc()
        return None
