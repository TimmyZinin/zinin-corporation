"""
⚖️ Zinin Corp — LLM-as-Judge
Quality scoring for agent responses using free LLM (Llama 3.3 70B).
Non-blocking: failures are logged but never break the response flow.
"""

import json
import logging
import re
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ── Judge result model ────────────────────────────────────

class JudgeResult(BaseModel):
    """Quality assessment from LLM judge."""
    relevance: int = Field(default=3, ge=1, le=5, description="Насколько ответ соответствует запросу (1-5)")
    completeness: int = Field(default=3, ge=1, le=5, description="Полнота ответа (1-5)")
    accuracy: int = Field(default=3, ge=1, le=5, description="Достоверность данных (1-5)")
    format_score: int = Field(default=3, ge=1, le=5, description="Соответствие формату (1-5)")
    overall: float = Field(default=3.0, ge=1.0, le=5.0, description="Общая оценка (средневзвешенная)")
    feedback: str = Field(default="", description="Краткая обратная связь (1-2 предложения)")
    passed: bool = Field(default=True, description="Прошёл ли порог качества (overall >= 3.0)")


# ── Judge prompt ──────────────────────────────────────────

_JUDGE_SYSTEM = """You are a strict quality judge for AI agent responses in a corporate AI system.
You evaluate responses on 4 dimensions, each scored 1-5:
- relevance: Does the response address the user's actual request?
- completeness: Is the answer thorough? Does it cover all aspects?
- accuracy: Are facts, numbers, and data points real (not fabricated)?
- format: Does it follow formatting guidelines (concise, structured, no fluff)?

CRITICAL RULES:
- Score 1-2 = poor (vague, fabricated data, off-topic, wall of text)
- Score 3 = acceptable (addresses topic but missing details)
- Score 4 = good (solid, data-backed, well-formatted)
- Score 5 = excellent (concise, actionable, real data, perfect format)

ACCURACY red flags (score 1-2):
- Generic placeholder numbers ($100K, 50%, etc.) without context
- "Approximately" with round numbers when specifics should be available
- Self-introduction or backstory instead of answering the question
- Promises to do something instead of actually doing it

You MUST respond with ONLY a JSON object, no other text:
{"relevance": N, "completeness": N, "accuracy": N, "format_score": N, "feedback": "..."}
"""

_JUDGE_PROMPT = """Evaluate this agent response:

TASK: {task}

AGENT ({agent_name}) RESPONSE:
{response}

Return ONLY JSON: {{"relevance": N, "completeness": N, "accuracy": N, "format_score": N, "feedback": "..."}}"""


# ── Core judge function ───────────────────────────────────

def judge_response(
    task_description: str,
    agent_response: str,
    agent_name: str = "unknown",
) -> Optional[JudgeResult]:
    """Score agent response quality using free LLM.

    Returns JudgeResult or None if judge is unavailable.
    Never raises — all errors are caught and logged.
    """
    if not agent_response or len(agent_response.strip()) < 20:
        return JudgeResult(
            relevance=1, completeness=1, accuracy=1, format_score=1,
            overall=1.0, feedback="Response too short or empty", passed=False,
        )

    try:
        from .tech_tools import _call_llm_tech
    except ImportError:
        logger.warning("llm_judge: _call_llm_tech not available")
        return None

    # Truncate long inputs to save tokens
    task_short = task_description[:500]
    response_short = agent_response[:2000]

    prompt = _JUDGE_PROMPT.format(
        task=task_short,
        agent_name=agent_name,
        response=response_short,
    )

    try:
        raw = _call_llm_tech(prompt, system=_JUDGE_SYSTEM, max_tokens=300)
        if not raw:
            logger.warning("llm_judge: empty response from LLM")
            return None

        scores = _parse_judge_response(raw)
        if not scores:
            logger.warning(f"llm_judge: failed to parse response: {raw[:200]}")
            return None

        # Calculate weighted average
        overall = (
            scores.get("relevance", 3) * 0.30
            + scores.get("completeness", 3) * 0.25
            + scores.get("accuracy", 3) * 0.30
            + scores.get("format_score", 3) * 0.15
        )
        overall = round(min(max(overall, 1.0), 5.0), 2)

        result = JudgeResult(
            relevance=_clamp(scores.get("relevance", 3)),
            completeness=_clamp(scores.get("completeness", 3)),
            accuracy=_clamp(scores.get("accuracy", 3)),
            format_score=_clamp(scores.get("format_score", 3)),
            overall=overall,
            feedback=scores.get("feedback", ""),
            passed=overall >= 3.0,
        )

        logger.info(
            f"llm_judge [{agent_name}]: overall={result.overall} "
            f"(rel={result.relevance} comp={result.completeness} "
            f"acc={result.accuracy} fmt={result.format_score}) "
            f"passed={result.passed}"
        )
        return result

    except Exception as e:
        logger.warning(f"llm_judge: error scoring response: {e}")
        return None


# ── Helpers ───────────────────────────────────────────────

def _clamp(value, lo=1, hi=5) -> int:
    """Clamp integer to [lo, hi] range."""
    try:
        return max(lo, min(hi, int(value)))
    except (ValueError, TypeError):
        return 3


def _parse_judge_response(raw: str) -> Optional[dict]:
    """Extract JSON from judge LLM response. Handles markdown fences."""
    # Try direct JSON parse
    text = raw.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    # Try to find JSON object
    match = re.search(r"\{[^}]+\}", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            # Validate expected keys
            if "relevance" in data or "completeness" in data:
                return data
        except json.JSONDecodeError:
            pass

    # Fallback: try full text
    try:
        data = json.loads(text)
        if "relevance" in data or "completeness" in data:
            return data
        return None
    except json.JSONDecodeError:
        return None
