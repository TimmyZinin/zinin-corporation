"""Draft management for Yuki SMM bot — in-memory + JSON backup."""

import json
import logging
import os
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

DRAFTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "yuki_drafts")


class DraftManager:
    """Manages post drafts: create, get, update, delete."""

    _drafts: dict[str, dict] = {}
    _editing: dict[int, str] = {}  # user_id → post_id

    @classmethod
    def create_draft(
        cls,
        topic: str,
        text: str,
        author: str = "kristina",
        platform: str = "linkedin",
        image_path: str = "",
    ) -> str:
        """Create a new draft and return its ID."""
        post_id = uuid.uuid4().hex[:8]
        cls._drafts[post_id] = {
            "topic": topic,
            "text": text,
            "author": author,
            "platform": platform,
            "image_path": image_path,
            "status": "pending",  # pending, approved, rejected, published
            "reject_reason": "",
            "feedback": "",
        }
        cls._save_to_disk(post_id)
        logger.info(f"Draft created: {post_id} topic={topic[:40]}")
        return post_id

    @classmethod
    def get_draft(cls, post_id: str) -> Optional[dict]:
        """Get draft by ID."""
        if post_id in cls._drafts:
            return cls._drafts[post_id]
        # Try loading from disk
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
        """Mark user as editing a specific draft."""
        cls._editing[user_id] = post_id

    @classmethod
    def get_editing(cls, user_id: int) -> Optional[str]:
        """Get the draft ID the user is currently editing."""
        return cls._editing.get(user_id)

    @classmethod
    def clear_editing(cls, user_id: int) -> None:
        """Clear editing state for user."""
        cls._editing.pop(user_id, None)

    @classmethod
    def _save_to_disk(cls, post_id: str) -> None:
        """Persist draft to JSON file."""
        try:
            os.makedirs(DRAFTS_DIR, exist_ok=True)
            path = os.path.join(DRAFTS_DIR, f"{post_id}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cls._drafts[post_id], f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save draft {post_id}: {e}")

    @classmethod
    def _load_from_disk(cls, post_id: str) -> Optional[dict]:
        """Load draft from JSON file."""
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
