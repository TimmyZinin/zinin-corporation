"""
Agent Improvement Advisor — proactive improvement system for Zinin Corp agents.

CTO Мартин reads agent YAMLs, researches best practices via web,
analyzes via free LLM, and generates structured improvement proposals.
"""

import json
import logging
import os
import time
from datetime import datetime
from typing import Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from .tech_tools import _call_llm_tech

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Agent names for iteration
# ──────────────────────────────────────────────────────────

_AGENT_NAMES = ["manager", "accountant", "automator", "yuki", "designer"]

_AGENT_LABELS = {
    "manager": "👑 Алексей (CEO)",
    "accountant": "🏦 Маттиас (CFO)",
    "automator": "⚙️ Мартин (CTO)",
    "yuki": "📱 Юки (SMM)",
    "designer": "🎨 Райан (Designer)",
}

_MODEL_COSTS = {
    "openrouter/anthropic/claude-sonnet-4": {"name": "Claude Sonnet 4", "tier": "sonnet", "cost_1k": 0.015},
    "openrouter/anthropic/claude-3-5-haiku-latest": {"name": "Claude 3.5 Haiku", "tier": "haiku", "cost_1k": 0.001},
    "openrouter/anthropic/claude-3.5-haiku": {"name": "Claude 3.5 Haiku", "tier": "haiku", "cost_1k": 0.001},
}


# ──────────────────────────────────────────────────────────
# Proposal Storage
# ──────────────────────────────────────────────────────────

def _proposals_path() -> str:
    for p in ["/app/data/cto_proposals.json", "data/cto_proposals.json"]:
        if os.path.isdir(os.path.dirname(p)):
            return p
    return "data/cto_proposals.json"


def _load_proposals() -> dict:
    path = _proposals_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {
        "proposals": [],
        "stats": {"total_generated": 0, "approved": 0, "rejected": 0, "conditions": 0},
        "last_run": None,
    }


def _save_proposals(data: dict):
    path = _proposals_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Cap at 200 proposals
    data["proposals"] = data["proposals"][-200:]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ──────────────────────────────────────────────────────────
# Agent YAML Reading
# ──────────────────────────────────────────────────────────

def _agent_yaml_dir() -> str:
    for d in ["/app/agents", "agents"]:
        if os.path.isdir(d):
            return d
    return "agents"


def _read_all_agent_yamls() -> dict:
    """Read all agent YAMLs. Returns {name: config_dict}."""
    import yaml

    result = {}
    base_dir = _agent_yaml_dir()
    for name in _AGENT_NAMES:
        path = os.path.join(base_dir, f"{name}.yaml")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    result[name] = yaml.safe_load(f) or {}
            except Exception as e:
                logger.warning(f"Failed to read {path}: {e}")
                result[name] = {"error": str(e)}
    return result


def _summarize_agent(name: str, config: dict) -> str:
    """Create concise summary of agent for LLM context."""
    label = _AGENT_LABELS.get(name, name)
    role = config.get("role", "?")
    llm = config.get("llm", "?")
    model_info = _MODEL_COSTS.get(llm, {"name": llm, "tier": "?", "cost_1k": 0})
    goal = config.get("goal", "")
    # Truncate backstory to first 500 chars for summary
    backstory = config.get("backstory", "")
    backstory_preview = backstory[:500] + "..." if len(backstory) > 500 else backstory

    max_iter = config.get("max_iter", "?")
    allow_delegation = config.get("allow_delegation", False)
    memory = config.get("memory", False)

    return (
        f"--- {label} ---\n"
        f"Role: {role}\n"
        f"Model: {model_info['name']} (tier: {model_info['tier']}, ~${model_info['cost_1k']}/1k tokens)\n"
        f"Max iterations: {max_iter}, Delegation: {allow_delegation}, Memory: {memory}\n"
        f"Goal: {goal[:300]}\n"
        f"Backstory preview: {backstory_preview}\n"
    )


# ──────────────────────────────────────────────────────────
# Web Research
# ──────────────────────────────────────────────────────────

def _research_best_practices(topic: str) -> list[dict]:
    """Search DuckDuckGo for best practices. Returns [{title, url, snippet}]."""
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        logger.warning("duckduckgo_search not installed, skipping web research")
        return []

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(
                f"CrewAI agent {topic} best practices prompt engineering 2025 2026",
                max_results=5,
            ))
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
            }
            for r in results
        ]
    except Exception as e:
        logger.warning(f"Web research failed: {e}")
        return []


# ──────────────────────────────────────────────────────────
# LLM Analysis Prompts
# ──────────────────────────────────────────────────────────

