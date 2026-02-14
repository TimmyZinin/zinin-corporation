"""Post ratings storage — JSON persistence for learning loop.

Stores per-post ratings (text, image, overall) and aggregates per-author stats.
Used by ContentGenerator and image_gen to improve future generations.
"""

import json
import logging
import os
import threading
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "yuki_memory", "episodic")
_RATINGS_PATH = os.path.join(_DATA_DIR, "ratings.json")
_lock = threading.Lock()


def _ratings_path() -> str:
    return _RATINGS_PATH


def _load() -> dict:
    path = _ratings_path()
    with _lock:
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
        except Exception as e:
            logger.warning(f"Failed to load ratings: {e}")
    return {"ratings": [], "aggregated": {}}


def _save(data: dict) -> bool:
    path = _ratings_path()
    with _lock:
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.warning(f"Failed to save ratings: {e}")
            return False


class RatingStore:
    """Stores and aggregates post ratings per author."""

    @classmethod
    def record_rating(
        cls,
        post_id: str,
        author: str,
        brand: str = "sborka",
        platform: str = "linkedin",
        topic: str = "",
        text_score: int = 0,
        image_score: int = 0,
        overall_score: int = 0,
        image_feedback: str = "",
    ) -> dict:
        """Record a post rating. Returns the rating entry."""
        entry = {
            "post_id": post_id,
            "author": author,
            "brand": brand,
            "platform": platform,
            "topic": topic[:200],
            "text_score": text_score,
            "image_score": image_score,
            "overall_score": overall_score,
            "image_feedback": image_feedback[:500],
            "timestamp": datetime.now().isoformat(),
        }

        data = _load()
        data["ratings"].append(entry)

        # Keep last 500 ratings
        if len(data["ratings"]) > 500:
            data["ratings"] = data["ratings"][-500:]

        # Update aggregated stats
        cls._update_aggregated(data)
        _save(data)

        logger.info(f"Rating recorded: {post_id} author={author} text={text_score} img={image_score} overall={overall_score}")
        return entry

    @classmethod
    def get_author_stats(cls, author: str) -> dict:
        """Get aggregated stats for an author.

        Returns: {avg_text, avg_image, avg_overall, common_image_feedback, count}
        """
        data = _load()
        stats = data.get("aggregated", {}).get(author, {})
        return {
            "avg_text": stats.get("avg_text", 0.0),
            "avg_image": stats.get("avg_image", 0.0),
            "avg_overall": stats.get("avg_overall", 0.0),
            "common_image_feedback": stats.get("common_image_feedback", []),
            "count": stats.get("count", 0),
        }

    @classmethod
    def get_recent_issues(cls, author: str = "", n: int = 10) -> list[str]:
        """Get last N non-empty image feedback strings.

        If author is empty, returns feedback from all authors.
        """
        data = _load()
        feedbacks = []
        for r in reversed(data.get("ratings", [])):
            if author and r.get("author") != author:
                continue
            fb = r.get("image_feedback", "").strip()
            if fb:
                feedbacks.append(fb)
            if len(feedbacks) >= n:
                break
        return feedbacks

    @classmethod
    def format_stats(cls) -> str:
        """Format all author stats for /reflexion command."""
        data = _load()
        agg = data.get("aggregated", {})
        if not agg:
            return "📊 Оценки: пока нет данных"

        lines = ["📊 Статистика оценок:"]
        for author, stats in agg.items():
            count = stats.get("count", 0)
            if count == 0:
                continue
            avg_t = stats.get("avg_text", 0)
            avg_i = stats.get("avg_image", 0)
            avg_o = stats.get("avg_overall", 0)
            label = "Кристина" if author == "kristina" else "Тим"
            lines.append(
                f"\n  {label} ({count} постов):\n"
                f"    Текст: {avg_t:.1f}/5 | Картинка: {avg_i:.1f}/5 | Общая: {avg_o:.1f}/5"
            )
            issues = stats.get("common_image_feedback", [])
            if issues:
                lines.append(f"    Частые замечания: {', '.join(issues[:3])}")

        return "\n".join(lines)

    @classmethod
    def _update_aggregated(cls, data: dict) -> None:
        """Recalculate aggregated stats from all ratings."""
        by_author: dict[str, list[dict]] = {}
        for r in data.get("ratings", []):
            author = r.get("author", "unknown")
            by_author.setdefault(author, []).append(r)

        aggregated = {}
        for author, ratings in by_author.items():
            count = len(ratings)

            text_scores = [r["text_score"] for r in ratings if r.get("text_score", 0) > 0]
            image_scores = [r["image_score"] for r in ratings if r.get("image_score", 0) > 0]
            overall_scores = [r["overall_score"] for r in ratings if r.get("overall_score", 0) > 0]

            avg_text = sum(text_scores) / len(text_scores) if text_scores else 0.0
            avg_image = sum(image_scores) / len(image_scores) if image_scores else 0.0
            avg_overall = sum(overall_scores) / len(overall_scores) if overall_scores else 0.0

            # Collect common image feedback (last 20, deduplicated)
            feedbacks = []
            seen = set()
            for r in reversed(ratings):
                fb = r.get("image_feedback", "").strip()
                if fb and fb.lower() not in seen:
                    feedbacks.append(fb)
                    seen.add(fb.lower())
                if len(feedbacks) >= 5:
                    break

            aggregated[author] = {
                "avg_text": round(avg_text, 2),
                "avg_image": round(avg_image, 2),
                "avg_overall": round(avg_overall, 2),
                "common_image_feedback": feedbacks,
                "count": count,
            }

        data["aggregated"] = aggregated
