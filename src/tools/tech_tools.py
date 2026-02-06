"""
Technical tools for Niraj (CTO agent)

Real system checks: HTTP pings, API verification, service health.
"""

import json
import os
import platform
import time
from datetime import datetime
from typing import Optional, Type
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


def _data_path() -> str:
    for p in ["/app/data/tech_data.json", "data/tech_data.json"]:
        if os.path.isdir(os.path.dirname(p)):
            return p
    return "data/tech_data.json"


def _load_data() -> dict:
    path = _data_path()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"error_log": [], "cron_jobs": [], "last_updated": None}


def _save_data(data: dict):
    path = _data_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data["last_updated"] = datetime.now().isoformat()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _http_ping(url: str, timeout: int = 10) -> dict:
    """Ping a URL and return status, time, code."""
    try:
        start = time.time()
        req = Request(url, headers={"User-Agent": "AICorp-HealthCheck/1.0"})
        with urlopen(req, timeout=timeout) as resp:
            elapsed = round((time.time() - start) * 1000)
            return {"ok": True, "code": resp.status, "ms": elapsed}
    except HTTPError as e:
        return {"ok": False, "code": e.code, "ms": 0, "error": str(e.reason)}
    except URLError as e:
        return {"ok": False, "code": 0, "ms": 0, "error": str(e.reason)}
    except Exception as e:
        return {"ok": False, "code": 0, "ms": 0, "error": str(e)}


