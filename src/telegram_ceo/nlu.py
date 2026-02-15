"""NLU module for CEO bot — Russian intent detection.

Detects user intent from Russian text and maps to bot commands.
Keyword-based matching with normalization.
"""

import re
import logging
from typing import Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class Intent(BaseModel):
    """Detected intent from user text."""
    command: str        # e.g., "/balance", "/tasks", "/status"
    confidence: float   # 0.0–1.0
    agent: str = ""     # target agent key (if detected)
    params: dict = {}   # extracted parameters


# Command → trigger phrases mapping
INTENT_MAP: dict[str, list[str]] = {
    "/balance": [
        "покажи баланс", "сколько денег", "баланс", "деньги на счету",
        "состояние счёта", "состояние счета", "финансы", "сколько на балансе",
    ],
    "/tasks": [
        "что с задачами", "задачи", "таски", "бэклог", "список задач",
        "покажи задачи", "открытые задачи", "task pool", "тасклист",
    ],
    "/status": [
        "статус", "состояние системы", "кто работает",
        "как система", "здоровье системы",
    ],
    "/review": [
        "обзор", "стратегический обзор", "ревью", "review",
    ],
    "/report": [
        "отчёт", "отчет", "репорт", "сводка", "доклад",
        "полный отчёт", "корпоративный отчёт",
    ],
    "/analytics": [
        "аналитика", "использование api", "токены", "расход токенов",
        "сколько потратили", "стоимость api", "analytics",
    ],
    "/help": [
        "помощь", "что умеешь", "команды", "помоги",
        "что ты можешь", "какие команды",
    ],
    "/content": [
        "напиши пост", "создай контент", "сделай пост",
        "подготовь публикацию", "контент для linkedin",
    ],
    "/linkedin": [
        "linkedin статус", "линкедин", "опубликуй в linkedin",
    ],
}

# Agent name → trigger phrases mapping
AGENT_INTENT_MAP: dict[str, list[str]] = {
    "accountant": [
        "маттиас", "бухгалтер", "cfo", "финансовый директор",
        "финансы", "бюджет", "портфель", "крипто",
        "банк", "выручка", "доход", "расход",
    ],
    "automator": [
        "мартин", "cto", "техдиректор", "технический директор",
        "api", "деплой", "деплоить", "задеплоить", "сервер", "здоровье api",
        "инфраструктура", "код", "баг", "ошибка сервера",
    ],
    "smm": [
        "юки", "smm", "контент", "пост", "линкедин",
        "threads", "публикация", "соцсети", "подкаст",
    ],
    "designer": [
        "райан", "дизайн", "картинк", "инфографик",
        "визуал", "видео", "брендинг", "изображен",
        "нарисуй", "фото", "рисун", "сгенерир",
        "иллюстрац", "анимац", "ролик", "клип",
    ],
    "cpo": [
        "софи", "продукт", "фича", "спринт",
        "бэклог продукта", "roadmap", "роадмап",
    ],
}


def _normalize_text(text: str) -> str:
    """Normalize text for matching: lowercase, strip extra spaces."""
    text = text.lower().strip()
    text = re.sub(r"[.,!?;:]+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def detect_intent(text: str) -> Optional[Intent]:
    """Detect intent from Russian text.

    Returns Intent with highest confidence, or None if no match.
    Threshold: only returns if confidence >= 0.6.
    """
    normalized = _normalize_text(text)

    if not normalized or len(normalized) < 3:
        return None

    best_command = None
    best_confidence = 0.0

    for command, phrases in INTENT_MAP.items():
        for phrase in phrases:
            phrase_norm = _normalize_text(phrase)

            # Exact match
            if normalized == phrase_norm:
                return Intent(command=command, confidence=1.0)

            # Text starts with phrase
            if normalized.startswith(phrase_norm):
                conf = len(phrase_norm) / max(len(normalized), 1)
                conf = max(conf, 0.8)  # starts-with is high confidence
                if conf > best_confidence:
                    best_confidence = conf
                    best_command = command

            # Phrase is contained in text
            if phrase_norm in normalized and len(phrase_norm) >= 4:
                conf = len(phrase_norm) / max(len(normalized), 1)
                conf = max(conf, 0.6)  # contained is medium confidence
                if conf > best_confidence:
                    best_confidence = conf
                    best_command = command

    if best_command and best_confidence >= 0.6:
        return Intent(command=best_command, confidence=best_confidence)

    return None


def detect_agent(text: str) -> Optional[tuple[str, float]]:
    """Detect target agent from message text.

    Uses AGENT_INTENT_MAP for direct mentions, then falls back
    to task_pool AGENT_TAGS for keyword matching.

    Returns (agent_key, confidence) or None.
    """
    normalized = _normalize_text(text)

    if not normalized:
        return None

    # 1. Direct agent name/role mentions (high confidence)
    for agent_key, phrases in AGENT_INTENT_MAP.items():
        for phrase in phrases:
            if _normalize_text(phrase) in normalized:
                return (agent_key, 0.9)

    # 2. Tag-based matching via task_pool
    try:
        from ..task_pool import auto_tag, suggest_assignee
        tags = auto_tag(normalized)
        if tags:
            suggestions = suggest_assignee(tags)
            if suggestions and suggestions[0][1] >= 0.5:
                return suggestions[0]
    except Exception as e:
        logger.warning(f"Tag-based agent detection failed: {e}")

    return None
