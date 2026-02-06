"""
Technical tools for Niraj (CTO agent)
"""

import json
import os
import platform
from datetime import datetime
from typing import Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


def _data_path() -> str:
    """Resolve tech_data.json path (Docker or local)"""
    for p in ["/app/data/tech_data.json", "data/tech_data.json"]:
        if os.path.exists(os.path.dirname(p) or "."):
            return p
    return "data/tech_data.json"


def _load_data() -> dict:
    path = _data_path()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return _default_data()


def _save_data(data: dict):
    path = _data_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data["last_updated"] = datetime.now().isoformat()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _default_data() -> dict:
    return {
        "integrations": {
            "telegram": {
                "name": "Telegram Bot",
                "status": "inactive",
                "endpoint": "",
                "last_check": None,
            },
            "linkedin": {
                "name": "LinkedIn API",
                "status": "inactive",
                "endpoint": "",
                "last_check": None,
            },
            "activepieces": {
                "name": "Activepieces",
                "status": "inactive",
                "endpoint": "",
                "last_check": None,
            },
            "google_sheets": {
                "name": "Google Sheets",
                "status": "inactive",
                "endpoint": "",
                "last_check": None,
            },
        },
        "error_log": [],
        "cron_jobs": [],
        "last_updated": datetime.now().isoformat(),
    }


# ──────────────────────────────────────────────────────────
# Tool 1: System Health Checker
# ──────────────────────────────────────────────────────────

class SystemHealthInput(BaseModel):
    action: str = Field(
        ...,
        description=(
            "Action: 'status' (full system status), "
            "'agents' (check all agents health), "
            "'errors' (show recent errors), "
            "'log_error' (log an error — needs message), "
            "'clear_errors' (clear error log)"
        ),
    )
    message: Optional[str] = Field(None, description="Error message to log")


class SystemHealthChecker(BaseTool):
    name: str = "System Health Checker"
    description: str = (
        "Monitors system health, agent status, and error logs. "
        "Actions: status, agents, errors, log_error, clear_errors."
    )
    args_schema: Type[BaseModel] = SystemHealthInput

    def _run(self, action: str, message: str = None) -> str:
        data = _load_data()

        if action == "status":
            lines = ["SYSTEM HEALTH STATUS:"]
            lines.append(f"  Platform: {platform.system()} {platform.release()}")
            lines.append(f"  Python: {platform.python_version()}")

            # Check environment
            api_key = os.getenv("OPENROUTER_API_KEY", "")
            lines.append(f"  OpenRouter API: {'✅ Connected' if api_key else '❌ Missing'}")
            openai_key = os.getenv("OPENAI_API_KEY", "")
            lines.append(f"  OpenAI (embeddings): {'✅ Connected' if openai_key else '⚠️ Not set'}")
            db_url = os.getenv("DATABASE_URL", "")
            lines.append(f"  PostgreSQL: {'✅ Connected' if db_url else 'ℹ️ In-memory mode'}")

            # Integrations summary
            integrations = data.get("integrations", {})
            active = sum(1 for v in integrations.values() if v["status"] == "active")
            lines.append(f"  Integrations: {active}/{len(integrations)} active")

            # Errors
            errors = data.get("error_log", [])
            lines.append(f"  Recent errors: {len(errors)}")
            lines.append(f"  Last updated: {data.get('last_updated', 'N/A')}")
            return "\n".join(lines)

        if action == "agents":
            lines = ["AGENT STATUS:"]
            agents = {
                "Санторо (CEO)": "openrouter/anthropic/claude-sonnet-4",
                "Амара (CFO)": "openrouter/anthropic/claude-3.5-haiku",
                "Нирадж (CTO)": "openrouter/anthropic/claude-sonnet-4",
            }
            api_key = os.getenv("OPENROUTER_API_KEY", "")
            for name, model in agents.items():
                status = "✅ Ready" if api_key else "❌ No API key"
                lines.append(f"  {name}: {status} ({model})")
            return "\n".join(lines)

        if action == "errors":
            errors = data.get("error_log", [])
            if not errors:
                return "No errors recorded. System is clean! 🙏"
            lines = [f"ERROR LOG ({len(errors)} entries):"]
            for e in errors[-10:]:  # last 10
                lines.append(f"  [{e.get('time', '?')}] {e.get('message', '?')}")
            return "\n".join(lines)

        if action == "log_error":
            if not message:
                return "Error: need message to log"
            errors = data.get("error_log", [])
            errors.append({
                "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "message": message,
            })
            data["error_log"] = errors[-50:]  # keep last 50
            _save_data(data)
            return f"Error logged: {message}"

        if action == "clear_errors":
            data["error_log"] = []
            _save_data(data)
            return "Error log cleared."

        return f"Unknown action: {action}"


