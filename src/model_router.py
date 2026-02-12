"""
🧠 Zinin Corp — Smart Model Router

Routes tasks to appropriate LLM based on complexity:
- SIMPLE → Groq (Llama 3.3 70B) — fast, free
- MODERATE → Claude 3.5 Haiku — balanced
- COMPLEX → Claude Sonnet 4 — best quality

Feature flag: SMART_ROUTING_ENABLED env var (default: disabled).
Without GROQ_API_KEY, falls back to OpenRouter for all.
"""

import os
import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class TaskComplexity(str, Enum):
    SIMPLE = "simple"      # Quick responses, status checks, simple Q&A
    MODERATE = "moderate"  # Content generation, analysis, moderate tools
    COMPLEX = "complex"    # Strategic review, multi-agent, delegation, heavy tools


# Model configs per complexity tier
MODEL_TIERS = {
    TaskComplexity.SIMPLE: {
        "model": "groq/llama-3.3-70b-versatile",
        "description": "Groq Llama 3.3 70B — fast, free",
        "requires_key": "GROQ_API_KEY",
    },
    TaskComplexity.MODERATE: {
        "model": "openrouter/anthropic/claude-haiku-4-5-20251001",
        "description": "Claude 3.5 Haiku — balanced",
        "requires_key": "OPENROUTER_API_KEY",
    },
    TaskComplexity.COMPLEX: {
        "model": "openrouter/anthropic/claude-sonnet-4",
        "description": "Claude Sonnet 4 — best quality",
        "requires_key": "OPENROUTER_API_KEY",
    },
}

# Agent default complexity overrides
AGENT_COMPLEXITY = {
    "manager": TaskComplexity.COMPLEX,    # CEO always gets best model
    "accountant": TaskComplexity.COMPLEX,  # CFO handles finances — accuracy critical
    "automator": TaskComplexity.COMPLEX,   # CTO handles architecture — accuracy critical
    "smm": TaskComplexity.MODERATE,        # Content — good enough with Haiku
    "designer": TaskComplexity.MODERATE,   # Design descriptions — Haiku is fine
    "cpo": TaskComplexity.MODERATE,        # Product management — balanced
}

# Keywords that signal complex tasks
COMPLEX_KEYWORDS = {
    "стратеги", "strategy", "обзор", "review", "отчёт", "отчет", "report",
    "делегир", "delegate", "бюджет", "budget", "портфел", "portfolio",
    "аудит", "audit", "архитектур", "architecture", "миграци", "migration",
}

# Keywords that signal simple tasks
SIMPLE_KEYWORDS = {
    "статус", "status", "баланс", "balance", "помощь", "help",
    "время", "time", "привет", "hello", "hi", "здравствуй",
    "список", "list", "покажи", "show",
}


def is_smart_routing_enabled() -> bool:
    """Check if smart routing is enabled via feature flag."""
    return os.getenv("SMART_ROUTING_ENABLED", "").lower() in ("1", "true", "yes")


def assess_complexity(
    message: str,
    agent_name: str = "",
    has_delegation: bool = False,
    tool_count: int = 0,
) -> TaskComplexity:
    """Assess task complexity based on message and context.

    Args:
        message: User message text
        agent_name: Target agent name
        has_delegation: Whether agent has delegation capability
        tool_count: Number of tools agent has

    Returns:
        TaskComplexity enum value
    """
    # Agent override takes priority
    if agent_name in AGENT_COMPLEXITY:
        base_complexity = AGENT_COMPLEXITY[agent_name]
    else:
        base_complexity = TaskComplexity.MODERATE

    # Delegation = always complex
    if has_delegation:
        return TaskComplexity.COMPLEX

    # Many tools = at least moderate
    if tool_count > 10:
        base_complexity = max(base_complexity, TaskComplexity.MODERATE, key=_complexity_rank)

    # Check message keywords
    msg_lower = message.lower()

    for kw in COMPLEX_KEYWORDS:
        if kw in msg_lower:
            return TaskComplexity.COMPLEX

    for kw in SIMPLE_KEYWORDS:
        if kw in msg_lower:
            return min(base_complexity, TaskComplexity.SIMPLE, key=_complexity_rank)

    # Short messages are likely simple
    if len(message) < 30:
        return min(base_complexity, TaskComplexity.MODERATE, key=_complexity_rank)

    # Long messages are likely complex
    if len(message) > 300:
        return max(base_complexity, TaskComplexity.MODERATE, key=_complexity_rank)

    return base_complexity


def select_model(
    complexity: TaskComplexity,
    agent_config: Optional[dict] = None,
) -> str:
    """Select the appropriate model for the given complexity.

    Falls back to OpenRouter if required API key is missing.

    Args:
        complexity: Task complexity level
        agent_config: Optional agent-specific config with 'llm' key

    Returns:
        Model identifier string (e.g., 'groq/llama-3.3-70b-versatile')
    """
    if not is_smart_routing_enabled():
        # When disabled, use agent's configured model or default
        if agent_config and "llm" in agent_config:
            return agent_config["llm"]
        return "openrouter/anthropic/claude-sonnet-4"

    tier = MODEL_TIERS[complexity]

    # Check if required API key is available
    required_key = tier["requires_key"]
    if not os.getenv(required_key):
        # Fall back to OpenRouter
        logger.info(
            f"Smart routing: {required_key} not set, "
            f"falling back to OpenRouter for {complexity.value}"
        )
        if complexity == TaskComplexity.SIMPLE:
            # No Groq key → use Haiku instead
            return MODEL_TIERS[TaskComplexity.MODERATE]["model"]
        return tier["model"]

    logger.info(f"Smart routing: {complexity.value} → {tier['model']}")
    return tier["model"]


def get_routing_summary() -> str:
    """Get a text summary of current routing configuration."""
    enabled = is_smart_routing_enabled()
    groq_available = bool(os.getenv("GROQ_API_KEY"))
    openrouter_available = bool(os.getenv("OPENROUTER_API_KEY"))

    lines = [
        f"🧠 Smart Model Routing: {'ON' if enabled else 'OFF'}",
        f"  Groq API: {'✅' if groq_available else '❌'}",
        f"  OpenRouter API: {'✅' if openrouter_available else '❌'}",
        "",
        "Тиры:",
    ]

    for complexity, tier in MODEL_TIERS.items():
        key_ok = bool(os.getenv(tier["requires_key"]))
        status = "✅" if key_ok else "⚠️ fallback"
        lines.append(f"  {complexity.value}: {tier['description']} [{status}]")

    return "\n".join(lines)


def _complexity_rank(c: TaskComplexity) -> int:
    """Numeric rank for comparison."""
    return {
        TaskComplexity.SIMPLE: 0,
        TaskComplexity.MODERATE: 1,
        TaskComplexity.COMPLEX: 2,
    }[c]
