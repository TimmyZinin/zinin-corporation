"""
🖼️ Zinin Corp — Image Registry

Thread-safe JSON persistence for generated images.
Tracks metadata: source agent, style, topic, status, approval flow.
Used by Gallery command and Yuki→Ryan pipeline.
"""

import json
import logging
import os
import threading
import uuid
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

_lock = threading.Lock()

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_REGISTRY_PATH = os.path.join(_DATA_DIR, "image_registry.json")

# TTL for unreviewed images (days)
TTL_DAYS = 7

# Statuses
STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"


def _registry_path() -> str:
    """Patchable path for tests."""
    return _REGISTRY_PATH


def _load_registry() -> list[dict]:
    path = _registry_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as e:
            logger.warning("Failed to load image registry: %s", e)
    return []


def _save_registry(data: list[dict]) -> bool:
    path = _registry_path()
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        return True
    except Exception as e:
        logger.warning("Failed to save image registry: %s", e)
        return False


def register_image(
    path: str,
    source_agent: str = "designer",
    style: str = "auto",
    topic: str = "",
    metadata: dict | None = None,
) -> dict:
    """Register a new image in the registry. Returns the entry."""
    entry = {
        "id": uuid.uuid4().hex[:12],
        "path": path,
        "source_agent": source_agent,
        "style": style,
        "topic": topic,
        "status": STATUS_PENDING,
        "forwarded_to": "",
        "created_at": datetime.now().isoformat(),
        "reviewed_at": "",
        "metadata": metadata or {},
    }
    with _lock:
        registry = _load_registry()
        registry.append(entry)
        _save_registry(registry)
    logger.info("Registered image %s from %s: %s", entry["id"], source_agent, path)
    return entry


def get_images(
    status: str | None = None,
    source_agent: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[dict]:
    """Get images filtered by status and/or source agent."""
    with _lock:
        registry = _load_registry()

    filtered = registry
    if status:
        filtered = [e for e in filtered if e.get("status") == status]
    if source_agent:
        filtered = [e for e in filtered if e.get("source_agent") == source_agent]

    # Sort by created_at descending (newest first)
    filtered.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return filtered[offset : offset + limit]


def get_image_by_id(image_id: str) -> dict | None:
    """Get a single image by ID."""
    with _lock:
        registry = _load_registry()
    for entry in registry:
        if entry.get("id") == image_id:
            return entry
    return None


def update_status(image_id: str, status: str) -> dict | None:
    """Update image status (approved/rejected). Returns updated entry or None."""
    if status not in (STATUS_APPROVED, STATUS_REJECTED, STATUS_PENDING):
        return None

    with _lock:
        registry = _load_registry()
        for entry in registry:
            if entry.get("id") == image_id:
                entry["status"] = status
                entry["reviewed_at"] = datetime.now().isoformat()
                _save_registry(registry)
                logger.info("Image %s → %s", image_id, status)
                return entry
    return None


def forward_to_agent(image_id: str, agent: str) -> dict | None:
    """Mark image as forwarded to another agent. Returns updated entry."""
    with _lock:
        registry = _load_registry()
        for entry in registry:
            if entry.get("id") == image_id:
                entry["forwarded_to"] = agent
                _save_registry(registry)
                logger.info("Image %s forwarded to %s", image_id, agent)
                return entry
    return None


def get_gallery(limit: int = 10, page: int = 0) -> dict:
    """Get paginated gallery: pending first, then recent approved.

    Returns: {"images": [...], "total": int, "page": int, "pages": int}
    """
    with _lock:
        registry = _load_registry()

    # Pending first, then approved, skip rejected
    visible = [e for e in registry if e.get("status") != STATUS_REJECTED]

    # Sort: pending first (by created_at desc), then approved (by reviewed_at desc)
    def sort_key(e):
        is_pending = 1 if e.get("status") == STATUS_PENDING else 0
        ts = e.get("created_at", "")
        return (is_pending, ts)

    visible.sort(key=sort_key, reverse=True)

    total = len(visible)
    pages = max(1, (total + limit - 1) // limit)
    offset = page * limit
    images = visible[offset : offset + limit]

    return {
        "images": images,
        "total": total,
        "page": page,
        "pages": pages,
    }


def cleanup_expired() -> int:
    """Remove pending images older than TTL_DAYS. Returns count removed."""
    cutoff = datetime.now() - timedelta(days=TTL_DAYS)
    removed = 0

    with _lock:
        registry = _load_registry()
        original_len = len(registry)
        registry = [
            e for e in registry
            if not (
                e.get("status") == STATUS_PENDING
                and e.get("created_at", "9999") < cutoff.isoformat()
            )
        ]
        removed = original_len - len(registry)
        if removed > 0:
            _save_registry(registry)
            logger.info("Cleaned up %d expired images", removed)

    return removed


def get_stats() -> dict:
    """Get registry statistics."""
    with _lock:
        registry = _load_registry()

    total = len(registry)
    by_status = {}
    by_agent = {}
    for entry in registry:
        s = entry.get("status", "unknown")
        a = entry.get("source_agent", "unknown")
        by_status[s] = by_status.get(s, 0) + 1
        by_agent[a] = by_agent.get(a, 0) + 1

    return {
        "total": total,
        "by_status": by_status,
        "by_agent": by_agent,
    }
