"""Tests for src/image_registry.py — Image Registry CRUD + Gallery + Cleanup."""

import json
import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

from src.image_registry import (
    register_image,
    get_images,
    get_image_by_id,
    update_status,
    forward_to_agent,
    get_gallery,
    cleanup_expired,
    get_stats,
    STATUS_PENDING,
    STATUS_APPROVED,
    STATUS_REJECTED,
    TTL_DAYS,
    _load_registry,
    _save_registry,
)


@pytest.fixture(autouse=True)
def tmp_registry(tmp_path):
    """Redirect registry to temp file for every test."""
    path = str(tmp_path / "image_registry.json")
    with patch("src.image_registry._registry_path", return_value=path):
        yield path


# ──────────────────────────────────────────────────────────
# Register
# ──────────────────────────────────────────────────────────

class TestRegisterImage:
    def test_register_returns_entry(self, tmp_registry):
        entry = register_image("/img/test.png", source_agent="designer", style="isotype", topic="AI")
        assert entry["path"] == "/img/test.png"
        assert entry["source_agent"] == "designer"
        assert entry["style"] == "isotype"
        assert entry["topic"] == "AI"
        assert entry["status"] == STATUS_PENDING
        assert entry["forwarded_to"] == ""
        assert len(entry["id"]) == 12

    def test_register_persists_to_file(self, tmp_registry):
        register_image("/img/a.png")
        with open(tmp_registry, "r") as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["path"] == "/img/a.png"

    def test_register_multiple(self, tmp_registry):
        register_image("/img/a.png")
        register_image("/img/b.png")
        register_image("/img/c.png")
        with open(tmp_registry, "r") as f:
            data = json.load(f)
        assert len(data) == 3

    def test_register_unique_ids(self, tmp_registry):
        ids = set()
        for i in range(10):
            entry = register_image(f"/img/{i}.png")
            ids.add(entry["id"])
        assert len(ids) == 10

    def test_register_defaults(self, tmp_registry):
        entry = register_image("/img/x.png")
        assert entry["source_agent"] == "designer"
        assert entry["style"] == "auto"
        assert entry["topic"] == ""
        assert entry["metadata"] == {}

    def test_register_with_metadata(self, tmp_registry):
        entry = register_image("/img/x.png", metadata={"width": 1024, "model": "gemini"})
        assert entry["metadata"]["width"] == 1024
        assert entry["metadata"]["model"] == "gemini"

    def test_register_created_at_format(self, tmp_registry):
        entry = register_image("/img/x.png")
        # Should be parseable ISO format
        dt = datetime.fromisoformat(entry["created_at"])
        assert isinstance(dt, datetime)


# ──────────────────────────────────────────────────────────
# Get images
# ──────────────────────────────────────────────────────────

class TestGetImages:
    def test_get_all(self, tmp_registry):
        register_image("/img/a.png")
        register_image("/img/b.png")
        images = get_images()
        assert len(images) == 2

    def test_get_empty(self, tmp_registry):
        assert get_images() == []

    def test_filter_by_status(self, tmp_registry):
        e1 = register_image("/img/a.png")
        e2 = register_image("/img/b.png")
        update_status(e1["id"], STATUS_APPROVED)
        pending = get_images(status=STATUS_PENDING)
        assert len(pending) == 1
        assert pending[0]["id"] == e2["id"]

    def test_filter_by_agent(self, tmp_registry):
        register_image("/img/a.png", source_agent="designer")
        register_image("/img/b.png", source_agent="smm")
        designer_imgs = get_images(source_agent="designer")
        assert len(designer_imgs) == 1
        assert designer_imgs[0]["source_agent"] == "designer"

    def test_limit_and_offset(self, tmp_registry):
        for i in range(5):
            register_image(f"/img/{i}.png")
        page1 = get_images(limit=2, offset=0)
        page2 = get_images(limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) == 2
        # No overlap
        ids1 = {img["id"] for img in page1}
        ids2 = {img["id"] for img in page2}
        assert ids1.isdisjoint(ids2)

    def test_sorted_newest_first(self, tmp_registry):
        e1 = register_image("/img/a.png")
        e2 = register_image("/img/b.png")
        images = get_images()
        # Second registered should be first (newest)
        assert images[0]["id"] == e2["id"]


