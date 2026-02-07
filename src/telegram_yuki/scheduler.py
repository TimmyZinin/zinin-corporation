"""Scheduled post manager for Yuki SMM bot."""

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

SCHEDULE_FILE = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "yuki_drafts", "schedule.json"
)


class PostScheduler:
    """Manages scheduled posts — stores queue, checks for due posts."""

    _queue: list[dict] = []

    @classmethod
    def schedule(
        cls,
        post_id: str,
        platforms: list[str],
        publish_at: datetime,
    ) -> None:
        """Add a post to the schedule queue."""
        entry = {
            "post_id": post_id,
            "platforms": platforms,
            "publish_at": publish_at.isoformat(),
            "status": "scheduled",  # scheduled, publishing, published, failed
        }
        cls._queue.append(entry)
        cls._save()
        logger.info(
            f"Scheduled post {post_id} for {publish_at.strftime('%H:%M %d.%m')} "
            f"on {', '.join(platforms)}"
        )

    @classmethod
    def get_due_posts(cls) -> list[dict]:
        """Get posts that are due for publishing (publish_at <= now)."""
        now = datetime.now(timezone.utc)
        due = []
        for entry in cls._queue:
            if entry["status"] != "scheduled":
                continue
            publish_at = datetime.fromisoformat(entry["publish_at"])
            if publish_at.tzinfo is None:
                publish_at = publish_at.replace(tzinfo=timezone.utc)
            if publish_at <= now:
                due.append(entry)
        return due

    @classmethod
    def mark_published(cls, post_id: str) -> None:
        for entry in cls._queue:
            if entry["post_id"] == post_id:
                entry["status"] = "published"
        cls._save()

    @classmethod
    def mark_failed(cls, post_id: str, error: str = "") -> None:
        for entry in cls._queue:
            if entry["post_id"] == post_id:
                entry["status"] = "failed"
                entry["error"] = error
        cls._save()

    @classmethod
    def get_scheduled(cls) -> list[dict]:
        """Get all pending scheduled posts."""
        return [e for e in cls._queue if e["status"] == "scheduled"]

    @classmethod
    def cancel(cls, post_id: str) -> bool:
        """Cancel a scheduled post."""
        for entry in cls._queue:
            if entry["post_id"] == post_id and entry["status"] == "scheduled":
                entry["status"] = "cancelled"
                cls._save()
                return True
        return False

    @classmethod
    def _save(cls):
        try:
            os.makedirs(os.path.dirname(SCHEDULE_FILE), exist_ok=True)
            with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
                json.dump(cls._queue, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save schedule: {e}")

    @classmethod
    def _load(cls):
        try:
            if os.path.exists(SCHEDULE_FILE):
                with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
                    cls._queue = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load schedule: {e}")

    @classmethod
    def cleanup_old(cls, days: int = 7):
        """Remove entries older than N days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        before = len(cls._queue)
        cls._queue = [
            e for e in cls._queue
            if e["status"] == "scheduled"
            or datetime.fromisoformat(e["publish_at"]).replace(tzinfo=timezone.utc) > cutoff
        ]
        removed = before - len(cls._queue)
        if removed:
            cls._save()
            logger.info(f"Cleaned up {removed} old schedule entries")


def get_schedule_time(offset_key: str) -> datetime:
    """Convert a schedule offset key to an absolute datetime.

    Keys: 'now', '1h', '3h', 'tomorrow', 'evening'
    """
    now = datetime.now(timezone.utc)
    offsets = {
        "now": timedelta(0),
        "1h": timedelta(hours=1),
        "3h": timedelta(hours=3),
        "tomorrow": timedelta(days=1) - timedelta(hours=now.hour, minutes=now.minute) + timedelta(hours=10),
        "evening": timedelta(hours=max(0, 18 - now.hour)),
    }
    delta = offsets.get(offset_key, timedelta(0))
    return now + delta


# Load on import
PostScheduler._load()
