"""Apply approved CTO proposals to agent YAML configs.

After CEO approves a proposal, this module:
1. Reads the target agent YAML
2. Applies the proposed change (prompt, model_tier, or tool)
3. Validates the result
4. Computes a real diff
5. Saves the modified YAML
"""

import difflib
import html
import logging
import os
import re
from typing import Optional

import yaml

from .improvement_advisor import _agent_yaml_dir
from .tech_tools import _call_llm_tech

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────

_REQUIRED_YAML_KEYS = {"role", "goal", "backstory", "llm"}

_TIER_TO_MODEL = {
    "sonnet": "openrouter/anthropic/claude-sonnet-4",
    "haiku": "openrouter/anthropic/claude-3-5-haiku-latest",
}

_APPLY_PROMPT_SYSTEM = (
    "Ты — инженер промптов для мульти-агентных систем CrewAI.\n"
    "Тебе дан текущий текст поля YAML-агента и описание изменения.\n\n"
    "ЗАДАЧА: применить описанное изменение к тексту и вернуть ПОЛНЫЙ НОВЫЙ текст поля.\n\n"
    "ПРАВИЛА:\n"
    "1. Верни ТОЛЬКО новый текст поля — без кавычек, без имени поля, без YAML-разметки\n"
    "2. Сохрани ВСЕ существующие секции и структуру, которые не затронуты изменением\n"
    "3. Изменяй ТОЛЬКО то, что описано в предложении\n"
    "4. Сохрани стиль, тон и язык оригинала\n"
    "5. НЕ добавляй комментарии о том, что ты изменил\n"
    "6. НЕ добавляй маркеры типа [НОВОЕ] или [ИЗМЕНЕНО]\n"
    "7. Текст на русском языке\n"
    "8. НЕ выдумывай данные. Применяй ТОЛЬКО то, что описано в предложении."
)


# ──────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────

def apply_proposal(proposal: dict) -> dict:
    """Apply an approved proposal to the target agent's YAML.

    Returns:
        {"applied": bool, "diff": str, "message": str}
    """
    ptype = proposal.get("proposal_type", "prompt")

    # Tool proposals require manual code changes
    if ptype == "tool":
        return {
            "applied": False,
            "diff": "",
            "message": (
                "Предложение инструмента одобрено. Требуется ручная реализация:\n"
                f"{proposal.get('proposed_change', '—')}"
            ),
        }

    agent_name = proposal.get("target_agent", "")
    yaml_path = os.path.join(_agent_yaml_dir(), f"{agent_name}.yaml")

    if not os.path.exists(yaml_path):
        raise FileNotFoundError(f"YAML not found: {yaml_path}")

    # Read original
    with open(yaml_path, "r", encoding="utf-8") as f:
        original_text = f.read()

    # Create backup
    backup_path = yaml_path + ".backup"
    with open(backup_path, "w", encoding="utf-8") as f:
        f.write(original_text)

    try:
        # Apply change based on type
        if ptype == "model_tier":
            new_text = _apply_model_tier_change(proposal, original_text)
        else:  # "prompt" or unknown → treat as prompt
            new_text = _apply_prompt_change(proposal, original_text)

        # Validate
        _validate_yaml(new_text)

        # Check something actually changed
        if new_text.strip() == original_text.strip():
            raise ValueError("Изменений не обнаружено — LLM вернул тот же текст")

        # Write modified YAML
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write(new_text)

        # Compute diff
        diff = _compute_diff(original_text, new_text, agent_name)

        # Remove backup on success
        try:
            os.remove(backup_path)
        except OSError:
            pass

        logger.info(f"Proposal applied: {proposal.get('id')} → {agent_name}.yaml")
        return {
            "applied": True,
            "diff": diff,
            "message": "Изменения применены к YAML. Вступят в силу после рестарта.",
        }

    except Exception as e:
        # Rollback from backup
        try:
            if os.path.exists(backup_path):
                with open(backup_path, "r", encoding="utf-8") as f:
                    restored = f.read()
                with open(yaml_path, "w", encoding="utf-8") as f:
                    f.write(restored)
                os.remove(backup_path)
                logger.info(f"Rollback successful for {agent_name}.yaml")
        except Exception as rb_err:
            logger.error(f"Rollback failed for {agent_name}.yaml: {rb_err}")
        raise


