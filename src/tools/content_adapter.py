"""
📱 Zinin Corp — Multi-Platform Content Adapter
Adapts a base post for different platforms (LinkedIn, Telegram, Threads).
Uses free LLM (Llama 3.3 70B) for intelligent rewriting.
Falls back to rule-based adaptation if LLM unavailable.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


# ── Platform rules ────────────────────────────────────────

PLATFORM_RULES = {
    "linkedin": {
        "label": "LinkedIn",
        "max_chars": 3000,
        "tone": "профессиональный, экспертный",
        "hashtags": True,
        "max_hashtags": 5,
        "emoji_level": "minimal",
        "format": "длинный пост с абзацами, подзаголовками и CTA",
        "signature": True,
    },
    "telegram": {
        "label": "Telegram",
        "max_chars": 2000,
        "tone": "прямой, разговорный, без воды",
        "hashtags": False,
        "max_hashtags": 0,
        "emoji_level": "moderate",
        "format": "короткий пост, буллеты, без подзаголовков",
        "signature": False,
    },
    "threads": {
        "label": "Threads",
        "max_chars": 500,
        "tone": "провокационный, дискуссионный",
        "hashtags": True,
        "max_hashtags": 3,
        "emoji_level": "none",
        "format": "1-3 предложения, вопрос в конце для дискуссии",
        "signature": False,
    },
}

_ADAPT_SYSTEM = """You are a content adaptation expert. You rewrite posts for different social platforms.
RULES:
- Keep the core message and key facts EXACTLY
- NEVER invent new data or numbers
- Adapt tone, length, and format for the target platform
- Output ONLY the adapted post text, nothing else
- Write in Russian (unless the original is in English)"""

_ADAPT_PROMPT_TEMPLATE = (
    "Адаптируй этот пост для {platform_label}:\n\n"
    "ПРАВИЛА ПЛАТФОРМЫ:\n"
    "- Макс. длина: {max_chars} символов\n"
    "- Тон: {tone}\n"
    "- Формат: {format}\n"
    "- Хэштеги: {hashtag_note}\n"
    "- Эмодзи: {emoji_level}\n"
    "{signature_note}\n\n"
    "ОРИГИНАЛЬНЫЙ ПОСТ:\n"
    "{original_text}\n\n"
    "Верни ТОЛЬКО адаптированный текст для {platform_label}:"
)


# ── Core adaptation ───────────────────────────────────────

def adapt_content(original_text: str, target_platform: str,
                  source_platform: str = "linkedin") -> str:
    """Adapt content for a target platform.

    Uses LLM when available, falls back to rule-based adaptation.
    Returns adapted text or original if adaptation fails.
    """
    if target_platform == source_platform:
        return original_text

    rules = PLATFORM_RULES.get(target_platform)
    if not rules:
        logger.warning(f"Unknown platform: {target_platform}")
        return original_text

    # Try LLM adaptation first
    adapted = _llm_adapt(original_text, target_platform, rules)
    if adapted:
        return adapted

    # Fallback: rule-based adaptation
    return _rule_based_adapt(original_text, target_platform, rules)


def adapt_for_all_platforms(original_text: str,
                            source_platform: str = "linkedin") -> dict[str, str]:
    """Adapt content for all platforms at once.

    Returns dict: {platform_name: adapted_text}.
    Source platform gets original text unchanged.
    """
    result = {}
    for platform in PLATFORM_RULES:
        if platform == source_platform:
            result[platform] = original_text
        else:
            result[platform] = adapt_content(original_text, platform, source_platform)
    return result


# ── LLM adaptation ────────────────────────────────────────

def _llm_adapt(original_text: str, target_platform: str,
               rules: dict) -> Optional[str]:
    """Adapt using free LLM. Returns None if unavailable."""
    try:
        from .tech_tools import _call_llm_tech
    except ImportError:
        return None

    signature_note = "- Подпись бренда в конце: да" if rules.get("signature") else ""
    hashtag_note = f"да (макс. {rules.get('max_hashtags', 0)})" if rules.get("hashtags") else "нет"

    prompt = _ADAPT_PROMPT_TEMPLATE.format(
        platform_label=rules["label"],
        max_chars=rules["max_chars"],
        tone=rules["tone"],
        format=rules["format"],
        hashtag_note=hashtag_note,
        emoji_level=rules["emoji_level"],
        signature_note=signature_note,
        original_text=original_text[:2000],
    )

    try:
        result = _call_llm_tech(prompt, system=_ADAPT_SYSTEM, max_tokens=1500)
        if result and len(result.strip()) > 20:
            adapted = result.strip()
            # Enforce max length
            if len(adapted) > rules["max_chars"]:
                adapted = _truncate_smart(adapted, rules["max_chars"])
            return adapted
    except Exception as e:
        logger.warning(f"LLM adaptation failed for {target_platform}: {e}")

    return None


# ── Rule-based fallback ───────────────────────────────────

def _rule_based_adapt(original_text: str, target_platform: str,
                      rules: dict) -> str:
    """Simple rule-based adaptation when LLM is unavailable."""
    text = original_text.strip()

    if target_platform == "telegram":
        # Remove hashtags
        text = re.sub(r'#\w+', '', text).strip()
        # Truncate to limit
        if len(text) > rules["max_chars"]:
            text = _truncate_smart(text, rules["max_chars"])

    elif target_platform == "threads":
        # Take first paragraph or first 2 sentences as hook
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if paragraphs:
            hook = paragraphs[0]
            # If still too long, take first sentence
            if len(hook) > rules["max_chars"]:
                sentences = re.split(r'[.!?]\s+', hook)
                hook = sentences[0] + "." if sentences else hook[:rules["max_chars"]]
            # Add discussion question if space allows
            if len(hook) < rules["max_chars"] - 50:
                hook += "\n\nА как у вас?"
            text = hook[:rules["max_chars"]]
        else:
            text = text[:rules["max_chars"]]

    elif target_platform == "linkedin":
        # Ensure not too long
        if len(text) > rules["max_chars"]:
            text = _truncate_smart(text, rules["max_chars"])

    return text


def _truncate_smart(text: str, max_chars: int) -> str:
    """Truncate text at sentence boundary, not mid-word."""
    if len(text) <= max_chars:
        return text

    # Find last sentence end before limit
    truncated = text[:max_chars]
    last_period = max(truncated.rfind('.'), truncated.rfind('!'), truncated.rfind('?'))

    if last_period > max_chars * 0.5:
        return truncated[:last_period + 1]

    # Fallback: truncate at last space
    last_space = truncated.rfind(' ')
    if last_space > max_chars * 0.5:
        return truncated[:last_space] + "..."

    return truncated + "..."