_IMPROVEMENT_SYSTEM = """Ты — эксперт по prompt engineering для мульти-агентных систем CrewAI.
Твоя задача — анализировать YAML-конфигурацию агента и предложить ОДНО конкретное улучшение.

Типы улучшений:
1. PROMPT — улучшение backstory, goal или инструкций
2. TOOL — предложение нового инструмента или улучшение использования существующих
3. MODEL_TIER — рекомендация сменить модель (haiku↔sonnet) с обоснованием стоимости

ФОРМАТ ОТВЕТА (строго JSON, без markdown):
{
    "proposal_type": "prompt или tool или model_tier",
    "title": "Краткий заголовок до 60 символов",
    "description": "Подробное описание на русском (200-400 слов)",
    "current_state": "Что сейчас и почему это проблема",
    "proposed_change": "Конкретное изменение с примером кода/текста",
    "confidence_score": 0.85,
    "reasoning": "Почему это улучшит агента"
}

ПРАВИЛА:
- Анализируй РЕАЛЬНЫЙ YAML. НЕ выдумывай проблемы.
- Если агент хорош — предложи мелкое улучшение с низким confidence (0.3-0.5).
- Всегда предлагай КОНКРЕТНЫЕ изменения, не общие слова.
- confidence_score: 0.9+ критично важное, 0.7-0.9 полезное, 0.5-0.7 желательное, <0.5 мелкое.
- Отвечай ТОЛЬКО валидным JSON, без объяснений до/после."""

_MODEL_AUDIT_SYSTEM = """Ты — эксперт по оптимизации затрат на LLM в мульти-агентных системах.
Анализируй каждого агента и определи, нужно ли менять уровень модели.

Claude Sonnet 4: ~$0.015/1k tokens — для сложного рассуждения, делегирования, стратегии
Claude 3.5 Haiku: ~$0.001/1k tokens — для рутинных задач, генерации контента, обработки данных

ФОРМАТ ОТВЕТА (строго JSON, без markdown):
{
    "recommendations": [
        {
            "agent": "имя_агента",
            "current_tier": "sonnet или haiku",
            "recommended_tier": "sonnet или haiku",
            "action": "keep или upgrade или downgrade",
            "reasoning": "Почему на русском",
            "estimated_monthly_saving_usd": 0.0
        }
    ],
    "summary": "Общий вывод на русском"
}

Отвечай ТОЛЬКО валидным JSON."""


# ──────────────────────────────────────────────────────────
# Tool: Agent Improvement Advisor
# ──────────────────────────────────────────────────────────

class ImprovementInput(BaseModel):
    action: str = Field(
        ...,
        description=(
            "Action: 'analyze' (analyze ONE agent and propose improvement), "
            "'analyze_all' (pick least-recently-improved agent and analyze), "
            "'list_proposals' (show recent proposals with statuses), "
            "'get_proposal' (get specific proposal by id), "
            "'model_audit' (audit model tiers for all agents), "
            "'self_reflect' (CTO analyzes himself)"
        ),
    )
    target_agent: Optional[str] = Field(
        None,
        description=f"Agent key for 'analyze'. Options: {', '.join(_AGENT_NAMES)}",
    )
    proposal_id: Optional[str] = Field(
        None,
        description="Proposal ID for 'get_proposal'",
    )


