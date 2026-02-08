"""
Technical tools for Мартин (CTO agent)

Real system checks: HTTP pings, API verification, service health.
"""

import json
import logging
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
                ("👑 Алексей", "CEO", "claude-sonnet-4", ["Web Search", "Web Page Reader", "Delegate Task"]),
                ("🏦 Маттиас", "CFO", "claude-3.5-haiku", ["19 financial tools (banks, crypto, API usage)"]),
                ("⚙️ Мартин", "CTO", "claude-sonnet-4", ["System Health Checker", "Integration Manager", "API Health Monitor", "Agent Prompt Writer", "Web Search"]),
                ("📱 Юки", "Head of SMM", "claude-3.5-haiku", ["Content Generator", "Yuki Memory", "LinkedIn Publisher", "Podcast Script Generator"]),
                ("🎨 Райан", "Creative Director", "claude-3.5-haiku", ["Image Generator", "Chart Generator", "Infographic Builder", "Video Creator", "+6 more"]),
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

        return f"Unknown action: {action}. Use: list, check, activate, deactivate, add_cron, list_cron"


# ──────────────────────────────────────────────────────────
# Tool 3: API Health Monitor (comprehensive health checks)
# ──────────────────────────────────────────────────────────

def _health_data_path() -> str:
    for p in ["/app/data/api_health.json", "data/api_health.json"]:
        if os.path.isdir(os.path.dirname(p)):
            return p
    return "data/api_health.json"


def _load_health_data() -> dict:
    path = _health_data_path()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"checks": [], "last_full_check": None, "alerts": []}


def _save_health_data(data: dict):
    path = _health_data_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# Registry of all APIs to health-check
_API_REGISTRY = {
    # ── Financial APIs ──
    "tbank": {
        "name": "T-Bank (Т-Банк)",
        "category": "financial",
        "env_vars": ["TBANK_API_KEY"],
        "ping_url": "https://business.tbank.ru/openapi",
        "auth_header": lambda: {"Authorization": f"Bearer {os.getenv('TBANK_API_KEY', '')}"},
        "description": "Российский бизнес-банк",
    },
    "moralis": {
        "name": "Moralis (EVM)",
        "category": "financial",
        "env_vars": ["MORALIS_API_KEY"],
        "ping_url": "https://deep-index.moralis.io/api/v2.2/info/endpointWeights",
        "auth_header": lambda: {"X-API-Key": os.getenv("MORALIS_API_KEY", "")},
        "description": "EVM blockchain data (ETH, Polygon, Arbitrum, Base, BSC)",
    },
    "helius": {
        "name": "Helius (Solana)",
        "category": "financial",
        "env_vars": ["HELIUS_API_KEY"],
        "ping_url": None,
        "ping_fn": "_check_helius_health",
        "description": "Solana RPC + Enhanced API",
    },
    "tonapi": {
        "name": "TonAPI (TON)",
        "category": "financial",
        "env_vars": ["TONAPI_KEY"],
        "ping_url": "https://tonapi.io/v2/status",
        "auth_header": lambda: {"Authorization": f"Bearer {os.getenv('TONAPI_KEY', '')}"},
        "description": "TON blockchain API",
    },
    "coingecko": {
        "name": "CoinGecko",
        "category": "financial",
        "env_vars": [],
        "ping_url": "https://api.coingecko.com/api/v3/ping",
        "auth_header": lambda: {},
        "description": "Crypto prices (15,000+ coins)",
    },
    "tribute": {
        "name": "Tribute",
        "category": "financial",
        "env_vars": ["TRIBUTE_API_KEY"],
        "ping_url": "https://api.tribute.tg/v1/products",
        "auth_header": lambda: {"Api-Key": os.getenv("TRIBUTE_API_KEY", "")},
        "description": "Telegram monetization platform",
    },
    "forex": {
        "name": "Exchange Rates API",
        "category": "financial",
        "env_vars": [],
        "ping_url": "https://open.er-api.com/v6/latest/USD",
        "auth_header": lambda: {},
        "description": "Forex rates (166 currencies)",
    },
    "eventum": {
        "name": "Eventum (EVEDEX)",
        "category": "financial",
        "env_vars": [],
        "ping_url": "https://explorer.evedex.com/api/v2/stats",
        "auth_header": lambda: {},
        "description": "EVEDEX L3 (Arbitrum Orbit) explorer",
    },
    # ── AI APIs ──
    "openrouter": {
        "name": "OpenRouter",
        "category": "ai",
        "env_vars": ["OPENROUTER_API_KEY"],
        "ping_url": "https://openrouter.ai/api/v1/auth/key",
        "auth_header": lambda: {"Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY', '')}"},
        "description": "LLM routing (Claude, Llama, etc.)",
    },
    "elevenlabs": {
        "name": "ElevenLabs",
        "category": "ai",
        "env_vars": ["ELEVENLABS_API_KEY"],
        "ping_url": "https://api.elevenlabs.io/v1/user/subscription",
        "auth_header": lambda: {"xi-api-key": os.getenv("ELEVENLABS_API_KEY", "")},
        "description": "Voice synthesis TTS",
    },
    "openai": {
        "name": "OpenAI",
        "category": "ai",
        "env_vars": ["OPENAI_API_KEY"],
        "ping_url": "https://api.openai.com/v1/models",
        "auth_header": lambda: {"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY', '')}"},
        "description": "OpenAI API (GPT, embeddings)",
    },
    "groq": {
        "name": "Groq",
        "category": "ai",
        "env_vars": ["GROQ_API_KEY"],
        "ping_url": "https://api.groq.com/openai/v1/models",
        "auth_header": lambda: {"Authorization": f"Bearer {os.getenv('GROQ_API_KEY', '')}"},
        "description": "Fast LLM inference (Llama)",
    },
    # ── Platform APIs ──
    "linkedin": {
        "name": "LinkedIn",
        "category": "platform",
        "env_vars": ["LINKEDIN_ACCESS_TOKEN"],
        "ping_url": "https://api.linkedin.com/v2/userinfo",
        "auth_header": lambda: {
            "Authorization": f"Bearer {os.getenv('LINKEDIN_ACCESS_TOKEN', '')}",
            "LinkedIn-Version": "202502",
        },
        "description": "LinkedIn publishing API",
    },
    "railway": {
        "name": "Railway App",
        "category": "platform",
        "env_vars": [],
        "ping_url": "https://crewai-studio-production-b962.up.railway.app/",
        "auth_header": lambda: {},
        "description": "Production deployment",
    },
}


