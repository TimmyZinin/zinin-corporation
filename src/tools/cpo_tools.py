"""
📋 Product tools for Софи (CPO agent)

Feature health checks, backlog management, sprint tracking, progress reports.
All data is read from/written to local JSON files in data/product/.
"""

import json
import logging
import os
from datetime import datetime
from typing import Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# Data helpers
# ──────────────────────────────────────────────────────────

def _product_dir() -> str:
    for base in ["/app/data/product", "data/product"]:
        parent = os.path.dirname(base)
        if os.path.isdir(parent):
            os.makedirs(base, exist_ok=True)
            return base
    os.makedirs("data/product", exist_ok=True)
    return "data/product"


def _load_json(filename: str) -> dict:
    path = os.path.join(_product_dir(), filename)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_json(filename: str, data: dict):
    path = os.path.join(_product_dir(), filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


# ──────────────────────────────────────────────────────────
# Tool 1: Feature Health Checker
# ──────────────────────────────────────────────────────────

class FeatureHealthInput(BaseModel):
    action: str = Field(
        ...,
        description=(
            "Action: 'status' (overall product health summary), "
            "'features' (list all features with status), "
            "'add_feature' (add new feature — needs name, description, priority), "
            "'update_feature' (update feature — needs name, new_status), "
            "'blockers' (list all blocked features)"
        ),
    )
    name: Optional[str] = Field(None, description="Feature name")
    description: Optional[str] = Field(None, description="Feature description")
    priority: Optional[str] = Field(None, description="Priority: critical, high, medium, low")
    new_status: Optional[str] = Field(None, description="New status: todo, in_progress, done, blocked")


class FeatureHealthChecker(BaseTool):
    name: str = "Feature Health Checker"
    description: str = (
        "Checks product health: feature statuses, blockers, overall progress. "
        "Actions: status, features, add_feature, update_feature, blockers."
    )
    args_schema: Type[BaseModel] = FeatureHealthInput

    def _run(self, action: str, name: str = None, description: str = None,
             priority: str = None, new_status: str = None) -> str:
        data = _load_json("features.json")
        features = data.get("features", {})

        if action == "status":
            if not features:
                return "No features tracked yet. Use action='add_feature' to start."

            total = len(features)
            done = sum(1 for f in features.values() if f.get("status") == "done")
            in_prog = sum(1 for f in features.values() if f.get("status") == "in_progress")
            blocked = sum(1 for f in features.values() if f.get("status") == "blocked")
            todo = sum(1 for f in features.values() if f.get("status") == "todo")

            # Health score
            if total == 0:
                health = "N/A"
            elif blocked > total * 0.3:
                health = "❌ CRITICAL — >30% features blocked"
            elif blocked > 0 or (in_prog == 0 and todo > 0):
                health = "⚠️ DEGRADED — blockers or stalled progress"
            else:
                health = "✅ HEALTHY"

            lines = [
                "═══ PRODUCT HEALTH ═══",
                f"Overall: {health}",
                f"Features: {total} total",
                f"  ✅ Done: {done}",
                f"  🔄 In Progress: {in_prog}",
                f"  📋 Todo: {todo}",
                f"  🚫 Blocked: {blocked}",
                f"Completion: {round(done / total * 100)}%" if total > 0 else "",
            ]

            # Priority breakdown
            by_priority = {}
            for f in features.values():
                p = f.get("priority", "medium")
                by_priority.setdefault(p, {"total": 0, "done": 0})
                by_priority[p]["total"] += 1
                if f.get("status") == "done":
                    by_priority[p]["done"] += 1

            if by_priority:
                lines.append("")
                lines.append("▸ By Priority:")
                for p in ["critical", "high", "medium", "low"]:
                    if p in by_priority:
                        info = by_priority[p]
                        lines.append(f"  {p.upper()}: {info['done']}/{info['total']} done")

            return "\n".join(lines)

        if action == "features":
            if not features:
                return "No features tracked. Use action='add_feature' to add."
            lines = ["═══ ALL FEATURES ═══"]
            status_icons = {"done": "✅", "in_progress": "🔄", "todo": "📋", "blocked": "🚫"}
            for key, f in sorted(features.items(), key=lambda x: (
                {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(x[1].get("priority", "medium"), 2),
                x[0],
            )):
                icon = status_icons.get(f.get("status", "todo"), "📋")
                lines.append(f"  {icon} [{f.get('priority', 'medium').upper()}] {f.get('name', key)}")
                lines.append(f"     Status: {f.get('status', 'todo')} | Added: {f.get('added', '?')}")
                if f.get("description"):
                    lines.append(f"     {f['description'][:100]}")
            return "\n".join(lines)

        if action == "add_feature":
            if not name:
                return "Error: need name for feature."
            key = name.lower().replace(" ", "_").replace("-", "_")[:50]
            features[key] = {
                "name": name,
                "description": description or "",
                "priority": priority or "medium",
                "status": "todo",
                "added": datetime.now().strftime("%Y-%m-%d"),
                "updated": datetime.now().strftime("%Y-%m-%d"),
            }
            data["features"] = features
            _save_json("features.json", data)
            return f"Feature added: {name} (priority: {priority or 'medium'}, status: todo)"

        if action == "update_feature":
            if not name:
                return "Error: need feature name."
            key = name.lower().replace(" ", "_").replace("-", "_")[:50]
            if key not in features:
                # Try fuzzy match
                matches = [k for k in features if name.lower() in k]
                if len(matches) == 1:
                    key = matches[0]
                else:
                    return f"Feature '{name}' not found. Available: {', '.join(features.keys())}"
            if new_status:
                features[key]["status"] = new_status
            if priority:
                features[key]["priority"] = priority
            if description:
                features[key]["description"] = description
            features[key]["updated"] = datetime.now().strftime("%Y-%m-%d")
            data["features"] = features
            _save_json("features.json", data)
            return f"Feature updated: {features[key]['name']} → status={features[key]['status']}"

        if action == "blockers":
            blocked = {k: f for k, f in features.items() if f.get("status") == "blocked"}
            if not blocked:
                return "No blocked features. All clear."
            lines = [f"═══ BLOCKED FEATURES ({len(blocked)}) ═══"]
            for key, f in blocked.items():
                lines.append(f"  🚫 [{f.get('priority', '?').upper()}] {f.get('name', key)}")
                lines.append(f"     {f.get('description', '')[:100]}")
            return "\n".join(lines)

        return f"Unknown action: {action}"


# ──────────────────────────────────────────────────────────
# Tool 2: Sprint Tracker
# ──────────────────────────────────────────────────────────

class SprintInput(BaseModel):
    action: str = Field(
        ...,
        description=(
            "Action: 'current' (show current sprint status), "
            "'history' (show past sprints), "
            "'create' (create new sprint — needs name, tasks as JSON list), "
            "'complete_task' (mark task done — needs task_name), "
            "'close' (close current sprint)"
        ),
    )
    name: Optional[str] = Field(None, description="Sprint name or task name")
    tasks: Optional[str] = Field(
        None,
        description='JSON list of task names, e.g. \'["Task 1", "Task 2"]\'',
    )


class SprintTracker(BaseTool):
    name: str = "Sprint Tracker"
    description: str = (
        "Tracks sprint progress: tasks, completion, velocity. "
        "Actions: current, history, create, complete_task, close."
    )
    args_schema: Type[BaseModel] = SprintInput

    def _run(self, action: str, name: str = None, tasks: str = None) -> str:
        data = _load_json("sprints.json")
        sprints = data.get("sprints", [])
        current = data.get("current_sprint")

        if action == "current":
            if not current:
                return "No active sprint. Use action='create' to start one."
            total = len(current.get("tasks", {}))
            done = sum(1 for t in current.get("tasks", {}).values() if t.get("done"))
            lines = [
                f"═══ SPRINT: {current.get('name', '?')} ═══",
                f"Started: {current.get('started', '?')}",
                f"Progress: {done}/{total} tasks ({round(done / total * 100) if total else 0}%)",
                "",
            ]
            for task_key, task_info in current.get("tasks", {}).items():
                icon = "✅" if task_info.get("done") else "⬜"
                lines.append(f"  {icon} {task_info.get('name', task_key)}")
                if task_info.get("completed_at"):
                    lines.append(f"     Completed: {task_info['completed_at']}")
            return "\n".join(lines)

        if action == "history":
            if not sprints:
                return "No completed sprints yet."
            lines = ["═══ SPRINT HISTORY ═══"]
            for s in sprints[-10:]:
                total = len(s.get("tasks", {}))
                done = sum(1 for t in s.get("tasks", {}).values() if t.get("done"))
                lines.append(
                    f"  {s.get('name', '?')}: {done}/{total} "
                    f"({s.get('started', '?')} → {s.get('closed', '?')})"
                )
            return "\n".join(lines)

        if action == "create":
            if not name:
                return "Error: need sprint name."
            task_list = []
            if tasks:
                try:
                    task_list = json.loads(tasks)
                except json.JSONDecodeError:
                    task_list = [t.strip() for t in tasks.split(",") if t.strip()]

            # Close current sprint if exists
            if current:
                sprints.append(current)

            new_sprint = {
                "name": name,
                "started": datetime.now().strftime("%Y-%m-%d"),
                "tasks": {},
            }
            for t in task_list:
                key = t.lower().replace(" ", "_")[:50]
                new_sprint["tasks"][key] = {"name": t, "done": False}

            data["current_sprint"] = new_sprint
            data["sprints"] = sprints
            _save_json("sprints.json", data)
            return f"Sprint '{name}' created with {len(task_list)} tasks."

        if action == "complete_task":
            if not current:
                return "No active sprint."
            if not name:
                return "Error: need task_name."
            task_key = name.lower().replace(" ", "_")[:50]
            task_tasks = current.get("tasks", {})
            if task_key not in task_tasks:
                # Fuzzy match
                matches = [k for k in task_tasks if name.lower() in k]
                if len(matches) == 1:
                    task_key = matches[0]
                else:
                    return f"Task '{name}' not found. Available: {', '.join(task_tasks.keys())}"
            task_tasks[task_key]["done"] = True
            task_tasks[task_key]["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            data["current_sprint"] = current
            _save_json("sprints.json", data)
            return f"Task '{task_tasks[task_key]['name']}' marked as done."

        if action == "close":
            if not current:
                return "No active sprint to close."
            current["closed"] = datetime.now().strftime("%Y-%m-%d")
            sprints.append(current)
            data["current_sprint"] = None
            data["sprints"] = sprints[-50:]  # Keep last 50
            _save_json("sprints.json", data)
            total = len(current.get("tasks", {}))
            done = sum(1 for t in current.get("tasks", {}).values() if t.get("done"))
            return f"Sprint '{current['name']}' closed. Result: {done}/{total} tasks completed."

        return f"Unknown action: {action}"


# ──────────────────────────────────────────────────────────
# Tool 3: Backlog Analyzer
# ──────────────────────────────────────────────────────────

class BacklogInput(BaseModel):
    action: str = Field(
        ...,
        description=(
            "Action: 'summary' (backlog overview with priorities), "
            "'stale' (features not updated in 7+ days), "
            "'suggest_sprint' (suggest next sprint tasks based on priority), "
            "'metrics' (backlog metrics: age, throughput, cycle time)"
        ),
    )
    sprint_size: Optional[int] = Field(
        None, description="Number of tasks for suggested sprint (default: 5)",
    )


class BacklogAnalyzer(BaseTool):
    name: str = "Backlog Analyzer"
    description: str = (
        "Analyzes product backlog: priorities, stale items, sprint suggestions, metrics. "
        "Actions: summary, stale, suggest_sprint, metrics."
    )
    args_schema: Type[BaseModel] = BacklogInput

    def _run(self, action: str, sprint_size: int = None) -> str:
        data = _load_json("features.json")
        features = data.get("features", {})
        sprint_data = _load_json("sprints.json")

        if action == "summary":
            if not features:
                return "Backlog is empty. No features tracked."
            lines = ["═══ BACKLOG SUMMARY ═══"]
            by_priority = {"critical": [], "high": [], "medium": [], "low": []}
            for key, f in features.items():
                p = f.get("priority", "medium")
                if f.get("status") != "done":
                    by_priority.setdefault(p, []).append(f)
            for p in ["critical", "high", "medium", "low"]:
                items = by_priority.get(p, [])
                if items:
                    lines.append(f"\n▸ {p.upper()} ({len(items)}):")
                    for f in items:
                        status_icon = {"todo": "📋", "in_progress": "🔄", "blocked": "🚫"}.get(
                            f.get("status", "todo"), "📋"
                        )
                        lines.append(f"  {status_icon} {f.get('name', '?')}")

            total_open = sum(
                1 for f in features.values() if f.get("status") != "done"
            )
            total_done = sum(
                1 for f in features.values() if f.get("status") == "done"
            )
            lines.append(f"\nTotal: {total_open} open, {total_done} done")
            return "\n".join(lines)

        if action == "stale":
            now = datetime.now()
            stale = []
            for key, f in features.items():
                if f.get("status") == "done":
                    continue
                updated = f.get("updated", f.get("added", ""))
                if updated:
                    try:
                        upd_date = datetime.strptime(updated, "%Y-%m-%d")
                        days = (now - upd_date).days
                        if days >= 7:
                            stale.append((key, f, days))
                    except ValueError:
                        pass
            if not stale:
                return "No stale features. All items are fresh."
            stale.sort(key=lambda x: -x[2])
            lines = [f"═══ STALE FEATURES ({len(stale)}) ═══"]
            for key, f, days in stale:
                lines.append(f"  ⏰ {f.get('name', key)} — {days} days since update")
                lines.append(f"     Priority: {f.get('priority', '?')}, Status: {f.get('status', '?')}")
            return "\n".join(lines)

        if action == "suggest_sprint":
            size = sprint_size or 5
            candidates = [
                (key, f) for key, f in features.items()
                if f.get("status") in ("todo", "blocked")
            ]
            # Sort: critical first, then high, etc. Within same priority: older first.
            priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            candidates.sort(key=lambda x: (
                priority_order.get(x[1].get("priority", "medium"), 2),
                x[1].get("added", "9999"),
            ))
            selected = candidates[:size]
            if not selected:
                return "No open tasks to suggest for sprint."
            lines = [f"═══ SUGGESTED SPRINT ({len(selected)} tasks) ═══"]
            for key, f in selected:
                lines.append(f"  📌 [{f.get('priority', '?').upper()}] {f.get('name', key)}")
                if f.get("description"):
                    lines.append(f"     {f['description'][:80]}")
            return "\n".join(lines)

        if action == "metrics":
            if not features:
                return "No data for metrics."
            now = datetime.now()
            # Throughput: done features
            done_features = [f for f in features.values() if f.get("status") == "done"]
            open_features = [f for f in features.values() if f.get("status") != "done"]

            # Average age of open features
            ages = []
            for f in open_features:
                added = f.get("added", "")
                if added:
                    try:
                        ages.append((now - datetime.strptime(added, "%Y-%m-%d")).days)
                    except ValueError:
                        pass
            avg_age = round(sum(ages) / len(ages)) if ages else 0

            # Sprint velocity
            sprints = sprint_data.get("sprints", [])
            velocities = []
            for s in sprints[-5:]:
                total = len(s.get("tasks", {}))
                done = sum(1 for t in s.get("tasks", {}).values() if t.get("done"))
                if total > 0:
                    velocities.append(done)
            avg_velocity = round(sum(velocities) / len(velocities), 1) if velocities else 0

            lines = [
                "═══ PRODUCT METRICS ═══",
                f"Total features: {len(features)}",
                f"  Done: {len(done_features)}",
                f"  Open: {len(open_features)}",
                f"  Completion rate: {round(len(done_features) / len(features) * 100)}%",
                "",
                f"Avg age of open items: {avg_age} days",
                f"Sprint velocity (last 5): {avg_velocity} tasks/sprint",
                f"Sprints completed: {len(sprints)}",
            ]
            return "\n".join(lines)

        return f"Unknown action: {action}"


# ──────────────────────────────────────────────────────────
# Tool 4: Progress Reporter
# ──────────────────────────────────────────────────────────

class ProgressInput(BaseModel):
    action: str = Field(
        ...,
        description=(
            "Action: 'weekly' (weekly progress report), "
            "'daily' (daily status), "
            "'log' (log a progress note — needs note), "
            "'notes' (show recent progress notes)"
        ),
    )
    note: Optional[str] = Field(None, description="Progress note to log")


class ProgressReporter(BaseTool):
    name: str = "Progress Reporter"
    description: str = (
        "Generates progress reports and logs notes about product development. "
        "Actions: weekly, daily, log, notes."
    )
    args_schema: Type[BaseModel] = ProgressInput

    def _run(self, action: str, note: str = None) -> str:
        features_data = _load_json("features.json")
        sprint_data = _load_json("sprints.json")
        notes_data = _load_json("progress_notes.json")

        features = features_data.get("features", {})
        current_sprint = sprint_data.get("current_sprint")
        sprints = sprint_data.get("sprints", [])
        notes = notes_data.get("notes", [])

        if action == "log":
            if not note:
                return "Error: need note text."
            notes.append({
                "text": note[:500],
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            })
            notes_data["notes"] = notes[-200:]
            _save_json("progress_notes.json", notes_data)
            return f"Note logged: {note[:100]}..."

        if action == "notes":
            if not notes:
                return "No progress notes yet."
            lines = ["═══ RECENT NOTES ═══"]
            for n in notes[-15:]:
                lines.append(f"  [{n.get('timestamp', '?')}] {n.get('text', '?')[:120]}")
            return "\n".join(lines)

        if action in ("daily", "weekly"):
            lines = [f"═══ {'WEEKLY' if action == 'weekly' else 'DAILY'} PROGRESS REPORT ═══"]
            lines.append(f"Date: {datetime.now().strftime('%Y-%m-%d')}")
            lines.append("")

            # Feature summary
            total = len(features)
            done = sum(1 for f in features.values() if f.get("status") == "done")
            in_prog = sum(1 for f in features.values() if f.get("status") == "in_progress")
            blocked = sum(1 for f in features.values() if f.get("status") == "blocked")
            lines.append(f"▸ Features: {done}/{total} done, {in_prog} in progress, {blocked} blocked")

            # Sprint status
            if current_sprint:
                s_total = len(current_sprint.get("tasks", {}))
                s_done = sum(1 for t in current_sprint.get("tasks", {}).values() if t.get("done"))
                lines.append(f"▸ Sprint '{current_sprint.get('name', '?')}': {s_done}/{s_total}")
            else:
                lines.append("▸ Sprint: No active sprint")

            # Velocity
            if sprints:
                last = sprints[-1]
                last_total = len(last.get("tasks", {}))
                last_done = sum(1 for t in last.get("tasks", {}).values() if t.get("done"))
                lines.append(f"▸ Last sprint: {last.get('name', '?')} — {last_done}/{last_total}")

            # Recent notes
            recent_notes = notes[-5:] if action == "weekly" else notes[-3:]
            if recent_notes:
                lines.append("")
                lines.append("▸ Recent notes:")
                for n in recent_notes:
                    lines.append(f"  • {n.get('text', '?')[:100]}")

            # Blockers
            blocked_features = [f for f in features.values() if f.get("status") == "blocked"]
            if blocked_features:
                lines.append("")
                lines.append(f"▸ Blockers ({len(blocked_features)}):")
                for f in blocked_features:
                    lines.append(f"  🚫 {f.get('name', '?')}: {f.get('description', '')[:80]}")

            return "\n".join(lines)

        return f"Unknown action: {action}"
