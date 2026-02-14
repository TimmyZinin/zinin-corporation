"""Tests for CallbackData Factory — typed callback routing (Sprint 10)."""

import pytest

from src.telegram_ceo.callback_factory import (
    TaskCB, EscCB, CtoCB, ApiCB, ActionCB,
    EveningCB, GalleryCB, VoiceBrainCB, SubMenuCB,
)


# ═══════════════════════════════════════════════════════════════
# TaskCB — 6 tests
# ═══════════════════════════════════════════════════════════════

class TestTaskCB:
    def test_pack_minimal(self):
        assert TaskCB(action="new").pack() == "task:new::"

    def test_pack_with_id(self):
        assert TaskCB(action="assign", id="abc").pack() == "task:assign:abc:"

    def test_pack_with_id_and_agent(self):
        assert TaskCB(action="do_assign", id="abc", agent="smm").pack() == "task:do_assign:abc:smm"

    def test_unpack(self):
        cb = TaskCB.unpack("task:filter:TODO:")
        assert cb.action == "filter"
        assert cb.id == "TODO"
        assert cb.agent == ""

    def test_prefix(self):
        assert TaskCB.__prefix__ == "task"

    def test_defaults(self):
        cb = TaskCB(action="all")
        assert cb.id == ""
        assert cb.agent == ""


# ═══════════════════════════════════════════════════════════════
# EscCB — 3 tests
# ═══════════════════════════════════════════════════════════════

class TestEscCB:
    def test_pack(self):
        assert EscCB(action="extend", id="abc").pack() == "esc:extend:abc"

    def test_unpack(self):
        cb = EscCB.unpack("esc:split:t1")
        assert cb.action == "split"
        assert cb.id == "t1"

    def test_prefix(self):
        assert EscCB.__prefix__ == "esc"


# ═══════════════════════════════════════════════════════════════
# CtoCB — 3 tests
# ═══════════════════════════════════════════════════════════════

class TestCtoCB:
    def test_pack(self):
        assert CtoCB(action="approve", id="p1").pack() == "cto:approve:p1"

    def test_unpack(self):
        cb = CtoCB.unpack("cto:reject:p1")
        assert cb.action == "reject"
        assert cb.id == "p1"

    def test_prefix(self):
        assert CtoCB.__prefix__ == "cto"


# ═══════════════════════════════════════════════════════════════
# ApiCB — 2 tests
# ═══════════════════════════════════════════════════════════════

class TestApiCB:
    def test_pack(self):
        assert ApiCB(action="recheck", id="d1").pack() == "api:recheck:d1"

    def test_unpack(self):
        cb = ApiCB.unpack("api:ack:d1")
        assert cb.action == "ack"
        assert cb.id == "d1"


# ═══════════════════════════════════════════════════════════════
# ActionCB — 2 tests
# ═══════════════════════════════════════════════════════════════

class TestActionCB:
    def test_pack(self):
        assert ActionCB(action="launch", id="act_123").pack() == "action:launch:act_123"

    def test_pack_skip(self):
        assert ActionCB(action="skip", id="act_123").pack() == "action:skip:act_123"


# ═══════════════════════════════════════════════════════════════
# EveningCB — 2 tests
# ═══════════════════════════════════════════════════════════════

class TestEveningCB:
    def test_pack_approve(self):
        assert EveningCB(action="approve").pack() == "evening:approve"

    def test_pack_adjust(self):
        assert EveningCB(action="adjust").pack() == "evening:adjust"


# ═══════════════════════════════════════════════════════════════
# GalleryCB — 3 tests
# ═══════════════════════════════════════════════════════════════

class TestGalleryCB:
    def test_pack_ok(self):
        assert GalleryCB(action="ok", id="img1").pack() == "gal:ok:img1"

    def test_pack_page(self):
        assert GalleryCB(action="page", id="2").pack() == "gal:page:2"

    def test_pack_noop(self):
        assert GalleryCB(action="noop").pack() == "gal:noop:"


# ═══════════════════════════════════════════════════════════════
# VoiceBrainCB — 2 tests
# ═══════════════════════════════════════════════════════════════

class TestVoiceBrainCB:
    def test_pack_confirm(self):
        assert VoiceBrainCB(action="confirm").pack() == "vb:confirm"

    def test_pack_cancel(self):
        assert VoiceBrainCB(action="cancel").pack() == "vb:cancel"


# ═══════════════════════════════════════════════════════════════
# SubMenuCB — 3 tests
# ═══════════════════════════════════════════════════════════════

class TestSubMenuCB:
    def test_pack_content_post(self):
        assert SubMenuCB(menu="content", action="post").pack() == "sub:content:post"

    def test_pack_status_revenue(self):
        assert SubMenuCB(menu="status", action="revenue").pack() == "sub:status:revenue"

    def test_unpack(self):
        cb = SubMenuCB.unpack("sub:content:linkedin")
        assert cb.menu == "content"
        assert cb.action == "linkedin"


# ═══════════════════════════════════════════════════════════════
# Callback data length — Telegram limit 64 bytes
# ═══════════════════════════════════════════════════════════════

class TestCallbackDataLength:
    def test_task_cb_max_length(self):
        """Worst case: long task_id + agent name."""
        cb = TaskCB(action="do_assign", id="task_20260214_153000", agent="accountant")
        assert len(cb.pack().encode("utf-8")) <= 64

    def test_cto_cb_max_length(self):
        cb = CtoCB(action="conditions", id="prop_20260208_1530_automator")
        assert len(cb.pack().encode("utf-8")) <= 64

    def test_gallery_cb_max_length(self):
        cb = GalleryCB(action="fwd", id="img_20260214_153000_abc123")
        assert len(cb.pack().encode("utf-8")) <= 64
