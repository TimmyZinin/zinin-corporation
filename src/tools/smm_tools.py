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
]


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
    boring_starts = ["сегодня я", "хочу рассказать", "в этом посте", "привет всем"]
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
    length = len(content)
    if 1200 <= length <= 3000:
        score += 0.2
    elif length < 800:
        issues.append(f"TONE: Пост слишком короткий ({length} символов, нужно 1200+)")
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

ОБЯЗАТЕЛЬНАЯ СТРУКТУРА (все 6 частей):
1. Крючок (1-2 предложения) — провокационный, с цифрами, хватает за внимание
2. Проблема (2-3 предложения) — боль, симптомы, масштаб
3. История/Кейс (3-5 предложений) — конкретный пример, трансформация
4. Инсайт/Анализ (5-7 предложений) — почему так, системный взгляд
5. Решение/Действие (3-5 пунктов) — практические шаги, формулы
6. Вывод + CTA (1-2 предложения) — ключевая мысль + что делать

ПРАВИЛА:
{rules_text}

ЗАПРЕЩЕНО использовать: {', '.join(forbidden[:8])}

Длина: 1500-2500 символов для LinkedIn.
Язык: русский.
Подпись в конце: «— {author}\nСБОРКА — клуб карьерной дисциплины»

Пиши живо, уверенно, с конкретными цифрами и примерами."""

        user_prompt = f"Напиши экспертный пост для {platform.upper()} на тему: {topic}"

        result = _call_llm(user_prompt, system=system_prompt, max_tokens=2000)

        if not result:
            return "Error: LLM call failed. Check OPENROUTER_API_KEY or GROQ_API_KEY."

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
# Tool 3: LinkedIn Publisher
# ──────────────────────────────────────────────────────────

class LinkedInPublisherInput(BaseModel):
    action: str = Field(
        ...,
        description=(
            "Action: 'publish' (publish post — needs text), "
            "'check_token' (check if LinkedIn is configured), "
            "'status' (LinkedIn integration status)"
        ),
    )
    text: Optional[str] = Field(None, description="Post text to publish")


class LinkedInPublisherTool(BaseTool):
    name: str = "LinkedIn Publisher"
    description: str = (
        "Publishes posts to LinkedIn via API v2. "
        "Actions: publish, check_token, status."
    )
    args_schema: Type[BaseModel] = LinkedInPublisherInput

    def _run(self, action: str, text: str = None) -> str:
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
                f"  Person ID: {'Set' if person_id else 'MISSING'}"
            )

        if action == "check_token":
            if not access_token:
                return "❌ LINKEDIN_ACCESS_TOKEN not set"
            try:
                req = Request(
                    "https://api.linkedin.com/v2/userinfo",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "LinkedIn-Version": "202502",
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

        if action == "publish":
            if not text:
                return "Error: need text to publish"
            if not access_token or not person_id:
                return "❌ LinkedIn not configured. Set LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_ID."

            if len(text) > 3000:
                text = text[:2997] + "..."

            payload = {
                "author": f"urn:li:person:{person_id}",
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": text},
                        "shareMediaCategory": "NONE",
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                },
            }

            try:
                req = Request(
                    "https://api.linkedin.com/v2/ugcPosts",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                        "LinkedIn-Version": "202502",
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

        return f"Unknown action: {action}"
