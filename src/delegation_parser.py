"""
🔄 Zinin Corp — Delegation Parser

Parses agent responses for delegation patterns.
When an agent (e.g. CEO Alexey) delegates a task to another agent
(e.g. CFO Matthias), this module extracts the delegation so that
the target agent can be automatically invoked.
"""

import re
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# Agent name patterns for delegation detection (dative/accusative/nominative)
DELEGATION_AGENT_PATTERNS: Dict[str, List[str]] = {
    "manager": ["алексей", "алексею", "алексея", "алексеем"],
    "accountant": ["маттиас", "маттиасу", "маттиаса", "маттиасом"],
    "automator": ["мартин", "мартину", "мартина", "мартином"],
    "smm": ["юки"],
}

# Delegation verb patterns (Russian)
DELEGATION_VERBS = [
    r"поруча\w+",
    r"делегиру\w+",
    r"прошу\s+\w*\s*подготов",
    r"прошу\s+\w*\s*сделат",
    r"прошу\s+\w*\s*провест",
    r"прошу\s+\w*\s*проанализ",
    r"долж(?:ен|на|ны)\s+подготов",
    r"долж(?:ен|на|ны)\s+сделат",
    r"долж(?:ен|на|ны)\s+провест",
    r"долж(?:ен|на|ны)\s+проанализ",
    r"необходимо.*подготов",
    r"необходимо.*провест",
    r"нужно.*подготов",
    r"нужно.*провест",
    r"@\s*маттиас",
    r"@\s*мартин",
    r"@\s*юки",
    r"@\s*алексей",
]


def _detect_target_agent(text: str) -> str:
    """Detect which agent is being delegated to in a text fragment."""
    text_lower = text.lower()
    for agent_key, patterns in DELEGATION_AGENT_PATTERNS.items():
        for pattern in patterns:
            if pattern in text_lower:
                return agent_key
    return ""


def _has_delegation_verb(text: str) -> bool:
    """Check if text contains a delegation verb."""
    text_lower = text.lower()
    for pattern in DELEGATION_VERBS:
        if re.search(pattern, text_lower):
            return True
    return False


def _extract_task_description(text: str, agent_key: str) -> str:
    """Extract task description from delegation text."""
    # Remove list numbering
    cleaned = re.sub(r"^\d+[\.\)\-]\s*", "", text.strip())
    # Remove leading bullet/dash
    cleaned = re.sub(r"^[-•*]\s*", "", cleaned)
    return cleaned


def parse_delegations(text: str, source_agent: str) -> List[Dict]:
    """Parse agent response text for delegation patterns.

    Args:
        text: The agent's response text
        source_agent: The agent_key of the agent who wrote the response

    Returns:
        List of dicts with keys: agent_key, task_description
        Empty list if no delegations found.
    """
    if not text or not text.strip():
        return []

    delegations = []
    seen_agents = set()
    lines = text.split("\n")

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped or len(line_stripped) < 10:
            continue

        target = _detect_target_agent(line_stripped)
        if not target:
            continue

        # Skip self-delegation
        if target == source_agent:
            continue

        # Skip duplicate delegation to same agent
        if target in seen_agents:
            continue

        # Check for delegation verb
        if _has_delegation_verb(line_stripped):
            task_desc = _extract_task_description(line_stripped, target)
            delegations.append({
                "agent_key": target,
                "task_description": task_desc,
            })
            seen_agents.add(target)

    return delegations