# ──────────────────────────────────────────────────────────
# Get by ID
# ──────────────────────────────────────────────────────────

class TestGetImageById:
    def test_found(self, tmp_registry):
        entry = register_image("/img/a.png")
        result = get_image_by_id(entry["id"])
        assert result is not None
        assert result["path"] == "/img/a.png"

    def test_not_found(self, tmp_registry):
        assert get_image_by_id("nonexistent") is None

    def test_correct_id(self, tmp_registry):
        e1 = register_image("/img/a.png")
        e2 = register_image("/img/b.png")
        result = get_image_by_id(e1["id"])
        assert result["path"] == "/img/a.png"


# ──────────────────────────────────────────────────────────
# Update status
# ──────────────────────────────────────────────────────────

class TestUpdateStatus:
    def test_approve(self, tmp_registry):
        entry = register_image("/img/a.png")
        result = update_status(entry["id"], STATUS_APPROVED)
        assert result is not None
        assert result["status"] == STATUS_APPROVED
        assert result["reviewed_at"] != ""

    def test_reject(self, tmp_registry):
        entry = register_image("/img/a.png")
        result = update_status(entry["id"], STATUS_REJECTED)
        assert result["status"] == STATUS_REJECTED

    def test_invalid_status(self, tmp_registry):
        entry = register_image("/img/a.png")
        result = update_status(entry["id"], "invalid_status")
        assert result is None

    def test_not_found(self, tmp_registry):
        result = update_status("nonexistent", STATUS_APPROVED)
        assert result is None

    def test_persisted(self, tmp_registry):
        entry = register_image("/img/a.png")
        update_status(entry["id"], STATUS_APPROVED)
        reloaded = get_image_by_id(entry["id"])
        assert reloaded["status"] == STATUS_APPROVED


# ──────────────────────────────────────────────────────────
# Forward to agent
# ──────────────────────────────────────────────────────────

class TestForwardToAgent:
    def test_forward(self, tmp_registry):
        entry = register_image("/img/a.png")
        result = forward_to_agent(entry["id"], "smm")
        assert result is not None
        assert result["forwarded_to"] == "smm"

    def test_forward_not_found(self, tmp_registry):
        result = forward_to_agent("nonexistent", "smm")
        assert result is None

    def test_forward_persisted(self, tmp_registry):
        entry = register_image("/img/a.png")
        forward_to_agent(entry["id"], "smm")
        reloaded = get_image_by_id(entry["id"])
        assert reloaded["forwarded_to"] == "smm"


# ──────────────────────────────────────────────────────────
# Gallery
# ──────────────────────────────────────────────────────────

class TestGetGallery:
    def test_empty_gallery(self, tmp_registry):
        gallery = get_gallery()
        assert gallery["images"] == []
        assert gallery["total"] == 0
        assert gallery["page"] == 0
        assert gallery["pages"] == 1

    def test_basic_gallery(self, tmp_registry):
        register_image("/img/a.png")
        register_image("/img/b.png")
        gallery = get_gallery()
        assert gallery["total"] == 2
        assert len(gallery["images"]) == 2

    def test_excludes_rejected(self, tmp_registry):
        e1 = register_image("/img/a.png")
        e2 = register_image("/img/b.png")
        update_status(e1["id"], STATUS_REJECTED)
        gallery = get_gallery()
        assert gallery["total"] == 1
        assert gallery["images"][0]["id"] == e2["id"]

    def test_pending_first(self, tmp_registry):
        e1 = register_image("/img/a.png")
        e2 = register_image("/img/b.png")
        update_status(e1["id"], STATUS_APPROVED)
        gallery = get_gallery()
        # At least one pending (e2) should appear before approved (e1)
        statuses = [img["status"] for img in gallery["images"]]
        # All pending items come before approved items
        pending_indices = [i for i, s in enumerate(statuses) if s == STATUS_PENDING]
        approved_indices = [i for i, s in enumerate(statuses) if s == STATUS_APPROVED]
        if pending_indices and approved_indices:
            assert max(pending_indices) < min(approved_indices)

    def test_pagination(self, tmp_registry):
        for i in range(12):
            register_image(f"/img/{i}.png")
        g1 = get_gallery(limit=5, page=0)
        g2 = get_gallery(limit=5, page=1)
        g3 = get_gallery(limit=5, page=2)
        assert len(g1["images"]) == 5
        assert len(g2["images"]) == 5
        assert len(g3["images"]) == 2
        assert g1["pages"] == 3
        assert g1["total"] == 12

    def test_page_out_of_range(self, tmp_registry):
        register_image("/img/a.png")
        gallery = get_gallery(limit=5, page=10)
        assert gallery["images"] == []

    def test_gallery_pages_calculation(self, tmp_registry):
        for i in range(7):
            register_image(f"/img/{i}.png")
        gallery = get_gallery(limit=3)
        assert gallery["pages"] == 3  # ceil(7/3)


