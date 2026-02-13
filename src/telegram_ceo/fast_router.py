"""Fast Router — 0 LLM routing for CEO bot.

Routes 80%+ messages directly to the right agent without CEO LLM overhead.
Priority: intent detection → agent detection → fallback to manager.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from .nlu import detect_intent, detect_agent

logger = logging.getLogger(__name__)

INTENT_CONFIDENCE_THRESHOLD = 0.7
AGENT_CONFIDENCE_THRESHOLD = 0.6


@dataclass
class RouteResult:
    """Result of message routing."""
    route_type: str        # "intent", "agent", "fallback"
    agent_name: str        # agent key ("manager", "smm", "accountant", etc.)
    confidence: float      # routing confidence
    intent_command: Optional[str] = None  # e.g. "/status", "/help"


def route_message(text: str) -> RouteResult:
    """Route a message to the appropriate handler.

    Priority:
    1. Intent detection (>= 0.7) → redirect to command handler
    2. Agent detection (>= 0.6) → direct agent call
    3. Fallback → manager (CEO LLM)

    Returns RouteResult with routing decision.
    """
    # 1. Intent detection — maps to /command
    intent = detect_intent(text)
    if intent and intent.confidence >= INTENT_CONFIDENCE_THRESHOLD:
        logger.info(f"FastRouter: intent={intent.command} conf={intent.confidence:.2f}")
        return RouteResult(
            route_type="intent",
            agent_name="",
            confidence=intent.confidence,
            intent_command=intent.command,
        )

    # 2. Agent detection — direct routing
    agent_target = detect_agent(text)
    if agent_target and agent_target[1] >= AGENT_CONFIDENCE_THRESHOLD:
        agent_name, confidence = agent_target
        logger.info(f"FastRouter: agent={agent_name} conf={confidence:.2f}")
        return RouteResult(
            route_type="agent",
            agent_name=agent_name,
            confidence=confidence,
        )

    # 3. Fallback — CEO LLM
    logger.info("FastRouter: fallback to manager")
    return RouteResult(
        route_type="fallback",
        agent_name="manager",
        confidence=0.0,
    )