def _check_openrouter() -> dict:
    """Test OpenRouter API with a minimal call."""
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        return {"ok": False, "error": "OPENROUTER_API_KEY not set"}
    try:
        start = time.time()
        payload = json.dumps({
            "model": "openrouter/auto",
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
        }).encode("utf-8")
        req = Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(req, timeout=15) as resp:
            elapsed = round((time.time() - start) * 1000)
            return {"ok": True, "ms": elapsed, "code": resp.status}
    except HTTPError as e:
        return {"ok": False, "code": e.code, "error": f"HTTP {e.code}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _check_linkedin() -> dict:
    """Check LinkedIn token validity."""
    token = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
    if not token:
        return {"ok": False, "error": "LINKEDIN_ACCESS_TOKEN not set"}
    try:
        req = Request(
            "https://api.linkedin.com/v2/userinfo",
            headers={"Authorization": f"Bearer {token}", "LinkedIn-Version": "202502"},
        )
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {"ok": True, "user": data.get("name", "?")}
    except HTTPError as e:
        if e.code == 401:
            return {"ok": False, "error": "Token EXPIRED"}
        return {"ok": False, "error": f"HTTP {e.code}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _check_yuki_memory() -> dict:
    """Check Yuki's memory data stats."""
    for base in ["/app/data/yuki_memory", "data/yuki_memory"]:
        if os.path.isdir(base):
            stats = {"base": base}
            # Count episodic files
            gen_dir = os.path.join(base, "episodic", "generations")
            fb_dir = os.path.join(base, "episodic", "feedback")
            draft_dir = os.path.join(base, "episodic", "drafts")
            gen_count = fb_count = draft_count = 0
            if os.path.isdir(gen_dir):
                for f in os.listdir(gen_dir):
                    if f.endswith(".jsonl"):
                        with open(os.path.join(gen_dir, f)) as fh:
                            gen_count += sum(1 for _ in fh)
            if os.path.isdir(fb_dir):
                for f in os.listdir(fb_dir):
                    if f.endswith(".jsonl"):
                        with open(os.path.join(fb_dir, f)) as fh:
                            fb_count += sum(1 for _ in fh)
            if os.path.isdir(draft_dir):
                draft_count = len([f for f in os.listdir(draft_dir) if f.endswith(".json")])
            stats["generations"] = gen_count
            stats["feedback"] = fb_count
            stats["drafts"] = draft_count
            # Check rules/brand voice
            stats["rules"] = os.path.exists(os.path.join(base, "procedural", "rules.json"))
            stats["brand_voice"] = os.path.exists(os.path.join(base, "semantic", "brand_voice.json"))
            return stats
    return {"error": "Yuki memory directory not found"}


# ──────────────────────────────────────────────────────────
# Tool 1: System Health Checker (REAL checks)
# ──────────────────────────────────────────────────────────

class SystemHealthInput(BaseModel):
    action: str = Field(
        ...,
        description=(
            "Action: 'status' (full real health check — pings services, checks APIs), "
            "'agents' (check all agents and their tools), "
            "'errors' (show recent errors), "
            "'log_error' (log an error — needs message), "
            "'clear_errors' (clear error log)"
        ),
    )
    message: Optional[str] = Field(None, description="Error message to log")


class SystemHealthChecker(BaseTool):
    name: str = "System Health Checker"
    description: str = (
        "Performs REAL system health checks: pings services, tests API connectivity, "
        "verifies tokens, checks data integrity. "
        "Actions: status, agents, errors, log_error, clear_errors."
    )
    args_schema: Type[BaseModel] = SystemHealthInput

    def _run(self, action: str, message: str = None) -> str:
        data = _load_data()

        if action == "status":
            lines = ["═══ SYSTEM HEALTH CHECK ═══", f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"]
            lines.append(f"Platform: {platform.system()} {platform.release()}, Python {platform.python_version()}")
            lines.append("")

            # 1. Railway app
            lines.append("▸ Railway App:")
            app_check = _http_ping("https://crewai-studio-production-b962.up.railway.app/")
            if app_check["ok"]:
                lines.append(f"  ✅ Online (HTTP {app_check['code']}, {app_check['ms']}ms)")
            else:
                lines.append(f"  ❌ DOWN: {app_check.get('error', '?')}")

            # 2. OpenRouter API
            lines.append("▸ OpenRouter API:")
            api_key = os.getenv("OPENROUTER_API_KEY", "")
            if api_key:
                or_check = _check_openrouter()
                if or_check["ok"]:
                    lines.append(f"  ✅ Working ({or_check['ms']}ms)")
                else:
                    lines.append(f"  ❌ Error: {or_check.get('error', '?')}")
            else:
                lines.append("  ❌ OPENROUTER_API_KEY not set")

            # 3. LinkedIn
            lines.append("▸ LinkedIn API:")
            li_check = _check_linkedin()
            if li_check["ok"]:
                lines.append(f"  ✅ Token valid (user: {li_check['user']})")
            else:
                lines.append(f"  ❌ {li_check.get('error', '?')}")

            # 4. Environment vars
            lines.append("▸ Environment:")
            env_checks = [
                ("OPENROUTER_API_KEY", True),
                ("OPENAI_API_KEY", False),
                ("DATABASE_URL", False),
                ("LINKEDIN_ACCESS_TOKEN", False),
                ("LINKEDIN_PERSON_ID", False),
                ("GROQ_API_KEY", False),
            ]
            for var, required in env_checks:
                val = os.getenv(var, "")
                icon = "✅" if val else ("❌" if required else "⚠️")
                status = "Set" if val else ("MISSING (required)" if required else "Not set")
                lines.append(f"  {icon} {var}: {status}")

            # 5. Yuki memory
            lines.append("▸ Yuki Memory:")
            ym = _check_yuki_memory()
            if "error" in ym:
                lines.append(f"  ❌ {ym['error']}")
            else:
                lines.append(f"  Generations: {ym['generations']}, Feedback: {ym['feedback']}, Drafts: {ym['drafts']}")
                lines.append(f"  Rules: {'✅' if ym['rules'] else '❌'}, Brand Voice: {'✅' if ym['brand_voice'] else '❌'}")

            # 6. Errors
            errors = data.get("error_log", [])
            lines.append(f"▸ Error log: {len(errors)} entries")

            return "\n".join(lines)

        if action == "agents":
            lines = ["═══ AGENT STATUS ═══"]
            agents_info = [
                ("👑 Санторо", "CEO", "claude-sonnet-4", ["Web Search", "Web Page Reader"]),
                ("📊 Амара", "CFO", "claude-3.5-haiku", ["Financial Tracker", "Subscription Monitor", "API Usage Tracker"]),
                ("📱 Юки", "SMM", "claude-3.5-haiku", ["Content Generator", "Yuki Memory", "LinkedIn Publisher"]),
                ("⚙️ Нирадж", "CTO", "claude-sonnet-4", ["System Health Checker", "Integration Manager", "Web Search", "Web Page Reader"]),
            ]
            api_key = os.getenv("OPENROUTER_API_KEY", "")
            for name, role, model, tools in agents_info:
                status = "✅ Active" if api_key else "❌ No API key"
                lines.append(f"  {name} ({role}): {status}")
                lines.append(f"    Model: {model}")
                lines.append(f"    Tools: {', '.join(tools)}")
            return "\n".join(lines)

        if action == "errors":
            errors = data.get("error_log", [])
            if not errors:
                return "Error log is empty. No errors recorded."
            lines = [f"═══ ERROR LOG ({len(errors)} entries) ═══"]
            for e in errors[-10:]:
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
            data["error_log"] = errors[-50:]
            _save_data(data)
            return f"Error logged: {message}"

        if action == "clear_errors":
            data["error_log"] = []
            _save_data(data)
            return "Error log cleared."

        return f"Unknown action: {action}"


# ──────────────────────────────────────────────────────────
# Tool 2: Integration Manager (with real HTTP checks)
# ──────────────────────────────────────────────────────────

class IntegrationInput(BaseModel):
    action: str = Field(
        ...,
        description=(
            "Action: 'list' (all integrations with live status check), "
            "'check' (ping specific integration — needs name), "
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
        "Manages integrations with REAL connectivity checks. "
        "Pings endpoints, verifies tokens, reports actual status. "
        "Actions: list, check, activate, deactivate, add_cron, list_cron."
    )
    args_schema: Type[BaseModel] = IntegrationInput

    def _run(self, action: str, name: str = None, endpoint: str = None,
             schedule: str = None) -> str:
        data = _load_data()
        integrations = data.get("integrations", {})

        # Ensure default integrations exist
        if not integrations:
            integrations = {
                "railway_app": {"name": "Railway App", "endpoint": "https://crewai-studio-production-b962.up.railway.app/", "status": "unknown"},
                "openrouter": {"name": "OpenRouter API", "endpoint": "https://openrouter.ai/api/v1/models", "status": "unknown"},
                "linkedin": {"name": "LinkedIn API", "endpoint": "https://api.linkedin.com/v2/userinfo", "status": "unknown"},
            }
            data["integrations"] = integrations
            _save_data(data)

        if action == "list":
            lines = ["═══ INTEGRATIONS (live check) ═══"]
            for key, info in integrations.items():
                ep = info.get("endpoint", "")
                if ep and ep.startswith("http"):
                    ping = _http_ping(ep, timeout=8)
                    real_status = "✅ Online" if ping["ok"] else f"❌ Down ({ping.get('error', '?')})"
                    ms = f" ({ping['ms']}ms)" if ping.get("ms") else ""
                    # Update stored status
                    info["status"] = "active" if ping["ok"] else "down"
                    info["last_check"] = datetime.now().isoformat()
                else:
                    real_status = "⚠️ No endpoint configured"
                    ms = ""
                lines.append(f"  {real_status}{ms} — {info.get('name', key)}")
                if ep:
                    lines.append(f"    Endpoint: {ep}")
            _save_data(data)
            return "\n".join(lines)

        if action == "check":
            if not name:
                return "Error: need integration name"
            key = name.lower().replace(" ", "_")
            if key not in integrations:
                return f"Integration '{name}' not found. Available: {', '.join(integrations.keys())}"
            info = integrations[key]
            ep = info.get("endpoint", "")
            lines = [f"═══ CHECK: {info.get('name', key)} ═══"]
            if ep and ep.startswith("http"):
                ping = _http_ping(ep)
                if ping["ok"]:
                    lines.append(f"Status: ✅ Online (HTTP {ping['code']}, {ping['ms']}ms)")
                else:
                    lines.append(f"Status: ❌ Down — {ping.get('error', '?')}")
                info["status"] = "active" if ping["ok"] else "down"
                info["last_check"] = datetime.now().isoformat()
                _save_data(data)
            else:
                lines.append("Status: ⚠️ No endpoint to check")
            lines.append(f"Endpoint: {ep or 'Not configured'}")
            return "\n".join(lines)

        if action == "activate":
            if not name:
                return "Error: need integration name"
            key = name.lower().replace(" ", "_")
            if key not in integrations:
                integrations[key] = {"name": name, "status": "active", "endpoint": endpoint or "", "last_check": datetime.now().isoformat()}
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
                "name": name, "schedule": schedule, "endpoint": endpoint or "",
                "created": datetime.now().isoformat(), "active": True,
            })
            data["cron_jobs"] = cron_jobs
            _save_data(data)
            return f"Cron job added: '{name}' with schedule '{schedule}'"

        if action == "list_cron":
            cron_jobs = data.get("cron_jobs", [])
            if not cron_jobs:
                return "No cron jobs configured."
            lines = ["═══ CRON JOBS ═══"]
            for job in cron_jobs:
                status = "✅" if job.get("active") else "❌"
                lines.append(f"  {status} {job['name']}: {job['schedule']}")
            return "\n".join(lines)

        return f"Unknown action: {action}"
