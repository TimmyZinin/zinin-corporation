"""
SMM tools for Yuki (SMM manager agent)

Tools:
1. ContentGenerator — create, critique, and refine posts
2. YukiMemory — 4-layer memory system access
3. LinkedInPublisher — publish posts to LinkedIn API v2
"""

import json
import logging
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Helpers: data paths
# ──────────────────────────────────────────────────────────

def _memory_dir() -> str:
    for p in ["/app/data/yuki_memory", "data/yuki_memory"]:
        if os.path.isdir(p):
            return p
    return "data/yuki_memory"


def _load_json(path: str) -> dict:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_json(path: str, data: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ──────────────────────────────────────────────────────────
# Helpers: LLM calls (free models)
# ──────────────────────────────────────────────────────────

def _call_llm(prompt: str, system: str = "", max_tokens: int = 2000) -> Optional[str]:
    """Call LLM via OpenRouter (free) -> Groq (free) -> None."""
    from urllib.request import urlopen, Request
    from urllib.error import HTTPError

    providers = []

    # OpenRouter free models
    or_key = os.getenv("OPENROUTER_API_KEY", "")
    if or_key:
        providers.append({
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "key": or_key,
            "model": "meta-llama/llama-3.3-70b-instruct:free",
        })

    # Groq free
    groq_key = os.getenv("GROQ_API_KEY", "")
    if groq_key:
        providers.append({
            "url": "https://api.groq.com/openai/v1/chat/completions",
            "key": groq_key,
            "model": "llama-3.3-70b-versatile",
        })

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    for provider in providers:
        try:
            payload = json.dumps({
                "model": provider["model"],
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.7,
            }).encode("utf-8")

            req = Request(
                provider["url"],
                data=payload,
                headers={
                    "Authorization": f"Bearer {provider['key']}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )

            with urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"]

        except Exception as e:
            logger.warning(f"LLM call failed ({provider['model']}): {e}")
            continue

    return None


# ──────────────────────────────────────────────────────────
# Helpers: Self-Refine engine (ported from self_refine.py)
# ──────────────────────────────────────────────────────────

FORBIDDEN_PHRASES = [
    "попробуйте", "возможно", "верьте в себя",
    "каждый человек уникален", "секрет успеха",
    "быстро и легко", "многие люди",
    "сегодня поговорим", "хочу поделиться",
    "я видела это 10 000 раз", "я видела это тысячи раз",
    "звучит жёстко? ок. но это правда",
    "хватит жевать сопли",
    "в этом посте", "давайте разберёмся",
    "не секрет, что", "как мы все знаем",
    "в современном мире", "в наше время",
    "ни для кого не секрет", "всем известно",
    "в заключение хочу сказать", "подводя итог",
    "друзья", "дорогие друзья",
    "в этой статье", "сегодня я расскажу",
    "главная мысль заключается в том",
    "причина этой проблемы заключается",
    "оцените свои навыки", "определите области для роста",
    "помните, что важно", "не забывайте о том",
    "попробуйте задать себе вопрос",
    "чтобы оставаться актуальными",
    "вам нужно научиться", "вы должны понимать",
]


def _strip_non_cyrillic(text: str) -> str:
    """Remove CJK characters and other non-expected unicode from generated text.

    Keeps: Cyrillic, Latin, digits, common punctuation, emoji, arrows.
    Removes: CJK (Chinese/Japanese/Korean), Arabic, Thai, etc.
    """
    import re
    # Remove CJK Unified Ideographs, CJK Compatibility, Hangul, Katakana, Hiragana
    text = re.sub(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af\u3000-\u303f]', '', text)
    # Clean up any resulting double-spaces or orphaned arrows
    text = re.sub(r'→\s*→', '→', text)
    text = re.sub(r'  +', ' ', text)
    # Clean up lines that became just whitespace
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if stripped or not cleaned or cleaned[-1] != '':
            cleaned.append(line)
    return '\n'.join(cleaned)


def _evaluate_hook(content: str) -> Tuple[float, List[str]]:
    issues = []
    score = 0.5
    lines = content.strip().split("\n")
    first_lines = " ".join(lines[:3]).lower()
    if re.search(r"\d+%|\d+\s*(лет|раз|человек|компани|резюме)", first_lines):
        score += 0.3
    if "?" in first_lines:
        score += 0.1
    emotion_words = ["никогда", "всегда", "каждый", "ошибка", "проблема", "правда"]
    if any(w in first_lines for w in emotion_words):
        score += 0.1
    boring_starts = ["сегодня я", "хочу рассказать", "в этом посте", "привет всем",
                     "многие люди", "в современном мире", "ни для кого не секрет",
                     "не секрет, что", "как мы все знаем"]
    if any(s in first_lines for s in boring_starts):
        score -= 0.3
        issues.append("HOOK: Скучное начало")
    return min(1.0, max(0.0, score)), issues


def _evaluate_specificity(content: str) -> Tuple[float, List[str]]:
    issues = []
    score = 0.3
    numbers = re.findall(r"\d+", content)
    if len(numbers) >= 3:
        score += 0.3
    elif len(numbers) >= 1:
        score += 0.15
    else:
        issues.append("SPECIFICITY: Нет цифр и конкретных данных")
    examples = ["например", "пример", "случай", "клиент", "кандидат", "ситуация"]
    if any(w in content.lower() for w in examples):
        score += 0.2
    if re.search(r"\d+%", content):
        score += 0.2
    return min(1.0, max(0.0, score)), issues


def _evaluate_structure(content: str) -> Tuple[float, List[str]]:
    issues = []
    score = 0.3
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
    if len(paragraphs) >= 4:
        score += 0.3
    elif len(paragraphs) >= 2:
        score += 0.15
    else:
        issues.append("STRUCTURE: Мало абзацев, нет структуры")
    if re.search(r"[→•\-\*]", content):
        score += 0.2
    if re.search(r"—\s*\n.*СБОРКА", content):
        score += 0.2
    else:
        issues.append("STRUCTURE: Нет подписи «— Автор, СБОРКА»")
    return min(1.0, max(0.0, score)), issues


def _evaluate_tone(content: str, author: str = "") -> Tuple[float, List[str]]:
    issues = []
    score = 0.6
    soft = ["может быть", "наверное", "кажется", "вроде бы", "не уверен"]
    if any(w in content.lower() for w in soft):
        score -= 0.3
        issues.append("TONE: Неуверенные формулировки")
    direct = ["конкретно", "результат", "факт", "цифры", "формула", "вот пример"]
    if any(w in content.lower() for w in direct):
        score += 0.2
    # Penalize messianic/preachy tone
    preachy = ["оцените свои", "попробуйте задать", "помните, что важно",
               "вам нужно", "вы должны", "важно помнить", "не забывайте",
               "подумайте о том", "задайте себе вопрос"]
    preachy_found = [p for p in preachy if p in content.lower()]
    if preachy_found:
        score -= 0.3
        issues.append(f"TONE: Менторский/поучающий тон: {', '.join(preachy_found[:3])}")
    length = len(content)
    if 1200 <= length <= 3000:
        score += 0.2
    elif length < 800:
        issues.append(f"TONE: Пост слишком короткий ({length} символов, нужно 1200+)")
    # Check for CTA at the end
    last_lines = content.strip().split("\n")[-3:]
    last_text = " ".join(last_lines).lower()
    has_cta = "?" in last_text or any(w in last_text for w in [
        "расскажите", "напишите", "скиньте", "делитесь", "а вы", "а у вас",
        "пишите в комментар", "какой ваш", "что думаете",
    ])
    if not has_cta:
        score -= 0.2
        issues.append("TONE: Нет CTA/вопроса в конце поста")
    return min(1.0, max(0.0, score)), issues


def _evaluate_forbidden(content: str) -> Tuple[float, List[str]]:
    issues = []
    found = [p for p in FORBIDDEN_PHRASES if p.lower() in content.lower()]
    if found:
        issues.append(f"FORBIDDEN: Найдены запрещённые фразы: {', '.join(found)}")
        return 0.0, issues
    return 1.0, []


def _critique_content(content: str, topic: str = "", author: str = "") -> Dict:
    """Full rule-based critique."""
    hook_score, hook_issues = _evaluate_hook(content)
    spec_score, spec_issues = _evaluate_specificity(content)
    struct_score, struct_issues = _evaluate_structure(content)
    tone_score, tone_issues = _evaluate_tone(content, author)
    forb_score, forb_issues = _evaluate_forbidden(content)

    overall = (
        hook_score * 0.25
        + spec_score * 0.20
        + struct_score * 0.20
        + tone_score * 0.20
        + forb_score * 0.15
    )

    all_issues = hook_issues + spec_issues + struct_issues + tone_issues + forb_issues
    passed = overall >= 0.8 and forb_score == 1.0

    return {
        "overall_score": round(overall, 3),
        "scores": {
            "hook": round(hook_score, 3),
            "specificity": round(spec_score, 3),
            "structure": round(struct_score, 3),
            "tone": round(tone_score, 3),
            "forbidden": round(forb_score, 3),
        },
        "issues": all_issues,
        "passed": passed,
        "length": len(content),
    }


# ──────────────────────────────────────────────────────────
# Tool 1: Content Generator
# ──────────────────────────────────────────────────────────

class ContentGeneratorInput(BaseModel):
    action: str = Field(
        ...,
        description=(
            "Action: 'generate' (create a post — needs topic, author), "
            "'critique' (evaluate existing content — needs content), "
            "'refine' (improve content — needs content, optional topic/author)"
        ),
    )
    topic: Optional[str] = Field(None, description="Post topic (e.g., 'резюме', 'собеседование', 'LinkedIn профиль')")
    author: Optional[str] = Field(
        None,
        description="Author: 'kristina' (Кристина Жукова) or 'tim' (Тим Зинин). Default: kristina"
    )
    content: Optional[str] = Field(None, description="Existing content to critique or refine")
    platform: Optional[str] = Field(None, description="Platform: 'linkedin' (default), 'telegram'")


class ContentGenerator(BaseTool):
    name: str = "Content Generator"
    description: str = (
        "Creates, critiques, and refines SMM posts for СБОРКА. "
        "Uses 6-part structure (hook, problem, story, insight, action, conclusion). "
        "Actions: generate, critique, refine."
    )
    args_schema: Type[BaseModel] = ContentGeneratorInput

    def _run(self, action: str, topic: str = None, author: str = None,
             content: str = None, platform: str = None) -> str:

        author_name = "Кристина Жукова" if (author or "kristina") == "kristina" else "Тим Зинин"
        platform = platform or "linkedin"

        if action == "critique":
            if not content:
                return "Error: need content to critique"
            result = _critique_content(content, topic or "", author_name)
            lines = [f"CRITIQUE RESULT (score: {result['overall_score']:.2f}, passed: {result['passed']})"]
            for k, v in result["scores"].items():
                lines.append(f"  {k}: {v:.2f}")
            if result["issues"]:
                lines.append("Issues:")
                for issue in result["issues"]:
                    lines.append(f"  - {issue}")
            lines.append(f"Length: {result['length']} chars")
            return "\n".join(lines)

        if action == "refine":
            if not content:
                return "Error: need content to refine"
            return self._refine(content, topic or "", author_name)

        if action == "generate":
            if not topic:
                return "Error: need topic to generate"
            return self._generate(topic, author_name, platform)

        return f"Unknown action: {action}"

    def _generate(self, topic: str, author: str, platform: str) -> str:
        """Generate a post using LLM with self-refine."""
        # Load memory data for context
        mem_dir = _memory_dir()
        brand = _load_json(os.path.join(mem_dir, "semantic", "brand_voice.json"))
        vocab = _load_json(os.path.join(mem_dir, "semantic", "vocabulary.json"))
        rules = _load_json(os.path.join(mem_dir, "procedural", "rules.json"))

        author_key = "kristina" if "Кристина" in author else "tim"
        author_info = brand.get("authors", {}).get(author_key, {})

        forbidden = vocab.get("forbidden_phrases", [])
        rules_text = "\n".join(f"- {r['rule']}" for r in rules.get("rules", []))

        system_prompt = f"""Ты — профессиональный копирайтер проекта СБОРКА (клуб карьерной дисциплины).

Пишешь от имени: {author} ({author_info.get('role', '')})
Голос: {author_info.get('voice', 'Прямой, уверенный, экспертный')}

⚠️ ЯЗЫК: СТРОГО РУССКИЙ. Ни одного символа на китайском, японском, корейском или любом другом языке кроме русского и минимального английского (только термины вроде LinkedIn, AI, HR). Все стрелки пиши как →, не используй иероглифы.

⛔ АБСОЛЮТНЫЙ ЗАПРЕТ НА МЕССИАНСТВО:
- НЕ ПОУЧАЙ читателя. Ты НЕ учитель, НЕ гуру, НЕ ментор.
- НЕ ДАВАЙ СОВЕТОВ в стиле «оцените свои навыки», «подумайте о...», «попробуйте...»
- Ты делишься СВОИМ опытом и наблюдениями, а не учишь жизни.
- Тон = коллега за кофе рассказывает историю, а НЕ коуч на сцене.
- Вместо «Вам нужно...» пиши «Я заметил, что...» или «У нас в команде...»
- Вместо «Оцените свои навыки» пиши «Когда я последний раз смотрел свой список скиллов, выяснилось...»
- Никаких «5 шагов к успеху», «3 правила эффективности», «как стать лучше».

🎣 КРЮЧОК (ОБЯЗАТЕЛЬНО, ПЕРВАЯ СТРОКА):
Пост НАЧИНАЕТСЯ с короткого, яркого, провокационного вброса. 1 строка max.
Примеры хороших крючков:
- «73% резюме летят в корзину за 6 секунд.»
- «Вчера уволили лучшего разработчика в команде. За что? За перфекционизм.»
- «LinkedIn превратился в ярмарку тщеславия. И я часть проблемы.»
- «Мой клиент получил оффер на 40% выше. Секрет? Он врал. Почти.»
НЕ НАЧИНАЙ с: «Многие люди», «В современном мире», «Сегодня поговорим», «Хочу поделиться».

📐 СТРУКТУРА (все 6 частей):
1. Крючок (1 строка) — провокация, факт с цифрой, парадокс. Короткая. Яркая. Бьёт.
2. Проблема (2-3 предложения) — конкретная боль с деталями и масштабом.
3. История/Кейс (3-5 предложений) — КОНКРЕТНЫЙ пример с именем, цифрами, деталями. «Мой коллега Дима» > «многие специалисты».
4. Инсайт (3-5 предложений) — почему так происходит, механика. Делись наблюдением, а НЕ нравоучением.
5. Практика (3-5 пунктов →) — что КОНКРЕТНО делать. Каждый пункт — действие, не абстракция.
6. CTA / Финал (1-2 предложения) — ОБЯЗАТЕЛЬНО заканчивай открытым вопросом ИЛИ призывом к действию.

🔚 CTA В КОНЦЕ (ОБЯЗАТЕЛЬНО):
Последние 1-2 строки поста — ВСЕГДА вопрос или призыв. Примеры:
- «А у вас в команде есть такие "звёзды"? Что с ними делаете?»
- «Расскажите в комментах — сколько раз вы переделывали резюме в этом году?»
- «Скиньте свой LinkedIn — разберу бесплатно первые 5 профилей.»
- «Напишите одним словом — что для вас главное в работе?»
НЕ ЗАКАНЧИВАЙ просто выводом без вопроса/действия.

ПРАВИЛА:
{rules_text}

ЗАПРЕЩЕНО: {', '.join(forbidden[:10])}

АНТИ-ШАБЛОН — НЕ ПИШИ ТАК:
- «Многие люди до сих пор убеждены...» — СКУЧНО.
- «Главная мысль заключается в том, что...» — КАНЦЕЛЯРИТ.
- «Оцените свои навыки и определите области для роста» — МЕССИАНСТВО. Ты не коуч.
- «Чтобы оставаться актуальными, нам нужно...» — ОБЩО.
- «В заключение хочу сказать...» — ЛИШНЕЕ.
- «Помните, что важно...» — ПОУЧЕНИЕ. Не надо.
- «Попробуйте задать себе вопрос...» — ТЫ НЕ ТРЕНЕР.
- Не повторяй одну мысль разными словами в соседних абзацах.

СТИЛЬ:
- Пиши как человек за кофе, НЕ как ChatGPT и НЕ как коуч на сцене
- Разговорные обороты: «Вот пример», «Окей, но», «Серьёзно?», «Знаете что?»
- Конкретные цифры: «за 6 месяцев», «3 из 5 кандидатов», «рост на 40%»
- Короткие предложения. Абзацы по 2-3 предложения max.
- Никакой воды. Каждое предложение — ценность.
- Больше «я видел / я заметил / у нас было» и меньше «вам нужно / вы должны»

Длина: 1500-2500 символов для LinkedIn.
Подпись в конце (ДО CTA-вопроса): «— {author}\nСБОРКА — клуб карьерной дисциплины»"""

        user_prompt = f"Напиши экспертный пост для {platform.upper()} на тему: {topic}"

        result = _call_llm(user_prompt, system=system_prompt, max_tokens=2000)

        if not result:
            return "Error: LLM call failed. Check OPENROUTER_API_KEY or GROQ_API_KEY."

        # Strip CJK characters and other non-Cyrillic garbage
        result = _strip_non_cyrillic(result)

        # Auto-critique
        critique = _critique_content(result, topic, author)

        # If passed, return
        if critique["passed"]:
            return (
                f"POST GENERATED (score: {critique['overall_score']:.2f} ✅)\n"
                f"Author: {author}\nTopic: {topic}\nLength: {len(result)} chars\n"
                f"---\n{result}"
            )

        # Try one refine iteration
        refined = self._refine(result, topic, author)
        return refined

    def _refine(self, content: str, topic: str, author: str) -> str:
        """Refine content using LLM."""
        critique = _critique_content(content, topic, author)

        if critique["passed"]:
            return (
                f"CONTENT ALREADY GOOD (score: {critique['overall_score']:.2f} ✅)\n"
                f"---\n{content}"
            )

        issues_text = "\n".join(f"- {i}" for i in critique["issues"])

        prompt = f"""Улучши этот пост для СБОРКИ (клуб карьерной дисциплины).

ТЕКУЩИЕ ПРОБЛЕМЫ:
{issues_text}

ТЕКУЩИЙ SCORE: {critique['overall_score']:.2f}

ТРЕБОВАНИЯ:
- Обязательно 6 частей: крючок, проблема, история, инсайт, решение, вывод
- Конкретные цифры и примеры
- Прямой уверенный тон
- Длина 1500-2500 символов
- Подпись: «— {author}\nСБОРКА — клуб карьерной дисциплины»
- ЗАПРЕЩЕНО: {', '.join(FORBIDDEN_PHRASES[:6])}

ОРИГИНАЛЬНЫЙ ТЕКСТ:
{content}

Верни ТОЛЬКО улучшенный текст, без комментариев."""

        refined = _call_llm(prompt, max_tokens=2000)

        if not refined:
            return f"REFINE FAILED (original score: {critique['overall_score']:.2f})\n---\n{content}"

        # Strip CJK characters
        refined = _strip_non_cyrillic(refined)

        new_critique = _critique_content(refined, topic, author)

        status = "✅" if new_critique["passed"] else "⚠️"
        return (
            f"REFINED {status} (score: {critique['overall_score']:.2f} → {new_critique['overall_score']:.2f})\n"
            f"Length: {len(refined)} chars\n"
            f"---\n{refined}"
        )


# ──────────────────────────────────────────────────────────
# Tool 2: Yuki Memory
# ──────────────────────────────────────────────────────────

class YukiMemoryInput(BaseModel):
    action: str = Field(
        ...,
        description=(
            "Action: 'get_rules' (content rules), "
            "'get_brand_voice' (author profiles), "
            "'get_topics' (content categories), "
            "'get_forbidden' (banned phrases), "
            "'record_generation' (save post — needs data as JSON string), "
            "'record_feedback' (save feedback — needs data as JSON string), "
            "'get_stats' (generation/feedback statistics)"
        ),
    )
    data: Optional[str] = Field(None, description="JSON string with data for record actions")


class YukiMemory(BaseTool):
    name: str = "Yuki Memory"
    description: str = (
        "4-layer memory system: procedural (rules), semantic (brand voice), "
        "episodic (history), working (state). "
        "Actions: get_rules, get_brand_voice, get_topics, get_forbidden, "
        "record_generation, record_feedback, get_stats."
    )
    args_schema: Type[BaseModel] = YukiMemoryInput

    def _run(self, action: str, data: str = None) -> str:
        mem = _memory_dir()

        if action == "get_rules":
            rules = _load_json(os.path.join(mem, "procedural", "rules.json"))
            items = rules.get("rules", [])
            if not items:
                return "No rules found."
            lines = ["CONTENT RULES:"]
            for r in items:
                lines.append(f"  [{r.get('category', '?')}] {r.get('rule', '?')} (confidence: {r.get('confidence', 0)})")
            return "\n".join(lines)

        if action == "get_brand_voice":
            bv = _load_json(os.path.join(mem, "semantic", "brand_voice.json"))
            authors = bv.get("authors", {})
            tone = bv.get("tone", {})
            lines = ["BRAND VOICE:"]
            for key, info in authors.items():
                lines.append(f"  {info.get('name', key)}: {info.get('voice', '?')}")
                lines.append(f"    Role: {info.get('role', '?')}")
            lines.append(f"  DO: {', '.join(tone.get('do', []))}")
            lines.append(f"  DON'T: {', '.join(tone.get('dont', []))}")
            sig = bv.get("signature", "")
            if sig:
                lines.append(f"  Signature: {sig}")
            return "\n".join(lines)

        if action == "get_topics":
            topics = _load_json(os.path.join(mem, "semantic", "topics.json"))
            cats = topics.get("categories", {})
            lines = ["CONTENT TOPICS:"]
            for cat, keywords in cats.items():
                lines.append(f"  {cat}: {', '.join(keywords[:5])}")
            trending = topics.get("trending", [])
            if trending:
                lines.append(f"  Trending: {', '.join(trending)}")
            return "\n".join(lines)

        if action == "get_forbidden":
            vocab = _load_json(os.path.join(mem, "semantic", "vocabulary.json"))
            forbidden = vocab.get("forbidden_phrases", [])
            recommended = vocab.get("recommended_phrases", [])
            lines = ["VOCABULARY:"]
            lines.append(f"  FORBIDDEN ({len(forbidden)}): {', '.join(forbidden)}")
            lines.append(f"  RECOMMENDED ({len(recommended)}): {', '.join(recommended)}")
            return "\n".join(lines)

        if action == "record_generation":
            if not data:
                return "Error: need data (JSON string)"
            try:
                record = json.loads(data)
            except json.JSONDecodeError:
                record = {"content_preview": data[:200], "raw": True}

            record["timestamp"] = datetime.now().isoformat()
            # Append to JSONL file
            date_str = datetime.now().strftime("%Y-%m-%d")
            path = os.path.join(mem, "episodic", "generations", f"{date_str}.jsonl")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            return f"Generation recorded ({date_str})"

        if action == "record_feedback":
            if not data:
                return "Error: need data (JSON string)"
            try:
                record = json.loads(data)
            except json.JSONDecodeError:
                record = {"feedback": data, "raw": True}

            record["timestamp"] = datetime.now().isoformat()
            date_str = datetime.now().strftime("%Y-%m-%d")
            path = os.path.join(mem, "episodic", "feedback", f"{date_str}.jsonl")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            return f"Feedback recorded ({date_str})"

        if action == "get_stats":
            gen_dir = os.path.join(mem, "episodic", "generations")
            fb_dir = os.path.join(mem, "episodic", "feedback")

            gen_count = 0
            fb_count = 0
            if os.path.isdir(gen_dir):
                for f in os.listdir(gen_dir):
                    if f.endswith(".jsonl"):
                        with open(os.path.join(gen_dir, f), "r") as fh:
                            gen_count += sum(1 for _ in fh)
            if os.path.isdir(fb_dir):
                for f in os.listdir(fb_dir):
                    if f.endswith(".jsonl"):
                        with open(os.path.join(fb_dir, f), "r") as fh:
                            fb_count += sum(1 for _ in fh)

            state = _load_json(os.path.join(mem, "working", "state.json"))
            autonomy = state.get("agent", {}).get("autonomy_name", "DRAFT")

            return (
                f"YUKI STATS:\n"
                f"  Generations: {gen_count}\n"
                f"  Feedback entries: {fb_count}\n"
                f"  Autonomy level: {autonomy}\n"
                f"  Memory files: rules, brand_voice, topics, vocabulary"
            )

        return f"Unknown action: {action}"


# ──────────────────────────────────────────────────────────
# Tool 3: LinkedIn Publisher (Modern REST API)
# ──────────────────────────────────────────────────────────

_LINKEDIN_API_VERSION = "202502"
_LINKEDIN_BASE = "https://api.linkedin.com"


class LinkedInPublisherInput(BaseModel):
    action: str = Field(
        ...,
        description=(
            "Action: 'publish_text' (text post — needs text), "
            "'publish_image' (post with image — needs text + image_url), "
            "'check_token' (check if LinkedIn is configured), "
            "'status' (LinkedIn integration status)"
        ),
    )
    text: Optional[str] = Field(None, description="Post text (max 3000 chars)")
    image_url: Optional[str] = Field(None, description="Image URL to attach (for publish_image)")


class LinkedInPublisherTool(BaseTool):
    name: str = "LinkedIn Publisher"
    description: str = (
        "Publishes posts to LinkedIn via modern REST API. "
        "Actions: publish_text, publish_image, check_token, status. "
        "Supports text posts (up to 3000 chars) and image posts."
    )
    args_schema: Type[BaseModel] = LinkedInPublisherInput

    def _run(self, action: str, text: str = None, image_url: str = None) -> str:
        from urllib.request import urlopen, Request
        from urllib.error import HTTPError

        access_token = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
        person_id = os.getenv("LINKEDIN_PERSON_ID", "")

        if action == "status":
            configured = bool(access_token and person_id)
            return (
                f"LINKEDIN STATUS:\n"
                f"  Configured: {'✅ Yes' if configured else '❌ No'}\n"
                f"  Token: {'Set' if access_token else 'MISSING'}\n"
                f"  Person ID: {'Set' if person_id else 'MISSING'}\n"
                f"  API: REST /rest/posts (v{_LINKEDIN_API_VERSION})"
            )

        if action == "check_token":
            if not access_token:
                return "❌ LINKEDIN_ACCESS_TOKEN not set"
            try:
                req = Request(
                    f"{_LINKEDIN_BASE}/v2/userinfo",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "LinkedIn-Version": _LINKEDIN_API_VERSION,
                    },
                )
                with urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    name = data.get("name", "Unknown")
                    return f"✅ LinkedIn token valid. User: {name}"
            except HTTPError as e:
                if e.code == 401:
                    return "❌ LinkedIn token EXPIRED. Refresh at https://linkedin.com/developers/tools/oauth"
                return f"❌ LinkedIn error: {e.code}"
            except Exception as e:
                return f"❌ LinkedIn error: {e}"

        if action in ("publish_text", "publish"):
            if not text:
                return "Error: need text to publish"
            if not access_token or not person_id:
                return "❌ LinkedIn not configured. Set LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_ID."
            if len(text) > 3000:
                text = text[:2997] + "..."
            return self._publish_post(access_token, person_id, text)

        if action == "publish_image":
            if not text:
                return "Error: need text for image post"
            if not image_url:
                return "Error: need image_url for image post"
            if not access_token or not person_id:
                return "❌ LinkedIn not configured. Set LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_ID."
            if len(text) > 3000:
                text = text[:2997] + "..."
            return self._publish_image_post(access_token, person_id, text, image_url)

        return f"Unknown action: {action}. Use: publish_text, publish_image, check_token, status"

    def _publish_post(self, token: str, person_id: str, text: str) -> str:
        """Publish a text-only post via modern REST API."""
        from urllib.request import urlopen, Request
        from urllib.error import HTTPError

        payload = {
            "author": f"urn:li:person:{person_id}",
            "commentary": text,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
        }

        try:
            req = Request(
                f"{_LINKEDIN_BASE}/rest/posts",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "LinkedIn-Version": _LINKEDIN_API_VERSION,
                    "X-Restli-Protocol-Version": "2.0.0",
                },
                method="POST",
            )
            with urlopen(req, timeout=30) as resp:
                post_id = resp.headers.get("x-restli-id", "")
                url = f"https://www.linkedin.com/feed/update/{post_id}" if post_id else ""
                return f"✅ Published to LinkedIn!\nPost ID: {post_id}\nURL: {url}"
        except HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            if e.code == 401:
                return "❌ LinkedIn token EXPIRED. Refresh at https://linkedin.com/developers/tools/oauth"
            return f"❌ LinkedIn publish error: HTTP {e.code}\n{error_body[:200]}"
        except Exception as e:
            return f"❌ LinkedIn publish error: {e}"

    def _publish_image_post(self, token: str, person_id: str, text: str, image_url: str) -> str:
        """Publish a post with image via modern REST API (3-step: init upload, upload binary, create post)."""
        from urllib.request import urlopen, Request
        from urllib.error import HTTPError

        # Step 1: Initialize image upload
        init_payload = {
            "initializeUploadRequest": {
                "owner": f"urn:li:person:{person_id}",
            }
        }
        try:
            req = Request(
                f"{_LINKEDIN_BASE}/rest/images?action=initializeUpload",
                data=json.dumps(init_payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "LinkedIn-Version": _LINKEDIN_API_VERSION,
                },
                method="POST",
            )
            with urlopen(req, timeout=15) as resp:
                init_data = json.loads(resp.read().decode("utf-8"))
                value = init_data.get("value", {})
                upload_url = value.get("uploadUrl", "")
                image_urn = value.get("image", "")
                if not upload_url or not image_urn:
                    return f"❌ LinkedIn image init failed: no uploadUrl or image URN"
        except HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            return f"❌ LinkedIn image init error: HTTP {e.code}\n{error_body[:200]}"
        except Exception as e:
            return f"❌ LinkedIn image init error: {e}"

        # Step 2: Download image and upload to LinkedIn
        try:
            img_req = Request(image_url, headers={"User-Agent": "ZininCorp/1.0"})
            with urlopen(img_req, timeout=30) as img_resp:
                image_data = img_resp.read()

            upload_req = Request(
                upload_url,
                data=image_data,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/octet-stream",
                },
                method="PUT",
            )
            with urlopen(upload_req, timeout=60) as _:
                pass
        except Exception as e:
            return f"❌ LinkedIn image upload error: {e}"

        # Step 3: Create post with image
        post_payload = {
            "author": f"urn:li:person:{person_id}",
            "commentary": text,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "content": {
                "media": {
                    "title": "Image",
                    "id": image_urn,
                }
            },
            "lifecycleState": "PUBLISHED",
        }

        try:
            req = Request(
                f"{_LINKEDIN_BASE}/rest/posts",
                data=json.dumps(post_payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "LinkedIn-Version": _LINKEDIN_API_VERSION,
                    "X-Restli-Protocol-Version": "2.0.0",
                },
                method="POST",
            )
            with urlopen(req, timeout=30) as resp:
                post_id = resp.headers.get("x-restli-id", "")
                url = f"https://www.linkedin.com/feed/update/{post_id}" if post_id else ""
                return f"✅ Published to LinkedIn with image!\nPost ID: {post_id}\nURL: {url}"
        except HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            if e.code == 401:
                return "❌ LinkedIn token EXPIRED."
            return f"❌ LinkedIn image post error: HTTP {e.code}\n{error_body[:200]}"
        except Exception as e:
            return f"❌ LinkedIn image post error: {e}"


