"""
Zinin Corp — Real-Time Agent Monitoring Dashboard

Starlette ASGI app with SSE for live updates.
Reads from existing activity_tracker, rate_monitor, task_pool.
Zero new dependencies (starlette/sse-starlette/uvicorn via mcp).
"""

import asyncio
import hashlib
import json
import logging
from datetime import datetime

from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route
from sse_starlette.sse import EventSourceResponse

from ..activity_tracker import (
    get_all_statuses,
    get_recent_events,
    get_task_progress,
    get_quality_summary,
    AGENT_NAMES,
    AGENT_EMOJI,
)
from ..rate_monitor import get_all_usage, get_rate_alerts
from ..task_pool import get_pool_summary, get_all_tasks, TaskStatus
from .dashboard_html import render_dashboard_html
from .webhook_tribute import tribute_webhook

logger = logging.getLogger(__name__)

SSE_POLL_INTERVAL = 3  # seconds


# ── Endpoints ──────────────────────────────────────────────

async def index(request):
    """Serve the dashboard HTML page."""
    return HTMLResponse(render_dashboard_html())


async def api_snapshot(request):
    """Full state snapshot (used on initial page load)."""
    return JSONResponse(_build_snapshot())


async def api_agents(request):
    """Current agent statuses only."""
    statuses = get_all_statuses()
    for key in statuses:
        statuses[key]["progress"] = get_task_progress(key)
    return JSONResponse(statuses)


async def api_events(request):
    """Recent activity events."""
    hours = int(request.query_params.get("hours", "24"))
    limit = int(request.query_params.get("limit", "50"))
    events = get_recent_events(hours=hours, limit=limit)
    return JSONResponse(events)


async def event_stream(request):
    """SSE stream — pushes snapshot every 3s when data changes."""
    async def generate():
        last_hash = ""
        while True:
            await asyncio.sleep(SSE_POLL_INTERVAL)
            try:
                snapshot = _build_snapshot()
                current_hash = _hash_snapshot(snapshot)
                if current_hash != last_hash:
                    last_hash = current_hash
                    yield {
                        "event": "update",
                        "data": json.dumps(
                            snapshot, default=str, ensure_ascii=False
                        ),
                    }
            except Exception as e:
                logger.warning(f"SSE snapshot error: {e}")

    return EventSourceResponse(generate())


# ── Snapshot builder ───────────────────────────────────────

def _build_snapshot() -> dict:
    """Aggregate all data sources into one JSON-serializable dict."""
    statuses = get_all_statuses()
    for key in statuses:
        statuses[key]["progress"] = get_task_progress(key)
        statuses[key]["name"] = AGENT_NAMES.get(key, key)
        statuses[key]["emoji"] = AGENT_EMOJI.get(key, "")

    events = get_recent_events(hours=24, limit=50)
    quality = get_quality_summary()

    try:
        api_usage = get_all_usage(minutes=60)
    except Exception:
        api_usage = {}

    try:
        alerts = [a.model_dump() for a in get_rate_alerts(hours=24)]
    except Exception:
        alerts = []

    try:
        pool_summary = get_pool_summary()
        all_tasks = get_all_tasks()
        active_tasks = [
            {
                "id": t.id,
                "title": t.title,
                "status": t.status.value if hasattr(t.status, "value") else str(t.status),
                "assignee": t.assignee or "",
                "priority": t.priority,
            }
            for t in all_tasks
            if t.status != TaskStatus.DONE
        ][:20]
    except Exception:
        pool_summary = {}
        active_tasks = []

    return {
        "timestamp": datetime.now().isoformat(),
        "agents": statuses,
        "events": events,
        "quality": quality,
        "api_usage": api_usage,
        "alerts": alerts,
        "task_pool": pool_summary,
        "active_tasks": active_tasks,
    }


def _hash_snapshot(snapshot: dict) -> str:
    """Quick MD5 hash to detect data changes."""
    raw = json.dumps(snapshot, sort_keys=True, default=str)
    return hashlib.md5(raw.encode()).hexdigest()


# ── App factory ────────────────────────────────────────────

def create_app() -> Starlette:
    routes = [
        Route("/", index),
        Route("/api/snapshot", api_snapshot),
        Route("/api/agents", api_agents),
        Route("/api/events", api_events),
        Route("/api/stream", event_stream),
        Route("/webhooks/tribute", tribute_webhook, methods=["POST"]),
    ]
    return Starlette(routes=routes)


app = create_app()