# ──────────────────────────────────────────────────────────
# Prompt changes (LLM-powered)
# ──────────────────────────────────────────────────────────

def _apply_prompt_change(proposal: dict, original_text: str) -> str:
    """Use LLM to modify backstory/goal field. Returns new full YAML text."""
    proposed_change = proposal.get("proposed_change", "")
    target_field = _detect_target_field(proposed_change)

    # Extract current field value
    current_value = _extract_yaml_field(original_text, target_field)
    if not current_value:
        raise ValueError(f"Не удалось извлечь поле '{target_field}' из YAML")

    # Call LLM to apply the change
    prompt = (
        f"ТЕКУЩИЙ ТЕКСТ ПОЛЯ '{target_field}':\n"
        f"---\n{current_value}\n---\n\n"
        f"ОПИСАНИЕ ИЗМЕНЕНИЯ:\n{proposed_change}\n\n"
        f"Верни ПОЛНЫЙ НОВЫЙ текст поля с применённым изменением."
    )

    new_value = _call_llm_tech(prompt, system=_APPLY_PROMPT_SYSTEM, max_tokens=4000)
    if not new_value:
        raise ValueError("LLM недоступен для применения изменений")

    # Clean up LLM output
    new_value = new_value.strip()
    # Remove potential YAML field prefix the LLM might add
    for prefix in [f"{target_field}:", f"{target_field}: |"]:
        if new_value.startswith(prefix):
            new_value = new_value[len(prefix):].strip()

    if len(new_value) < 50:
        raise ValueError(
            f"LLM вернул слишком короткий текст ({len(new_value)} символов)"
        )

    return _replace_yaml_field(original_text, target_field, new_value)


# ──────────────────────────────────────────────────────────
# Model tier changes (deterministic)
# ──────────────────────────────────────────────────────────

def _apply_model_tier_change(proposal: dict, original_text: str) -> str:
    """Replace llm: line with new model. Returns new full YAML text."""
    proposed_change = proposal.get("proposed_change", "").lower()
    target_model = _detect_target_model(proposed_change, original_text)

    if not target_model:
        raise ValueError(
            "Не удалось определить целевую модель из предложения. "
            "Ожидается 'sonnet' или 'haiku' в proposed_change."
        )

    new_text = re.sub(
        r"^llm:\s+.*$",
        f"llm: {target_model}",
        original_text,
        count=1,
        flags=re.MULTILINE,
    )

    if new_text == original_text:
        raise ValueError("llm: поле не найдено или модель не изменилась")

    return new_text


# ──────────────────────────────────────────────────────────
# YAML field manipulation (preserves formatting)
# ──────────────────────────────────────────────────────────

def _extract_yaml_field(yaml_text: str, field: str) -> Optional[str]:
    """Extract a multi-line YAML field value from text."""
    lines = yaml_text.split("\n")
    field_start = None
    content_lines = []

    for i, line in enumerate(lines):
        if line.startswith(f"{field}:"):
            field_start = i
            # Check if it's a block scalar (|) or inline
            rest = line[len(f"{field}:"):].strip()
            if rest == "|":
                continue  # content starts on next line
            elif rest:
                return rest.strip('" ')
            continue

        if field_start is not None:
            # Indented content belongs to the field
            if line and not line[0].isspace():
                # New top-level key → field ended
                break
            if line.strip():
                content_lines.append(line.strip())
            elif content_lines:
                content_lines.append("")  # preserve blank lines within content

    # Remove trailing blank lines
    while content_lines and content_lines[-1] == "":
        content_lines.pop()

    return "\n".join(content_lines) if content_lines else None