# ──────────────────────────────────────────────────────────
# Tool 3b: Threads Publisher (Meta API)
# ──────────────────────────────────────────────────────────

_THREADS_BASE = "https://graph.threads.net/v1.0"


class ThreadsPublisherInput(BaseModel):
    action: str = Field(
        ...,
        description=(
            "Action: 'publish_text' (text post — needs text), "
            "'publish_image' (image post — needs text + image_url), "
            "'publish_carousel' (carousel — needs text + image_urls comma-separated), "
            "'check_token' (verify Threads is configured), "
            "'status' (Threads integration status)"
        ),
    )
    text: Optional[str] = Field(None, description="Post text (max 500 chars)")
    image_url: Optional[str] = Field(None, description="Image URL for single image post")
    image_urls: Optional[str] = Field(
        None, description="Comma-separated image URLs for carousel (2-20 images)"
    )


class ThreadsPublisherTool(BaseTool):
    name: str = "Threads Publisher"
    description: str = (
        "Publishes posts to Threads (Meta) via official API. "
        "Actions: publish_text, publish_image, publish_carousel, check_token, status. "
        "Supports text, image, and carousel posts."
    )
    args_schema: Type[BaseModel] = ThreadsPublisherInput

    def _run(
        self,
        action: str,
        text: str = None,
        image_url: str = None,
        image_urls: str = None,
    ) -> str:
        from urllib.request import urlopen, Request
        from urllib.error import HTTPError
        from urllib.parse import urlencode
        import time

        access_token = os.getenv("THREADS_ACCESS_TOKEN", "")
        user_id = os.getenv("THREADS_USER_ID", "")

        if action == "status":
            configured = bool(access_token and user_id)
            return (
                f"THREADS STATUS:\n"
                f"  Configured: {'✅ Yes' if configured else '❌ No'}\n"
                f"  Token: {'Set' if access_token else 'MISSING'}\n"
                f"  User ID: {'Set' if user_id else 'MISSING'}\n"
                f"  API: {_THREADS_BASE}"
            )

        if action == "check_token":
            if not access_token or not user_id:
                return "❌ THREADS_ACCESS_TOKEN or THREADS_USER_ID not set"
            try:
                params = urlencode({"access_token": access_token})
                req = Request(f"{_THREADS_BASE}/{user_id}?{params}")
                with urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    name = data.get("name", data.get("username", "Unknown"))
                    return f"✅ Threads token valid. User: {name}"
            except HTTPError as e:
                if e.code == 190 or e.code == 401:
                    return "❌ Threads token EXPIRED. Re-authorize at developers.meta.com"
                return f"❌ Threads error: HTTP {e.code}"
            except Exception as e:
                return f"❌ Threads error: {e}"

        if action in ("publish_text", "publish"):
            if not text:
                return "Error: need text to publish"
            if not access_token or not user_id:
                return "❌ Threads not configured. Set THREADS_ACCESS_TOKEN and THREADS_USER_ID."
            if len(text) > 500:
                text = text[:497] + "..."
            return self._publish_text(access_token, user_id, text)

        if action == "publish_image":
            if not text:
                return "Error: need text for image post"
            if not image_url:
                return "Error: need image_url for image post"
            if not access_token or not user_id:
                return "❌ Threads not configured. Set THREADS_ACCESS_TOKEN and THREADS_USER_ID."
            if len(text) > 500:
                text = text[:497] + "..."
            return self._publish_image(access_token, user_id, text, image_url)

        if action == "publish_carousel":
            if not text:
                return "Error: need text for carousel"
            if not image_urls:
                return "Error: need image_urls (comma-separated) for carousel"
            if not access_token or not user_id:
                return "❌ Threads not configured. Set THREADS_ACCESS_TOKEN and THREADS_USER_ID."
            urls = [u.strip() for u in image_urls.split(",") if u.strip()]
            if len(urls) < 2:
                return "Error: carousel needs at least 2 images"
            if len(urls) > 20:
                urls = urls[:20]
            if len(text) > 500:
                text = text[:497] + "..."
            return self._publish_carousel(access_token, user_id, text, urls)

        return f"Unknown action: {action}. Use: publish_text, publish_image, publish_carousel, check_token, status"

    def _create_container(self, token: str, user_id: str, params: dict) -> str:
        """Create a media container. Returns container ID or error string starting with '❌'."""
        from urllib.request import urlopen, Request
        from urllib.error import HTTPError
        from urllib.parse import urlencode

        params["access_token"] = token
        url = f"{_THREADS_BASE}/{user_id}/threads"
        try:
            req = Request(
                url,
                data=urlencode(params).encode("utf-8"),
                method="POST",
            )
            with urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                container_id = data.get("id", "")
                if not container_id:
                    return "❌ Threads: no container ID returned"
                return container_id
        except HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            return f"❌ Threads container error: HTTP {e.code}\n{error_body[:200]}"
        except Exception as e:
            return f"❌ Threads container error: {e}"

    def _publish_container(self, token: str, user_id: str, container_id: str) -> str:
        """Publish a media container. Returns success message or error."""
        from urllib.request import urlopen, Request
        from urllib.error import HTTPError
        from urllib.parse import urlencode
        import time

        # Wait for container processing
        time.sleep(5)

        params = {"creation_id": container_id, "access_token": token}
        url = f"{_THREADS_BASE}/{user_id}/threads_publish"
        try:
            req = Request(
                url,
                data=urlencode(params).encode("utf-8"),
                method="POST",
            )
            with urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                post_id = data.get("id", "")
                return post_id
        except HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            return f"❌ Threads publish error: HTTP {e.code}\n{error_body[:200]}"
        except Exception as e:
            return f"❌ Threads publish error: {e}"

    def _publish_text(self, token: str, user_id: str, text: str) -> str:
        """Publish a text-only Threads post."""
        container_id = self._create_container(token, user_id, {
            "media_type": "TEXT",
            "text": text,
        })
        if container_id.startswith("❌"):
            return container_id

        result = self._publish_container(token, user_id, container_id)
        if result.startswith("❌"):
            return result
        return f"✅ Published to Threads!\nPost ID: {result}\nURL: https://www.threads.net/post/{result}"

    def _publish_image(self, token: str, user_id: str, text: str, image_url: str) -> str:
        """Publish a Threads post with image."""
        container_id = self._create_container(token, user_id, {
            "media_type": "IMAGE",
            "text": text,
            "image_url": image_url,
        })
        if container_id.startswith("❌"):
            return container_id

        result = self._publish_container(token, user_id, container_id)
        if result.startswith("❌"):
            return result
        return f"✅ Published to Threads with image!\nPost ID: {result}\nURL: https://www.threads.net/post/{result}"

    def _publish_carousel(self, token: str, user_id: str, text: str, image_urls: list) -> str:
        """Publish a Threads carousel post (3-step: items → carousel container → publish)."""
        import time

        # Step 1: Create item containers
        item_ids = []
        for url in image_urls:
            item_id = self._create_container(token, user_id, {
                "media_type": "IMAGE",
                "image_url": url,
                "is_carousel_item": "true",
            })
            if item_id.startswith("❌"):
                return f"❌ Carousel item failed: {item_id}"
            item_ids.append(item_id)
            time.sleep(1)

        # Step 2: Create carousel container
        children_str = ",".join(item_ids)
        carousel_id = self._create_container(token, user_id, {
            "media_type": "CAROUSEL",
            "text": text,
            "children": children_str,
        })
        if carousel_id.startswith("❌"):
            return carousel_id

        # Step 3: Publish
        result = self._publish_container(token, user_id, carousel_id)
        if result.startswith("❌"):
            return result
        return (
            f"✅ Published carousel to Threads! ({len(image_urls)} images)\n"
            f"Post ID: {result}\nURL: https://www.threads.net/post/{result}"
        )