# ──────────────────────────────────────────────────────────
# Tool 2: Integration Manager
# ──────────────────────────────────────────────────────────

class IntegrationInput(BaseModel):
    action: str = Field(
        ...,
        description=(
            "Action: 'list' (all integrations), "
            "'check' (check specific integration — needs name), "
            "'activate' (activate — needs name, endpoint), "
            "'deactivate' (deactivate — needs name), "
            "'add_cron' (add cron job — needs name, schedule, endpoint), "
            "'list_cron' (list all cron jobs)"
        ),
    )
    name: Optional[str] = Field(None, description="Integration or cron job name")
    endpoint: Optional[str] = Field(None, description="URL or endpoint")
    schedule: Optional[str] = Field(None, description="Cron schedule (e.g., '0 9 * * *')")


class IntegrationManager(BaseTool):
    name: str = "Integration Manager"
    description: str = (
        "Manages external service integrations and cron jobs. "
        "Actions: list, check, activate, deactivate, add_cron, list_cron."
    )
    args_schema: Type[BaseModel] = IntegrationInput

    def _run(self, action: str, name: str = None, endpoint: str = None,
             schedule: str = None) -> str:
        data = _load_data()
        integrations = data.get("integrations", {})

        if action == "list":
            lines = ["INTEGRATIONS:"]
            for key, info in integrations.items():
                status_icon = "✅" if info["status"] == "active" else "❌"
                lines.append(
                    f"  {status_icon} {info['name']} ({key}): {info['status']}"
                    f"{' — ' + info['endpoint'] if info['endpoint'] else ''}"
                )
            return "\n".join(lines)

        if action == "check":
            if not name:
                return "Error: need integration name"
            key = name.lower().replace(" ", "_")
            if key not in integrations:
                return f"Integration '{name}' not found. Available: {', '.join(integrations.keys())}"
            info = integrations[key]
            info["last_check"] = datetime.now().isoformat()
            _save_data(data)
            return (
                f"Integration: {info['name']}\n"
                f"Status: {info['status']}\n"
                f"Endpoint: {info['endpoint'] or 'Not configured'}\n"
                f"Last check: {info['last_check']}"
            )

        if action == "activate":
            if not name:
                return "Error: need integration name"
            key = name.lower().replace(" ", "_")
            if key not in integrations:
                integrations[key] = {
                    "name": name,
                    "status": "active",
                    "endpoint": endpoint or "",
                    "last_check": datetime.now().isoformat(),
                }
            else:
                integrations[key]["status"] = "active"
                if endpoint:
                    integrations[key]["endpoint"] = endpoint
                integrations[key]["last_check"] = datetime.now().isoformat()
            _save_data(data)
            return f"Integration '{name}' activated{' with endpoint: ' + endpoint if endpoint else ''}."

        if action == "deactivate":
            if not name:
                return "Error: need integration name"
            key = name.lower().replace(" ", "_")
            if key not in integrations:
                return f"Integration '{name}' not found."
            integrations[key]["status"] = "inactive"
            _save_data(data)
            return f"Integration '{name}' deactivated."

        if action == "add_cron":
            if not all([name, schedule]):
                return "Error: need name and schedule"
            cron_jobs = data.get("cron_jobs", [])
            cron_jobs.append({
                "name": name,
                "schedule": schedule,
                "endpoint": endpoint or "",
                "created": datetime.now().isoformat(),
                "active": True,
            })
            data["cron_jobs"] = cron_jobs
            _save_data(data)
            return f"Cron job added: '{name}' with schedule '{schedule}'"

        if action == "list_cron":
            cron_jobs = data.get("cron_jobs", [])
            if not cron_jobs:
                return "No cron jobs configured."
            lines = ["CRON JOBS:"]
            for job in cron_jobs:
                status = "✅" if job.get("active") else "❌"
                lines.append(f"  {status} {job['name']}: {job['schedule']}")
            return "\n".join(lines)

        return f"Unknown action: {action}"
