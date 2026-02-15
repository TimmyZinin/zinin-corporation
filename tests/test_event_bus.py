"""Tests for EventBus — lightweight in-process pub/sub."""

import threading
import time

import pytest

from src.event_bus import (
    AGENT_EXECUTION_COMPLETED,
    AGENT_EXECUTION_STARTED,
    QUALITY_SCORED,
    TASK_APPROVAL_REQUIRED,
    TASK_APPROVED,
    TASK_ASSIGNED,
    TASK_COMPLETED,
    TASK_CREATED,
    TASK_REJECTED,
    TASK_RETRY,
    TASK_STARTED,
    TASK_UNBLOCKED,
    Event,
    EventBus,
    get_event_bus,
    reset_event_bus,
)


@pytest.fixture(autouse=True)
def _clean_bus():
    """Reset global EventBus before and after each test."""
    reset_event_bus()
    yield
    reset_event_bus()


# ── Event record ──


class TestEvent:
    def test_event_has_type_and_payload(self):
        e = Event("task.created", {"task_id": "abc"})
        assert e.type == "task.created"
        assert e.payload == {"task_id": "abc"}

    def test_event_has_timestamp(self):
        before = time.time()
        e = Event("x", {})
        after = time.time()
        assert before <= e.timestamp <= after

    def test_event_repr(self):
        e = Event("task.created", {"task_id": "abc", "title": "Test"})
        r = repr(e)
        assert "task.created" in r
        assert "task_id" in r


# ── EventBus core ──


class TestEventBus:
    def test_emit_no_subscribers(self):
        bus = EventBus()
        bus.emit("task.created", {"id": "1"})  # should not raise

    def test_subscribe_and_emit(self):
        bus = EventBus()
        received = []
        bus.on("task.created", lambda e: received.append(e))
        bus.emit("task.created", {"id": "1"})
        assert len(received) == 1
        assert received[0].type == "task.created"
        assert received[0].payload == {"id": "1"}

    def test_multiple_subscribers(self):
        bus = EventBus()
        results = []
        bus.on("x", lambda e: results.append("a"))
        bus.on("x", lambda e: results.append("b"))
        bus.emit("x")
        assert results == ["a", "b"]

    def test_subscriber_error_caught(self):
        bus = EventBus()
        received = []

        def bad_cb(e):
            raise ValueError("boom")

        bus.on("x", bad_cb)
        bus.on("x", lambda e: received.append(e))
        bus.emit("x")  # should not raise
        assert len(received) == 1

    def test_emit_different_types(self):
        bus = EventBus()
        a_events = []
        b_events = []
        bus.on("a", lambda e: a_events.append(e))
        bus.on("b", lambda e: b_events.append(e))
        bus.emit("a")
        bus.emit("b")
        bus.emit("a")
        assert len(a_events) == 2
        assert len(b_events) == 1

    def test_unsubscribe(self):
        bus = EventBus()
        received = []
        cb = lambda e: received.append(e)
        bus.on("x", cb)
        bus.emit("x")
        assert len(received) == 1
        bus.off("x", cb)
        bus.emit("x")
        assert len(received) == 1  # no new events

    def test_unsubscribe_nonexistent(self):
        bus = EventBus()
        bus.off("x", lambda e: None)  # should not raise

    def test_emit_none_payload(self):
        bus = EventBus()
        received = []
        bus.on("x", lambda e: received.append(e))
        bus.emit("x")
        assert received[0].payload == {}

    def test_emit_explicit_none_payload(self):
        bus = EventBus()
        received = []
        bus.on("x", lambda e: received.append(e))
        bus.emit("x", None)
        assert received[0].payload == {}


# ── History ──


class TestEventBusHistory:
    def test_history_recorded(self):
        bus = EventBus()
        bus.emit("a", {"k": "v"})
        bus.emit("b")
        history = bus.get_history()
        assert len(history) == 2
        assert history[0].type == "a"
        assert history[1].type == "b"

    def test_history_filtered_by_type(self):
        bus = EventBus()
        bus.emit("a")
        bus.emit("b")
        bus.emit("a")
        filtered = bus.get_history(event_type="a")
        assert len(filtered) == 2
        assert all(e.type == "a" for e in filtered)

    def test_history_limit(self):
        bus = EventBus()
        for i in range(10):
            bus.emit("x", {"i": i})
        limited = bus.get_history(limit=3)
        assert len(limited) == 3
        assert limited[0].payload["i"] == 7

    def test_history_bounded_by_maxlen(self):
        bus = EventBus(history_size=5)
        for i in range(10):
            bus.emit("x", {"i": i})
        history = bus.get_history()
        assert len(history) == 5
        assert history[0].payload["i"] == 5


# ── Subscriber count ──


class TestSubscriberCount:
    def test_count_total(self):
        bus = EventBus()
        bus.on("a", lambda e: None)
        bus.on("b", lambda e: None)
        bus.on("b", lambda e: None)
        assert bus.subscriber_count() == 3

    def test_count_by_type(self):
        bus = EventBus()
        bus.on("a", lambda e: None)
        bus.on("b", lambda e: None)
        bus.on("b", lambda e: None)
        assert bus.subscriber_count("a") == 1
        assert bus.subscriber_count("b") == 2
        assert bus.subscriber_count("c") == 0


# ── Clear ──


class TestClear:
    def test_clear_removes_all(self):
        bus = EventBus()
        bus.on("x", lambda e: None)
        bus.emit("x")
        bus.clear()
        assert bus.subscriber_count() == 0
        assert bus.get_history() == []


# ── Thread safety ──


class TestThreadSafety:
    def test_concurrent_emit(self):
        bus = EventBus()
        counter = {"n": 0}
        lock = threading.Lock()

        def cb(e):
            with lock:
                counter["n"] += 1

        bus.on("x", cb)
        threads = [threading.Thread(target=bus.emit, args=("x",)) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert counter["n"] == 100

    def test_concurrent_subscribe(self):
        bus = EventBus()
        cbs = [lambda e, i=i: None for i in range(50)]
        threads = [threading.Thread(target=bus.on, args=("x", cb)) for cb in cbs]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert bus.subscriber_count("x") == 50


# ── Singleton ──


class TestSingleton:
    def test_get_event_bus_returns_same_instance(self):
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        assert bus1 is bus2

    def test_reset_event_bus_clears(self):
        bus1 = get_event_bus()
        bus1.on("x", lambda e: None)
        reset_event_bus()
        bus2 = get_event_bus()
        assert bus2 is not bus1
        assert bus2.subscriber_count() == 0


# ── Event type constants ──


class TestEventConstants:
    def test_all_constants_are_strings(self):
        for const in (
            TASK_CREATED, TASK_ASSIGNED, TASK_STARTED,
            TASK_COMPLETED, TASK_UNBLOCKED,
            AGENT_EXECUTION_STARTED, AGENT_EXECUTION_COMPLETED,
            QUALITY_SCORED,
            TASK_APPROVAL_REQUIRED, TASK_APPROVED, TASK_REJECTED,
            TASK_RETRY,
        ):
            assert isinstance(const, str)
            assert "." in const  # dotted notation