# ──────────────────────────────────────────────────────────
# Tool 4: Podcast Script Generator
# ──────────────────────────────────────────────────────────

class PodcastScriptInput(BaseModel):
    topic: str = Field(..., description="Podcast episode topic (e.g., 'AI-агенты в бизнесе')")
    duration_minutes: int = Field(
        10,
        description="Target episode duration in minutes (default 10). ~900 chars/min of speech.",
    )


class PodcastScriptGenerator(BaseTool):
    name: str = "Podcast Script Generator"
    description: str = (
        "Generates a podcast script (monologue) for AI Corporation Podcast. "
        "One voice, Russian language, conversational tone. "
        "Returns plain text ready for TTS."
    )
    args_schema: Type[BaseModel] = PodcastScriptInput

    def _run(self, topic: str, duration_minutes: int = 10) -> str:
        target_chars = duration_minutes * 900  # ~900 chars per minute of speech

        system_prompt = f"""Ты — сценарист подкаста «AI Corporation Podcast».
Пишешь сценарий для ОДНОГО ведущего (монолог). Язык — русский.

⚠️ ФОРМАТ: чистый текст для озвучки. Без заголовков, без markdown, без таймкодов, без ремарок типа [пауза] или (смеётся).
Текст должен читаться вслух естественно, как живая речь.

🎯 ЦЕЛЕВАЯ ДЛИНА: ~{target_chars} символов ({duration_minutes} мин при ~900 символов/мин).

📐 СТРУКТУРА ВЫПУСКА:
1. КРЮЧОК (2-3 предложения) — яркий факт, провокация или вопрос. Сразу цепляет.
2. ВСТУПЛЕНИЕ (2-3 предложения) — «Привет! Это AI Corporation Podcast, и сегодня...»
3. ОСНОВНАЯ ЧАСТЬ (3-4 сегмента по 2-4 абзаца каждый):
   - Каждый сегмент = одна подтема/грань основной темы
   - Начинай сегмент с перехода: «А теперь давайте поговорим о...», «Окей, но вот что интересно...»
   - Конкретные примеры, цифры, кейсы в каждом сегменте
4. ВЫВОД (2-3 предложения) — ключевой инсайт выпуска
5. CTA + OUTRO (2-3 предложения) — «Подписывайтесь...», «Пишите ваши мысли...»

⛔ ЗАПРЕТЫ:
- Никаких менторских поучений: «вам нужно», «вы должны», «попробуйте»
- Никаких клише: «в современном мире», «сегодня мы поговорим»
- Никаких иероглифов/CJK символов
- Никаких markdown, списков с буллетами, заголовков
- Не используй слова: «возможно», «наверное», «кажется», «секрет успеха»

✅ СТИЛЬ:
- Разговорный, живой, как рассказываешь другу за кофе
- Короткие предложения (5-15 слов)
- Паузы через точки, не через запятые
- Личные наблюдения: «Я заметил», «У нас был случай», «Один мой знакомый»
- Конкретные цифры и факты
- Уместный юмор и ирония"""

        user_prompt = f"Напиши сценарий подкаста на тему: {topic}"

        result = _call_llm(user_prompt, system=system_prompt, max_tokens=4000)

        if not result:
            return "Error: LLM call failed. Check OPENROUTER_API_KEY or GROQ_API_KEY."

        # Clean up
        result = _strip_non_cyrillic(result)

        char_count = len(result)
        est_minutes = char_count / 900

        return (
            f"PODCAST SCRIPT GENERATED\n"
            f"Topic: {topic}\n"
            f"Length: {char_count} chars (~{est_minutes:.1f} min)\n"
            f"Target: {target_chars} chars (~{duration_minutes} min)\n"
            f"---\n{result}"
        )