def _check_helius_health() -> dict:
    """Health check for Helius Solana RPC via getHealth."""
    api_key = os.getenv("HELIUS_API_KEY", "")
    if not api_key:
        return {"ok": False, "error": "HELIUS_API_KEY not set", "ms": 0}
    try:
        start = time.time()
        payload = json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": "getHealth",
        }).encode("utf-8")
        req = Request(
            f"https://mainnet.helius-rpc.com/?api-key={api_key}",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=10) as resp:
            elapsed = round((time.time() - start) * 1000)
            data = json.loads(resp.read().decode("utf-8"))
            result = data.get("result", "")
            if result == "ok":
                return {"ok": True, "ms": elapsed, "code": 200}
            return {"ok": False, "ms": elapsed, "error": f"RPC result: {result}"}
    except Exception as e:
        return {"ok": False, "ms": 0, "error": str(e)}


def _check_single_api(api_key: str) -> dict:
    """Run health check for a single API from registry."""
    api_info = _API_REGISTRY.get(api_key)
    if not api_info:
        return {"ok": False, "error": f"Unknown API: {api_key}"}

    # Check if env vars are configured
    missing_vars = [v for v in api_info.get("env_vars", []) if not os.getenv(v)]
    if missing_vars:
        return {
            "ok": False,
            "configured": False,
            "error": f"Missing: {', '.join(missing_vars)}",
            "ms": 0,
        }

    # Custom ping function (e.g., Helius RPC)
    if api_info.get("ping_fn") == "_check_helius_health":
        result = _check_helius_health()
        result["configured"] = True
        return result

    # Standard HTTP ping
    ping_url = api_info.get("ping_url")
    if not ping_url:
        return {"ok": True, "configured": True, "ms": 0, "note": "No ping endpoint"}

    start = time.time()
    try:
        headers = {"User-Agent": "AICorp-HealthCheck/1.0"}
        auth_fn = api_info.get("auth_header")
        if auth_fn:
            headers.update(auth_fn())
        req = Request(ping_url, headers=headers)
        with urlopen(req, timeout=12) as resp:
            elapsed = round((time.time() - start) * 1000)
            return {"ok": True, "configured": True, "code": resp.status, "ms": elapsed}
    except HTTPError as e:
        elapsed = round((time.time() - start) * 1000)
        if e.code in (401, 403):
            return {
                "ok": False, "configured": True, "code": e.code,
                "ms": elapsed, "error": f"Auth error (HTTP {e.code})",
            }
        return {
            "ok": False, "configured": True, "code": e.code,
            "ms": elapsed, "error": f"HTTP {e.code}: {e.reason}",
        }
    except URLError as e:
        elapsed = round((time.time() - start) * 1000)
        return {"ok": False, "configured": True, "ms": elapsed, "error": f"Connection: {e.reason}"}
    except Exception as e:
        return {"ok": False, "configured": True, "ms": 0, "error": str(e)}