class AgentImprovementAdvisor(BaseTool):
    name: str = "Agent Improvement Advisor"
    description: str = (
        "Proactive agent improvement system. Reads agent YAML configs, "
        "researches best practices via web search, analyzes with LLM, "
        "and generates structured improvement proposals. "
        "Can analyze any agent including CTO himself. "
        "Actions: analyze, analyze_all, list_proposals, get_proposal, model_audit, self_reflect."
    )
    args_schema: Type[BaseModel] = ImprovementInput

    def _run(self, action: str, target_agent: str = None, proposal_id: str = None) -> str:
        if action == "analyze":
            return self._analyze_agent(target_agent)

        if action == "analyze_all":
            return self._analyze_least_recent()

        if action == "list_proposals":
            return self._list_proposals()

        if action == "get_proposal":
            return self._get_proposal(proposal_id)

        if action == "model_audit":
            return self._model_audit()

        if action == "self_reflect":
            return self._analyze_agent("automator")

        return (
            f"Unknown action: {action}. "
            "Use: analyze, analyze_all, list_proposals, get_proposal, model_audit, self_reflect"
        )

    # ── analyze ──

    def _analyze_agent(self, target_agent: str = None) -> str:
        if not target_agent:
            return f"Error: need target_agent. Options: {', '.join(_AGENT_NAMES)}"
        if target_agent not in _AGENT_NAMES:
            return f"Unknown agent: {target_agent}. Options: {', '.join(_AGENT_NAMES)}"

        agents = _read_all_agent_yamls()
        config = agents.get(target_agent, {})
        if not config or "error" in config:
            return f"Error reading YAML for {target_agent}: {config.get('error', 'not found')}"

        # Full YAML for analysis
        full_yaml = json.dumps(config, ensure_ascii=False, indent=2)
        if len(full_yaml) > 6000:
            full_yaml = full_yaml[:6000] + "\n... (truncated)"

        # Web research
        role = config.get("role", target_agent)
        research = _research_best_practices(role)
        research_text = ""
        if research:
            research_text = "\n\nBEST PRACTICES FROM WEB:\n"
            for r in research[:3]:
                research_text += f"- {r['title']}: {r['snippet'][:200]}\n"

        prompt = (
            f"Проанализируй агента '{_AGENT_LABELS.get(target_agent, target_agent)}' "
            f"и предложи ОДНО конкретное улучшение.\n\n"
            f"YAML CONFIG:\n```\n{full_yaml}\n```\n"
            f"{research_text}\n"
            f"Верни JSON с предложением."
        )

        llm_result = _call_llm_tech(prompt, system=_IMPROVEMENT_SYSTEM, max_tokens=2000)
        if not llm_result:
            return "❌ LLM недоступен для анализа. Проверь OPENROUTER_API_KEY."

        # Parse JSON from LLM response
        proposal_data = self._parse_proposal_json(llm_result)
        if not proposal_data:
            return f"❌ LLM вернул невалидный JSON. Raw:\n{llm_result[:500]}"

        # Create proposal
        now = datetime.now()
        proposal_id_str = f"prop_{now.strftime('%Y%m%d_%H%M')}_{target_agent}"
        proposal = {
            "id": proposal_id_str,
            "created_at": now.isoformat(),
            "target_agent": target_agent,
            "proposal_type": proposal_data.get("proposal_type", "prompt"),
            "title": proposal_data.get("title", "Без заголовка"),
            "description": proposal_data.get("description", ""),
            "current_state": proposal_data.get("current_state", ""),
            "proposed_change": proposal_data.get("proposed_change", ""),
            "research_sources": [r["url"] for r in research[:3]] if research else [],
            "confidence_score": min(max(float(proposal_data.get("confidence_score", 0.5)), 0.0), 1.0),
            "status": "pending",
            "conditions": "",
            "reviewed_at": None,
        }

        # Save
        data = _load_proposals()
        data["proposals"].append(proposal)
        data["stats"]["total_generated"] = data["stats"].get("total_generated", 0) + 1
        data["last_run"] = now.isoformat()
        _save_proposals(data)

        label = _AGENT_LABELS.get(target_agent, target_agent)
        type_labels = {"prompt": "📝 Промпт", "tool": "🔧 Инструмент", "model_tier": "🧠 Модель"}
        ptype = type_labels.get(proposal["proposal_type"], proposal["proposal_type"])

        return (
            f"═══ НОВОЕ ПРЕДЛОЖЕНИЕ ═══\n"
            f"ID: {proposal['id']}\n"
            f"Агент: {label}\n"
            f"Тип: {ptype}\n"
            f"Уверенность: {proposal['confidence_score']:.0%}\n\n"
            f"📋 {proposal['title']}\n\n"
            f"{proposal['description']}\n\n"
            f"Текущее состояние: {proposal['current_state']}\n\n"
            f"Предлагаемое изменение: {proposal['proposed_change']}"
        )

    # ── analyze_all ──

    def _analyze_least_recent(self) -> str:
        """Pick the agent that was least recently analyzed and run analyze."""
        data = _load_proposals()
        proposals = data.get("proposals", [])

        # Count proposals per agent
        last_analyzed = {}
        for p in proposals:
            agent = p.get("target_agent")
            ts = p.get("created_at", "")
            if agent and ts > last_analyzed.get(agent, ""):
                last_analyzed[agent] = ts

        # Find least recent (or never analyzed)
        target = None
        oldest_ts = None
        for name in _AGENT_NAMES:
            ts = last_analyzed.get(name)
            if ts is None:
                target = name
                break
            if oldest_ts is None or ts < oldest_ts:
                oldest_ts = ts
                target = name

        if not target:
            target = _AGENT_NAMES[0]

        return self._analyze_agent(target)

    # ── list_proposals ──

    def _list_proposals(self) -> str:
        data = _load_proposals()
        proposals = data.get("proposals", [])
        stats = data.get("stats", {})

        if not proposals:
            return (
                "Нет предложений. Запусти action='analyze_all' для генерации.\n"
                f"Статистика: {json.dumps(stats, ensure_ascii=False)}"
            )

        lines = [
            f"═══ ПРЕДЛОЖЕНИЯ ({len(proposals)} всего) ═══",
            f"Статистика: одобрено {stats.get('approved', 0)}, "
            f"отклонено {stats.get('rejected', 0)}, "
            f"с условиями {stats.get('conditions', 0)}",
            "",
        ]

        status_icons = {
            "pending": "⏳",
            "approved": "✅",
            "rejected": "❌",
            "conditions": "📝",
        }

        for p in proposals[-10:]:
            icon = status_icons.get(p.get("status"), "?")
            label = _AGENT_LABELS.get(p.get("target_agent", ""), p.get("target_agent", "?"))
            confidence = p.get("confidence_score", 0)
            lines.append(
                f"  {icon} [{p['id']}] {label} — {p.get('title', '?')} "
                f"(confidence: {confidence:.0%})"
            )

        return "\n".join(lines)

    # ── get_proposal ──

    def _get_proposal(self, proposal_id: str = None) -> str:
        if not proposal_id:
            return "Error: need proposal_id"
        data = _load_proposals()
        for p in data.get("proposals", []):
            if p.get("id") == proposal_id:
                return json.dumps(p, ensure_ascii=False, indent=2)
        return f"Proposal '{proposal_id}' not found."

    # ── model_audit ──

    def _model_audit(self) -> str:
        agents = _read_all_agent_yamls()
        summaries = []
        for name in _AGENT_NAMES:
            config = agents.get(name, {})
            if config and "error" not in config:
                summaries.append(_summarize_agent(name, config))

        prompt = (
            "Проведи аудит модельных тиров всех агентов Zinin Corp.\n"
            "Определи, кому стоит повысить/понизить модель.\n\n"
            "АГЕНТЫ:\n" + "\n".join(summaries) + "\n\n"
            "Верни JSON с рекомендациями."
        )

        result = _call_llm_tech(prompt, system=_MODEL_AUDIT_SYSTEM, max_tokens=2000)
        if not result:
            return "❌ LLM недоступен для аудита."

        # Try to parse JSON
        try:
            parsed = self._extract_json(result)
            if parsed:
                recs = parsed.get("recommendations", [])
                lines = ["═══ АУДИТ МОДЕЛЬНЫХ ТИРОВ ═══", ""]
                for rec in recs:
                    agent_label = _AGENT_LABELS.get(rec.get("agent", ""), rec.get("agent", "?"))
                    action = rec.get("action", "?")
                    action_icon = {"keep": "✅", "upgrade": "⬆️", "downgrade": "⬇️"}.get(action, "?")
                    lines.append(
                        f"  {action_icon} {agent_label}: {rec.get('current_tier', '?')} → "
                        f"{rec.get('recommended_tier', '?')} ({action})"
                    )
                    lines.append(f"    {rec.get('reasoning', '')}")
                    saving = rec.get("estimated_monthly_saving_usd", 0)
                    if saving:
                        lines.append(f"    Экономия: ~${saving:.2f}/мес")
                    lines.append("")

                summary = parsed.get("summary", "")
                if summary:
                    lines.append(f"Вывод: {summary}")
                return "\n".join(lines)
        except Exception:
            pass

        return f"═══ АУДИТ МОДЕЛЬНЫХ ТИРОВ ═══\n\n{result}"

    # ── helpers ──

    @staticmethod
    def _parse_proposal_json(text: str) -> Optional[dict]:
        """Extract and parse proposal JSON from LLM response."""
        # Try direct parse
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # Try extracting JSON from markdown code block
        for marker in ["```json", "```"]:
            if marker in text:
                start = text.index(marker) + len(marker)
                end = text.index("```", start) if "```" in text[start:] else len(text)
                try:
                    return json.loads(text[start:start + end - start].strip())
                except (json.JSONDecodeError, ValueError):
                    pass

        # Try finding { ... } block
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start >= 0 and brace_end > brace_start:
            try:
                return json.loads(text[brace_start:brace_end + 1])
            except json.JSONDecodeError:
                pass

        return None

    @staticmethod
    def _extract_json(text: str) -> Optional[dict]:
        """Same as _parse_proposal_json but for any JSON."""
        return AgentImprovementAdvisor._parse_proposal_json(text)