def _replace_yaml_field(yaml_text: str, field: str, new_value: str) -> str:
    """Replace a multi-line YAML field value while preserving the rest."""
    lines = yaml_text.split("\n")
    field_start = None
    field_end = None

    for i, line in enumerate(lines):
        if line.startswith(f"{field}:"):
            field_start = i
        elif field_start is not None and line and not line[0].isspace():
            # Next top-level key
            field_end = i
            break

    if field_start is None:
        raise ValueError(f"Поле '{field}' не найдено в YAML")

    if field_end is None:
        field_end = len(lines)

    # Build new field block
    new_lines = [f"{field}: |"]
    for content_line in new_value.strip().split("\n"):
        new_lines.append(f"  {content_line}")
    new_lines.append("")  # blank line separator

    result_lines = lines[:field_start] + new_lines + lines[field_end:]
    return "\n".join(result_lines)


# ──────────────────────────────────────────────────────────
# Detection helpers
# ──────────────────────────────────────────────────────────

def _detect_target_field(proposed_change: str) -> str:
    """Detect which YAML field to modify from proposal text."""
    text = proposed_change.lower()

    goal_keywords = ["goal", "цель", "целей", "целям"]
    role_keywords = ["role", "роль", "ролей", "ролям"]
    backstory_keywords = ["backstory", "бэкстори", "биограф", "характер", "предыстор"]

    for kw in goal_keywords:
        if kw in text:
            return "goal"

    for kw in role_keywords:
        if kw in text:
            return "role"

    # Default to backstory (most common target)
    return "backstory"


def _detect_target_model(proposed_change: str, original_text: str) -> Optional[str]:
    """Detect target model tier from proposal text."""
    text = proposed_change.lower()

    # Extract current model
    current_match = re.search(r"^llm:\s+(.+)$", original_text, re.MULTILINE)
    current_model = current_match.group(1).strip() if current_match else ""

    # Keywords for each tier
    if "sonnet" in text:
        return _TIER_TO_MODEL["sonnet"]
    if "haiku" in text:
        return _TIER_TO_MODEL["haiku"]

    # "upgrade" means haiku → sonnet
    if "upgrade" in text or "повысить" in text or "апгрейд" in text:
        if "haiku" in current_model:
            return _TIER_TO_MODEL["sonnet"]

    # "downgrade" means sonnet → haiku
    if "downgrade" in text or "понизить" in text or "даунгрейд" in text:
        if "sonnet" in current_model:
            return _TIER_TO_MODEL["haiku"]

    return None


# ──────────────────────────────────────────────────────────
# Diff and validation
# ──────────────────────────────────────────────────────────

def _compute_diff(before: str, after: str, agent_name: str) -> str:
    """Compute unified diff between two YAML texts."""
    before_lines = before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)
    diff = difflib.unified_diff(
        before_lines,
        after_lines,
        fromfile=f"agents/{agent_name}.yaml (до)",
        tofile=f"agents/{agent_name}.yaml (после)",
    )
    return "".join(diff)


def _validate_yaml(text: str):
    """Parse and validate YAML. Raises ValueError on problems."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ValueError(f"YAML невалиден: {e}")

    if not isinstance(data, dict):
        raise ValueError("YAML не содержит словарь верхнего уровня")

    for key in _REQUIRED_YAML_KEYS:
        if key not in data:
            raise ValueError(f"Отсутствует обязательное поле '{key}'")

    # Check field lengths
    for field in ("backstory", "goal"):
        val = data.get(field, "")
        if isinstance(val, str) and len(val) < 20:
            raise ValueError(
                f"Поле '{field}' слишком короткое ({len(val)} символов)"
            )


def format_diff_for_telegram(diff: str, max_len: int = 3000) -> str:
    """Truncate and format diff for Telegram display."""
    if not diff:
        return "(нет изменений)"

    # Keep only + and - lines for brevity
    lines = diff.split("\n")
    meaningful = []
    for line in lines:
        if line.startswith("---") or line.startswith("+++"):
            meaningful.append(line)
        elif line.startswith("@@"):
            meaningful.append(line)
        elif line.startswith("+") or line.startswith("-"):
            meaningful.append(line)

    result = "\n".join(meaningful) if meaningful else diff

    # HTML escape for Telegram
    result = html.escape(result)

    if len(result) > max_len:
        result = result[:max_len] + "\n... (обрезано)"

    return result