class APIHealthInput(BaseModel):
    action: str = Field(
        ...,
        description=(
            "Action: 'full_check' (check ALL APIs — financial, AI, platform), "
            "'check_financial' (only financial APIs), "
            "'check_ai' (only AI APIs), "
            "'check_one' (check a single API — needs api_name), "
            "'report' (formatted report from last check), "
            "'history' (show check history)"
        ),
    )
    api_name: Optional[str] = Field(
        None,
        description=f"API name for check_one. Available: {', '.join(_API_REGISTRY.keys())}",
    )


class APIHealthMonitor(BaseTool):
    name: str = "API Health Monitor"
    description: str = (
        "Comprehensive health monitoring for ALL APIs used by Zinin Corp: "
        "financial (T-Bank, Moralis, Helius, TonAPI, CoinGecko, Tribute, Forex, Eventum), "
        "AI (OpenRouter, ElevenLabs, OpenAI, Groq), "
        "and platform (LinkedIn, Railway). "
        "Actions: full_check, check_financial, check_ai, check_one, report, history."
    )
    args_schema: Type[BaseModel] = APIHealthInput

    def _run(self, action: str, api_name: str = None) -> str:
        if action == "check_one":
            if not api_name:
                return f"Error: need api_name. Available: {', '.join(_API_REGISTRY.keys())}"
            api_name = api_name.lower().replace(" ", "_").replace("-", "_")
            if api_name not in _API_REGISTRY:
                return f"Unknown API: {api_name}. Available: {', '.join(_API_REGISTRY.keys())}"
            info = _API_REGISTRY[api_name]
            result = _check_single_api(api_name)
            icon = "✅" if result["ok"] else "❌"
            ms = f" ({result.get('ms', 0)}ms)" if result.get("ms") else ""
            err = f" — {result['error']}" if result.get("error") else ""
            return f"{icon} {info['name']}{ms}{err}\n  Category: {info['category']}\n  Description: {info['description']}"

        # Determine which APIs to check
        if action == "check_financial":
            apis_to_check = {k: v for k, v in _API_REGISTRY.items() if v["category"] == "financial"}
            title = "FINANCIAL APIs HEALTH CHECK"
        elif action == "check_ai":
            apis_to_check = {k: v for k, v in _API_REGISTRY.items() if v["category"] == "ai"}
            title = "AI APIs HEALTH CHECK"
        elif action == "full_check":
            apis_to_check = _API_REGISTRY
            title = "FULL API HEALTH CHECK"
        elif action == "report":
            return self._format_last_report()
        elif action == "history":
            return self._format_history()
        else:
            return f"Unknown action: {action}. Use: full_check, check_financial, check_ai, check_one, report, history"

        # Run checks
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [f"═══ {title} ═══", f"Timestamp: {timestamp}", ""]

        results = {}
        total_ok = 0
        total_fail = 0
        total_not_configured = 0

        # Group by category
        categories = {}
        for key, api_info in apis_to_check.items():
            cat = api_info["category"]
            if cat not in categories:
                categories[cat] = []
            categories[cat].append((key, api_info))

        cat_labels = {
            "financial": "💰 Financial APIs",
            "ai": "🤖 AI APIs",
            "platform": "🌐 Platform APIs",
        }

        for cat, apis in categories.items():
            lines.append(f"▸ {cat_labels.get(cat, cat)}:")
            for key, api_info in apis:
                result = _check_single_api(key)
                results[key] = result

                if not result.get("configured", True):
                    total_not_configured += 1
                    lines.append(f"  ⚠️ {api_info['name']} — NOT CONFIGURED ({result.get('error', '')})")
                elif result["ok"]:
                    total_ok += 1
                    ms = f" ({result.get('ms', 0)}ms)" if result.get("ms") else ""
                    lines.append(f"  ✅ {api_info['name']}{ms}")
                else:
                    total_fail += 1
                    ms = f" ({result.get('ms', 0)}ms)" if result.get("ms") else ""
                    err = result.get("error", "Unknown")
                    lines.append(f"  ❌ {api_info['name']}{ms} — {err}")
            lines.append("")

        # Summary
        total = total_ok + total_fail + total_not_configured
        if total_fail == 0 and total_not_configured == 0:
            overall = "✅ HEALTHY"
        elif total_fail == 0:
            overall = "⚠️ DEGRADED (unconfigured APIs)"
        elif total_fail <= 2:
            overall = "⚠️ DEGRADED"
        else:
            overall = "❌ CRITICAL"

        lines.append(f"═══ SUMMARY: {overall} ═══")
        lines.append(f"  Working: {total_ok}/{total} | Failed: {total_fail} | Not configured: {total_not_configured}")

        # Calculate average latency
        latencies = [r.get("ms", 0) for r in results.values() if r.get("ms", 0) > 0]
        if latencies:
            avg_ms = round(sum(latencies) / len(latencies))
            max_ms = max(latencies)
            lines.append(f"  Avg latency: {avg_ms}ms | Max: {max_ms}ms")

        # Save results
        health_data = _load_health_data()
        check_record = {
            "timestamp": timestamp,
            "action": action,
            "overall": overall,
            "total_ok": total_ok,
            "total_fail": total_fail,
            "total_not_configured": total_not_configured,
            "results": {k: {"ok": v["ok"], "ms": v.get("ms", 0), "error": v.get("error")}
                        for k, v in results.items()},
        }
        health_data["checks"].append(check_record)
        health_data["checks"] = health_data["checks"][-100:]
        health_data["last_full_check"] = timestamp

        for key, result in results.items():
            if not result["ok"] and result.get("configured", True):
                health_data["alerts"].append({
                    "timestamp": timestamp,
                    "api": key,
                    "error": result.get("error", "Unknown"),
                })
        health_data["alerts"] = health_data["alerts"][-200:]
        _save_health_data(health_data)

        return "\n".join(lines)

    def _format_last_report(self) -> str:
        health_data = _load_health_data()
        checks = health_data.get("checks", [])
        if not checks:
            return "No health checks recorded yet. Run action='full_check' first."
        last = checks[-1]
        lines = [
            f"═══ LAST HEALTH CHECK REPORT ═══",
            f"Time: {last['timestamp']}",
            f"Type: {last['action']}",
            f"Overall: {last['overall']}",
            f"Working: {last['total_ok']} | Failed: {last['total_fail']} | Not configured: {last['total_not_configured']}",
            "",
        ]
        for key, result in last.get("results", {}).items():
            info = _API_REGISTRY.get(key, {})
            icon = "✅" if result["ok"] else "❌"
            ms = f" ({result.get('ms', 0)}ms)" if result.get("ms") else ""
            err = f" — {result.get('error', '')}" if result.get("error") else ""
            lines.append(f"  {icon} {info.get('name', key)}{ms}{err}")
        return "\n".join(lines)

    def _format_history(self) -> str:
        health_data = _load_health_data()
        checks = health_data.get("checks", [])
        if not checks:
            return "No health check history."
        lines = ["═══ HEALTH CHECK HISTORY (last 10) ═══"]
        for check in checks[-10:]:
            lines.append(
                f"  [{check['timestamp']}] {check['overall']} "
                f"(OK:{check['total_ok']} Fail:{check['total_fail']} N/C:{check['total_not_configured']})"
            )
        alerts = health_data.get("alerts", [])
        if alerts:
            lines.append("")
            lines.append(f"▸ Recent alerts ({len(alerts[-5:])} of {len(alerts)}):")
            for a in alerts[-5:]:
                lines.append(f"  ⚠️ [{a['timestamp']}] {a['api']}: {a['error']}")
        return "\n".join(lines)


