"""Draft management for Yuki SMM bot — in-memory + JSON backup + auto-cleanup."""

import json
import logging
import os
import time
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

DRAFTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "yuki_drafts")
MAX_DRAFTS = 50
MAX_AGE_SEC = 86400  # 24 hours


class DraftManager:
    """Manages post drafts: create, get, update, delete, cleanup."""

    _drafts: dict[str, dict] = {}
    _editing: dict[int, str] = {}  # user_id → post_id
    _feedback: dict[int, tuple[str, str]] = {}  # user_id → (post_id, mode: "post"|"future")
    _image_feedback: dict[int, str] = {}  # user_id → post_id (post-publish image refinement)

    @classmethod
    def create_draft(
        cls,
        topic: str,
        text: str,
        author: str = "kristina",
        brand: str = "sborka",
        platforms: list[str] | None = None,
        image_path: str = "",
    ) -> str:
        """Create a new draft and return its ID."""
        cls._cleanup()

        post_id = uuid.uuid4().hex[:8]
        cls._drafts[post_id] = {
            "topic": topic,
            "text": text,
            "author": author,
            "brand": brand,
            "platforms": platforms or ["linkedin"],
            "image_path": image_path,
            "status": "pending",  # pending, approved, rejected, published, scheduled
            "reject_reason": "",
            "feedback": "",
            "created_at": time.time(),
            "scheduled_at": "",
            "iteration": 1,
            "max_iterations": 3,
            "feedback_history": [],
            "platform_texts": {},
            "platform_status": {},
            "ratings": {"text": 0, "image": 0, "overall": 0},
            "rating_step": "",
        }
        cls._save_to_disk(post_id)
        logger.info(f"Draft created: {post_id} topic={topic[:40]} author={author}")
        return post_id

    @classmethod
    def get_draft(cls, post_id: str) -> Optional[dict]:
        """Get draft by ID."""
        if post_id in cls._drafts:
            return cls._drafts[post_id]
        return cls._load_from_disk(post_id)

    @classmethod
    def update_draft(cls, post_id: str, **kwargs) -> bool:
        """Update draft fields."""
        draft = cls.get_draft(post_id)
        if not draft:
            return False
        draft.update(kwargs)
        cls._drafts[post_id] = draft
        cls._save_to_disk(post_id)
        return True

    @classmethod
    def set_editing(cls, user_id: int, post_id: str) -> None:
        cls._editing[user_id] = post_id

    @classmethod
    def get_editing(cls, user_id: int) -> Optional[str]:
        return cls._editing.get(user_id)

    @classmethod
    def clear_editing(cls, user_id: int) -> None:
        cls._editing.pop(user_id, None)

    @classmethod
    def set_feedback(cls, user_id: int, post_id: str, mode: str) -> None:
        """Set feedback mode: mode is 'post' (this post) or 'future' (general)."""
        cls._feedback[user_id] = (post_id, mode)

    @classmethod
    def get_feedback(cls, user_id: int) -> Optional[tuple[str, str]]:
        """Returns (post_id, mode) or None."""
        return cls._feedback.get(user_id)

    @classmethod
    def clear_feedback(cls, user_id: int) -> None:
        cls._feedback.pop(user_id, None)

    @classmethod
    def set_image_feedback(cls, user_id: int, post_id: str) -> None:
        """Set post-publish image feedback mode."""
        cls._image_feedback[user_id] = post_id

    @classmethod
    def get_image_feedback(cls, user_id: int) -> Optional[str]:
        """Returns post_id for image feedback or None."""
        return cls._image_feedback.get(user_id)

    @classmethod
    def clear_image_feedback(cls, user_id: int) -> None:
        cls._image_feedback.pop(user_id, None)

    @classmethod
    def active_count(cls) -> int:
        """Count non-published/rejected drafts."""
        return sum(
            1 for d in cls._drafts.values()
            if d.get("status") in ("pending", "approved", "scheduled")
        )

    @classmethod
    def _cleanup(cls) -> None:
        """Remove old and excess drafts."""
        now = time.time()
        to_remove = []

        for pid, draft in cls._drafts.items():
            created = draft.get("created_at", 0)
            status = draft.get("status", "pending")
            # Remove old non-active drafts
            if status in ("published", "rejected") and (now - created) > MAX_AGE_SEC:
                to_remove.append(pid)
            # Remove very old drafts regardless of status
            elif (now - created) > MAX_AGE_SEC * 3:
                to_remove.append(pid)

        for pid in to_remove:
            cls._drafts.pop(pid, None)
            cls._remove_from_disk(pid)

        # If still over limit, remove oldest
        if len(cls._drafts) > MAX_DRAFTS:
            sorted_ids = sorted(
                cls._drafts, key=lambda k: cls._drafts[k].get("created_at", 0)
            )
            for pid in sorted_ids[: len(cls._drafts) - MAX_DRAFTS]:
                cls._drafts.pop(pid, None)
                cls._remove_from_disk(pid)

        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old drafts")

    @classmethod
    def _save_to_disk(cls, post_id: str) -> None:
        try:
            os.makedirs(DRAFTS_DIR, exist_ok=True)
            path = os.path.join(DRAFTS_DIR, f"{post_id}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cls._drafts[post_id], f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save draft {post_id}: {e}")

    @classmethod
    def _load_from_disk(cls, post_id: str) -> Optional[dict]:
        try:
            path = os.path.join(DRAFTS_DIR, f"{post_id}.json")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    draft = json.load(f)
                cls._drafts[post_id] = draft
                return draft
        except Exception as e:
            logger.warning(f"Failed to load draft {post_id}: {e}")
        return None

    @classmethod
    def _remove_from_disk(cls, post_id: str) -> None:
        try:
            path = os.path.join(DRAFTS_DIR, f"{post_id}.json")
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