# ──────────────────────────────────────────────────────────
# Cleanup expired
# ──────────────────────────────────────────────────────────

class TestCleanupExpired:
    def test_no_expired(self, tmp_registry):
        register_image("/img/a.png")
        removed = cleanup_expired()
        assert removed == 0

    def test_removes_old_pending(self, tmp_registry):
        entry = register_image("/img/old.png")
        # Manually backdate
        with open(tmp_registry, "r") as f:
            data = json.load(f)
        old_date = (datetime.now() - timedelta(days=TTL_DAYS + 1)).isoformat()
        data[0]["created_at"] = old_date
        with open(tmp_registry, "w") as f:
            json.dump(data, f)
        removed = cleanup_expired()
        assert removed == 1
        assert get_images() == []

    def test_keeps_approved(self, tmp_registry):
        entry = register_image("/img/old.png")
        update_status(entry["id"], STATUS_APPROVED)
        # Backdate
        with open(tmp_registry, "r") as f:
            data = json.load(f)
        old_date = (datetime.now() - timedelta(days=TTL_DAYS + 1)).isoformat()
        data[0]["created_at"] = old_date
        with open(tmp_registry, "w") as f:
            json.dump(data, f)
        removed = cleanup_expired()
        assert removed == 0  # Approved images are kept

    def test_keeps_recent_pending(self, tmp_registry):
        register_image("/img/new.png")
        removed = cleanup_expired()
        assert removed == 0


# ──────────────────────────────────────────────────────────
# Stats
# ──────────────────────────────────────────────────────────

class TestGetStats:
    def test_empty_stats(self, tmp_registry):
        stats = get_stats()
        assert stats["total"] == 0
        assert stats["by_status"] == {}
        assert stats["by_agent"] == {}

    def test_stats_counts(self, tmp_registry):
        e1 = register_image("/img/a.png", source_agent="designer")
        e2 = register_image("/img/b.png", source_agent="smm")
        e3 = register_image("/img/c.png", source_agent="designer")
        update_status(e1["id"], STATUS_APPROVED)
        stats = get_stats()
        assert stats["total"] == 3
        assert stats["by_status"]["pending"] == 2
        assert stats["by_status"]["approved"] == 1
        assert stats["by_agent"]["designer"] == 2
        assert stats["by_agent"]["smm"] == 1


# ──────────────────────────────────────────────────────────
# Load / Save edge cases
# ──────────────────────────────────────────────────────────

class TestLoadSaveEdge:
    def test_load_missing_file(self, tmp_registry):
        """Missing file → empty list."""
        if os.path.exists(tmp_registry):
            os.remove(tmp_registry)
        result = _load_registry()
        assert result == []

    def test_load_corrupted_json(self, tmp_registry):
        """Corrupted JSON → empty list."""
        with open(tmp_registry, "w") as f:
            f.write("{bad json!!!}")
        result = _load_registry()
        assert result == []

    def test_load_non_list(self, tmp_registry):
        """JSON that's not a list → empty list."""
        with open(tmp_registry, "w") as f:
            json.dump({"not": "a list"}, f)
        result = _load_registry()
        assert result == []

    def test_save_creates_dir(self, tmp_path):
        """Save creates parent directories."""
        deep_path = str(tmp_path / "a" / "b" / "registry.json")
        with patch("src.image_registry._registry_path", return_value=deep_path):
            result = _save_registry([{"test": True}])
            assert result is True
            assert os.path.exists(deep_path)