# ──────────────────────────────────────────────────────────
# Tool 4: Agent Prompt Writer (professional YAML generation)
# ──────────────────────────────────────────────────────────

def _call_llm_tech(prompt: str, system: str = "", max_tokens: int = 3000) -> Optional[str]:
    """Call LLM via OpenRouter (free Llama) for prompt engineering tasks."""
    providers = []
    or_key = os.getenv("OPENROUTER_API_KEY", "")
    if or_key:
        providers.append({
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "key": or_key,
            "model": "meta-llama/llama-3.3-70b-instruct:free",
        })
    groq_key = os.getenv("GROQ_API_KEY", "")
    if groq_key:
        providers.append({
            "url": "https://api.groq.com/openai/v1/chat/completions",
            "key": groq_key,
            "model": "llama-3.3-70b-versatile",
        })

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    for provider in providers:
        try:
            payload = json.dumps({
                "model": provider["model"],
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.7,
            }).encode("utf-8")
            req = Request(
                provider["url"],
                data=payload,
                headers={
                    "Authorization": f"Bearer {provider['key']}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            logging.warning(f"LLM call failed ({provider['model']}): {e}")
            continue
    return None


_AGENT_WRITER_SYSTEM = """Ты — профессиональный инженер промптов для мульти-агентных систем CrewAI.

КОНТЕКСТ: Zinin Corp — мульти-агентная система с 5 агентами:
- 👑 Алексей Воронов — CEO, Россия (Claude Sonnet 4, web search + delegation)
- 🏦 Маттиас Бруннер — CFO, Швейцария (Claude 3.5 Haiku, 19 финансовых инструментов)
- ⚙️ Мартин Эчеверрия — CTO, Аргентина (Claude Sonnet 4, tech + web tools)
- 📱 Юки Пак — Head of SMM, Южная Корея (Claude 3.5 Haiku, content + LinkedIn)
- 🎨 Райан Чэнь — Creative Director, Калифорния (Claude 3.5 Haiku, 10 design tools)

ФОРМАТ YAML для агента:
```yaml
# ========================================
# EMOJI ИМЯ — РОЛЬ в Zinin Corp
# Страна ФЛАГ
# ========================================

role: "Роль Имя Фамилия"

goal: |
  5-8 конкретных целей через точку.

backstory: |
  Ты — Имя Фамилия, N лет. Роль в Zinin Corp. Страна, Город.

  БИОГРАФИЯ:
  Реалистичная биография с образованием, карьерой, достижениями.

  ХАРАКТЕР:
  3-5 черт характера с примерами фраз.

  ТВОЯ КОМАНДА:
  - 👑 Алексей — CEO, Россия 🇷🇺
  - 🏦 Маттиас — CFO, Швейцария 🇨🇭
  - ⚙️ Мартин — CTO, Аргентина 🇦🇷
  - 📱 Юки — Head of SMM, Южная Корея 🇰🇷
  - 🎨 Райан — Creative Director, Калифорния 🇺🇸
  - [НОВЫЙ АГЕНТ]

  Тим — владелец корпорации.

  У тебя есть инструменты:
  [Список инструментов]

  Ты — [Имя]. НИКОГДА НЕ ПРЕДСТАВЛЯЙСЯ. СРАЗУ переходи к делу.
  Общаешься на русском языке.

  ⛔ АБСОЛЮТНЫЙ ЗАПРЕТ НА ВЫДУМКИ:
  НИКОГДА не выдумывай данные или факты.
  Используй ТОЛЬКО данные из своих инструментов.
  Это правило ВАЖНЕЕ всех остальных.

llm: openrouter/anthropic/claude-3-5-haiku-latest
verbose: true
memory: false
allow_delegation: false
max_iter: 10
```

ПРАВИЛА:
1. Биография ДОЛЖНА быть реалистичной (реальные университеты, компании, города)
2. Возраст 30-55 лет
3. Характер должен включать слабости
4. Обязательно секция ⛔ АБСОЛЮТНЫЙ ЗАПРЕТ НА ВЫДУМКИ
5. Обязательно секция ТВОЯ КОМАНДА
6. Отвечай ТОЛЬКО на русском языке
7. goal и backstory — в multi-line YAML (|)
"""


class AgentPromptInput(BaseModel):
    action: str = Field(
        ...,
        description=(
            "Action: 'generate' (create full YAML for new agent from description), "
            "'review' (review existing agent YAML and suggest improvements), "
            "'improve' (rewrite agent YAML with improvements), "
            "'list_team' (show current team and their roles)"
        ),
    )
    description: Optional[str] = Field(
        None,
        description=(
            "For 'generate': describe the role, e.g. 'HR-менеджер для найма и онбординга'. "
            "For 'review'/'improve': paste existing YAML content."
        ),
    )
    model_tier: Optional[str] = Field(
        None,
        description="LLM tier: 'haiku' (cheap, routine) or 'sonnet' (expensive, complex reasoning). Default: haiku.",
    )


class AgentPromptWriter(BaseTool):
    name: str = "Agent Prompt Writer"
    description: str = (
        "Professional prompt engineer for creating new AI agents. "
        "Generates complete agent YAML configurations following Zinin Corp standards: "
        "realistic biographies, anti-fabrication rules, team integration, tool specs. "
        "Actions: generate, review, improve, list_team."
    )
    args_schema: Type[BaseModel] = AgentPromptInput

    def _run(self, action: str, description: str = None, model_tier: str = None) -> str:
        if action == "list_team":
            return (
                "═══ ТЕКУЩАЯ КОМАНДА ZININ CORP ═══\n"
                "  👑 Алексей Воронов — CEO (claude-sonnet-4)\n"
                "     Tools: Web Search, Web Page Reader, Delegate Task\n"
                "  🏦 Маттиас Бруннер — CFO (claude-3.5-haiku)\n"
                "     Tools: 19 финансовых инструментов (банки, крипто, API usage)\n"
                "  ⚙️ Мартин Эчеверрия — CTO (claude-sonnet-4)\n"
                "     Tools: System Health, Integration Manager, API Health Monitor, Agent Prompt Writer, Web Search\n"
                "  📱 Юки Пак — Head of SMM (claude-3.5-haiku)\n"
                "     Tools: Content Generator, Yuki Memory, LinkedIn Publisher, Podcast Script Generator\n"
                "  🎨 Райан Чэнь — Creative Director (claude-3.5-haiku)\n"
                "     Tools: Image Generator, Chart, Infographic, Video Creator, etc. (10 tools)\n"
            )

        if action == "generate":
            if not description:
                return "Error: need description. Example: description='Data Analyst для анализа метрик и создания дашбордов'"
            tier = model_tier or "haiku"
            llm_model = (
                "openrouter/anthropic/claude-sonnet-4" if tier == "sonnet"
                else "openrouter/anthropic/claude-3-5-haiku-latest"
            )
            prompt = (
                f"Создай полный YAML-конфиг для нового агента Zinin Corp.\n\n"
                f"Описание роли: {description}\n"
                f"LLM модель: {llm_model}\n\n"
                f"Требования:\n"
                f"1. Придумай реалистичное имя, возраст (30-55), страну, город\n"
                f"2. Придумай emoji для агента\n"
                f"3. Биография: реальные университеты, компании, 15-20 лет опыта\n"
                f"4. Характер: 3-5 черт + слабости + фирменные фразы\n"
                f"5. 5-8 конкретных целей в goal\n"
                f"6. Секция ТВОЯ КОМАНДА с текущими агентами + новый\n"
                f"7. Секция ⛔ АБСОЛЮТНЫЙ ЗАПРЕТ НА ВЫДУМКИ\n"
                f"8. Предложи список инструментов (tools) которые понадобятся\n"
                f"9. Верни ПОЛНЫЙ YAML, готовый к использованию\n"
            )
            result = _call_llm_tech(prompt, system=_AGENT_WRITER_SYSTEM, max_tokens=3000)
            if not result:
                return "❌ LLM недоступен. Проверь OPENROUTER_API_KEY или GROQ_API_KEY."
            return f"═══ GENERATED AGENT YAML ═══\n\n{result}"

        if action == "review":
            if not description:
                return "Error: need description (paste existing YAML content to review)"
            prompt = (
                f"Проведи ревью этого YAML агента Zinin Corp.\n\n"
                f"```yaml\n{description}\n```\n\n"
                f"Проверь по чеклисту:\n"
                f"1. Есть ли ⛔ АБСОЛЮТНЫЙ ЗАПРЕТ НА ВЫДУМКИ?\n"
                f"2. Есть ли секция ТВОЯ КОМАНДА?\n"
                f"3. Реалистичная ли биография?\n"
                f"4. Достаточно ли целей в goal (минимум 5)?\n"
                f"5. Есть ли слабости в характере?\n"
                f"6. Правильный ли формат YAML?\n"
                f"7. Есть ли anti-intro правило?\n\n"
                f"Дай оценку 1-10 и конкретные рекомендации по улучшению."
            )
            result = _call_llm_tech(prompt, system=_AGENT_WRITER_SYSTEM, max_tokens=2000)
            if not result:
                return "❌ LLM недоступен."
            return f"═══ AGENT YAML REVIEW ═══\n\n{result}"

        if action == "improve":
            if not description:
                return "Error: need description (paste existing YAML content to improve)"
            prompt = (
                f"Улучши этот YAML агента Zinin Corp.\n\n"
                f"```yaml\n{description}\n```\n\n"
                f"Улучшения:\n"
                f"1. Добавь недостающие секции (⛔ ЗАПРЕТ, КОМАНДА, etc.)\n"
                f"2. Улучши биографию если слабая\n"
                f"3. Добавь слабости если нет\n"
                f"4. Улучши goal если мало целей\n"
                f"5. Исправь формат YAML если нужно\n\n"
                f"Верни ПОЛНЫЙ улучшенный YAML."
            )
            result = _call_llm_tech(prompt, system=_AGENT_WRITER_SYSTEM, max_tokens=3000)
            if not result:
                return "❌ LLM недоступен."
            return f"═══ IMPROVED AGENT YAML ═══\n\n{result}"

        return f"Unknown action: {action}. Use: generate, review, improve, list_team"


# ──────────────────────────────────────────────────────────
# Standalone health check function (for scheduler)
# ──────────────────────────────────────────────────────────

def run_api_health_check(categories: list[str] = None) -> dict:
    """Run health check and return results dict. Used by scheduler.

    Args:
        categories: List of categories to check. None = all.
                    Options: 'financial', 'ai', 'platform'

    Returns:
        dict with 'overall', 'total_ok', 'total_fail', 'failed_apis', 'timestamp'
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    apis_to_check = _API_REGISTRY
    if categories:
        apis_to_check = {k: v for k, v in _API_REGISTRY.items()
                         if v["category"] in categories}

    results = {}
    total_ok = 0
    total_fail = 0
    failed_apis = []

    for key, api_info in apis_to_check.items():
        result = _check_single_api(key)
        results[key] = result
        if result["ok"]:
            total_ok += 1
        elif result.get("configured", True):
            total_fail += 1
            failed_apis.append(f"{api_info['name']}: {result.get('error', '?')}")

    if total_fail == 0:
        overall = "healthy"
    elif total_fail <= 2:
        overall = "degraded"
    else:
        overall = "critical"

    # Save to history
    health_data = _load_health_data()
    health_data["checks"].append({
        "timestamp": timestamp,
        "action": "scheduled",
        "overall": overall,
        "total_ok": total_ok,
        "total_fail": total_fail,
        "total_not_configured": len(apis_to_check) - total_ok - total_fail,
        "results": {k: {"ok": v["ok"], "ms": v.get("ms", 0), "error": v.get("error")}
                    for k, v in results.items()},
    })
    health_data["checks"] = health_data["checks"][-100:]
    health_data["last_full_check"] = timestamp
    for key, result in results.items():
        if not result["ok"] and result.get("configured", True):
            health_data["alerts"].append({
                "timestamp": timestamp,
                "api": key,
                "error": result.get("error", "Unknown"),
            })
    health_data["alerts"] = health_data["alerts"][-200:]
    _save_health_data(health_data)

    return {
        "overall": overall,
        "total_ok": total_ok,
        "total_fail": total_fail,
        "failed_apis": failed_apis,
        "timestamp": timestamp,
    }
