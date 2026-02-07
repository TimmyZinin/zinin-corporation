"""
Financial tools for Маттиас (CFO agent)
"""

import json
import os
from datetime import datetime
from typing import Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


def _data_path() -> str:
    """Resolve financial_data.json path (Docker or local)"""
    for p in ["/app/data/financial_data.json", "data/financial_data.json"]:
        if os.path.exists(os.path.dirname(p) or "."):
            return p
    return "data/financial_data.json"


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
        "projects": {
            "crypto_club": {
                "name": "Крипто маркетологи",
                "priority": 1,
                "revenue": {"subscriptions": 0, "one_time": 0},
                "expenses": {"api_costs": 0, "infrastructure": 0},
            },
            "sborka": {
                "name": "Сборка",
                "priority": 2,
                "revenue": {"services": 0, "consulting": 0},
                "expenses": {"api_costs": 0, "expert_fees": 0},
            },
            "botanika": {
                "name": "Ботаника",
                "priority": 3,
                "revenue": {"services": 0},
                "expenses": {"api_costs": 0},
            },
            "personal_brand": {
                "name": "Личный бренд",
                "priority": 4,
                "revenue": {"consulting": 0},
                "expenses": {"api_costs": 0},
            },
        },
        "subscriptions": {
            "crypto_club": {
                "active": 0,
                "monthly_price_rub": 0,
                "churn_rate": 0.05,
            },
            "sborka": {
                "active": 0,
                "monthly_price_rub": 0,
                "churn_rate": 0.03,
            },
        },
        "api_usage": {
            "manager": {"name": "Управленец", "used_usd": 0, "limit_usd": 50},
            "accountant": {"name": "Маттиас", "used_usd": 0, "limit_usd": 30},
            "automator": {"name": "Автоматизатор", "used_usd": 0, "limit_usd": 100},
        },
        "last_updated": datetime.now().isoformat(),
    }


# ──────────────────────────────────────────────────────────
# Tool 1: Financial Tracker
# ──────────────────────────────────────────────────────────

class FinancialTrackerInput(BaseModel):
    action: str = Field(
        ...,
        description=(
            "Action to perform: "
            "'add_income' (needs project, category, amount), "
            "'add_expense' (needs project, category, amount), "
            "'report' (optional project — omit for full report), "
            "'roi' (ROI ranking of all projects), "
            "'summary' (quick one-line per project)"
        ),
    )
    project: Optional[str] = Field(
        None,
        description="Project key: crypto_club, sborka, botanika, personal_brand",
    )
    category: Optional[str] = Field(
        None,
        description="Revenue/expense category (e.g. subscriptions, api_costs, consulting)",
    )
    amount: Optional[float] = Field(None, description="Amount in RUB")


class FinancialTracker(BaseTool):
    name: str = "Financial Tracker"
    description: str = (
        "Tracks income and expenses for all projects. "
        "Actions: add_income, add_expense, report, roi, summary."
    )
    args_schema: Type[BaseModel] = FinancialTrackerInput

    def _run(self, action: str, project: str = None, category: str = None,
             amount: float = None) -> str:
        data = _load_data()
        projects = data["projects"]

        if action == "add_income":
            if not all([project, category, amount is not None]):
                return "Error: need project, category, amount"
            if project not in projects:
                return f"Error: project '{project}' not found"
            rev = projects[project]["revenue"]
            if category not in rev:
                rev[category] = 0
            rev[category] += amount
            _save_data(data)
            return f"Added income: {project}/{category} +{amount} RUB"

        if action == "add_expense":
            if not all([project, category, amount is not None]):
                return "Error: need project, category, amount"
            if project not in projects:
                return f"Error: project '{project}' not found"
            exp = projects[project]["expenses"]
            if category not in exp:
                exp[category] = 0
            exp[category] += amount
            _save_data(data)
            return f"Added expense: {project}/{category} +{amount} RUB"

        if action == "report":
            return self._report(projects, project)

        if action == "roi":
            return self._roi(projects)

        if action == "summary":
            return self._summary(projects)

        return f"Unknown action: {action}"

    @staticmethod
    def _report(projects: dict, project_key: str = None) -> str:
        def _proj_report(key: str, p: dict) -> str:
            total_rev = sum(p["revenue"].values())
            total_exp = sum(p["expenses"].values())
            profit = total_rev - total_exp
            roi = (profit / total_exp * 100) if total_exp > 0 else 0
            lines = [
                f"=== {p.get('name', key.upper())} (priority #{p.get('priority','?')}) ===",
                f"Revenue: {total_rev:,.0f} RUB",
            ]
            for k, v in p["revenue"].items():
                lines.append(f"  {k}: {v:,.0f}")
            lines.append(f"Expenses: {total_exp:,.0f} RUB")
            for k, v in p["expenses"].items():
                lines.append(f"  {k}: {v:,.0f}")
            lines.append(f"Profit: {profit:,.0f} RUB | ROI: {roi:.1f}%")
            return "\n".join(lines)

        if project_key:
            if project_key not in projects:
                return f"Project '{project_key}' not found"
            return _proj_report(project_key, projects[project_key])

        parts = []
        total_rev = total_exp = 0
        for k, p in projects.items():
            parts.append(_proj_report(k, p))
            total_rev += sum(p["revenue"].values())
            total_exp += sum(p["expenses"].values())
        profit = total_rev - total_exp
        roi = (profit / total_exp * 100) if total_exp > 0 else 0
        parts.append(
            f"\n=== TOTAL ===\n"
            f"Revenue: {total_rev:,.0f} RUB\n"
            f"Expenses: {total_exp:,.0f} RUB\n"
            f"Profit: {profit:,.0f} RUB | ROI: {roi:.1f}%"
        )
        return "\n\n".join(parts)

    @staticmethod
    def _roi(projects: dict) -> str:
        rows = []
        for k, p in projects.items():
            rev = sum(p["revenue"].values())
            exp = sum(p["expenses"].values())
            profit = rev - exp
            roi = (profit / exp * 100) if exp > 0 else 0
            rows.append((p.get("name", k), rev, exp, profit, roi))
        rows.sort(key=lambda r: r[4], reverse=True)
        lines = ["ROI RANKING:"]
        for i, (name, rev, exp, profit, roi) in enumerate(rows, 1):
            lines.append(f"#{i} {name}: profit {profit:,.0f} RUB, ROI {roi:.1f}%")
        return "\n".join(lines)

    @staticmethod
    def _summary(projects: dict) -> str:
        lines = ["FINANCIAL SUMMARY:"]
        for k, p in sorted(projects.items(), key=lambda x: x[1].get("priority", 99)):
            rev = sum(p["revenue"].values())
            exp = sum(p["expenses"].values())
            lines.append(f"  {p.get('name', k)}: {rev:,.0f} rev / {exp:,.0f} exp / {rev - exp:,.0f} profit")
        return "\n".join(lines)


# ──────────────────────────────────────────────────────────
# Tool 2: Subscription Monitor
# ──────────────────────────────────────────────────────────

class SubscriptionInput(BaseModel):
    action: str = Field(
        ...,
        description=(
            "Action: 'status' (current subscribers), "
            "'forecast' (monthly revenue forecast), "
            "'churn' (churn analysis), "
            "'update' (set subscribers — needs project, count, price_rub)"
        ),
    )
    project: Optional[str] = Field(None, description="Project key: crypto_club or sborka")
    count: Optional[int] = Field(None, description="Number of active subscribers")
    price_rub: Optional[float] = Field(None, description="Monthly price in RUB")


class SubscriptionMonitor(BaseTool):
    name: str = "Subscription Monitor"
    description: str = (
        "Tracks active subscriptions in paid clubs. "
        "Actions: status, forecast, churn, update."
    )
    args_schema: Type[BaseModel] = SubscriptionInput

    def _run(self, action: str, project: str = None, count: int = None,
             price_rub: float = None) -> str:
        data = _load_data()
        subs = data.get("subscriptions", {})

        if action == "update":
            if not all([project, count is not None, price_rub is not None]):
                return "Error: need project, count, price_rub"
            if project not in subs:
                subs[project] = {"active": 0, "monthly_price_rub": 0, "churn_rate": 0.05}
            subs[project]["active"] = count
            subs[project]["monthly_price_rub"] = price_rub
            _save_data(data)
            return f"Updated: {project} — {count} subscribers at {price_rub} RUB/month"

        if action == "status":
            lines = ["SUBSCRIPTION STATUS:"]
            total = 0
            for k, s in subs.items():
                lines.append(f"  {k}: {s['active']} active @ {s['monthly_price_rub']:,.0f} RUB/mo")
                total += s["active"]
            lines.append(f"  Total subscribers: {total}")
            return "\n".join(lines)

        if action == "forecast":
            lines = ["MONTHLY REVENUE FORECAST:"]
            total = 0
            for k, s in subs.items():
                mrr = s["active"] * s["monthly_price_rub"]
                total += mrr
                lines.append(f"  {k}: {mrr:,.0f} RUB/month ({s['active']} x {s['monthly_price_rub']:,.0f})")
            lines.append(f"  TOTAL MRR: {total:,.0f} RUB/month")
            return "\n".join(lines)

        if action == "churn":
            lines = ["CHURN ANALYSIS:"]
            for k, s in subs.items():
                lost = int(s["active"] * s["churn_rate"])
                lost_revenue = lost * s["monthly_price_rub"]
                lines.append(
                    f"  {k}: ~{lost} subscribers/month ({s['churn_rate']*100:.0f}% rate), "
                    f"revenue risk: {lost_revenue:,.0f} RUB"
                )
            return "\n".join(lines)

        return f"Unknown action: {action}"


# ──────────────────────────────────────────────────────────
# Tool 3: API Usage Tracker
# ──────────────────────────────────────────────────────────

class APIUsageInput(BaseModel):
    action: str = Field(
        ...,
        description=(
            "Action: 'usage' (show all agents usage), "
            "'add' (add API spend — needs agent, amount_usd), "
            "'set_limit' (set limit — needs agent, amount_usd), "
            "'alerts' (check budget alerts), "
            "'reset' (reset all usage to 0 for new month)"
        ),
    )
    agent: Optional[str] = Field(
        None, description="Agent key: manager, accountant, automator"
    )
    amount_usd: Optional[float] = Field(None, description="Amount in USD")


class APIUsageTracker(BaseTool):
    name: str = "API Usage Tracker"
    description: str = (
        "Monitors API spending per agent and enforces budgets. "
        "Actions: usage, add, set_limit, alerts, reset."
    )
    args_schema: Type[BaseModel] = APIUsageInput

    def _run(self, action: str, agent: str = None, amount_usd: float = None) -> str:
        data = _load_data()
        api = data.get("api_usage", {})

        if action == "add":
            if not all([agent, amount_usd is not None]):
                return "Error: need agent and amount_usd"
            if agent not in api:
                return f"Error: agent '{agent}' not found"
            api[agent]["used_usd"] += amount_usd
            _save_data(data)
            pct = api[agent]["used_usd"] / api[agent]["limit_usd"] * 100
            warn = f" WARNING: {pct:.0f}% of limit!" if pct >= 80 else ""
            return f"Added ${amount_usd:.2f} to {agent}. Total: ${api[agent]['used_usd']:.2f}/{api[agent]['limit_usd']}{warn}"

        if action == "usage":
            lines = ["API USAGE (USD):"]
            total_used = total_limit = 0
            for k, a in api.items():
                pct = a["used_usd"] / a["limit_usd"] * 100 if a["limit_usd"] > 0 else 0
                status = "OK" if pct < 80 else "WARN" if pct < 100 else "OVER"
                lines.append(f"  [{status}] {a['name']} ({k}): ${a['used_usd']:.2f} / ${a['limit_usd']} ({pct:.0f}%)")
                total_used += a["used_usd"]
                total_limit += a["limit_usd"]
            lines.append(f"  TOTAL: ${total_used:.2f} / ${total_limit}")
            return "\n".join(lines)

        if action == "set_limit":
            if not all([agent, amount_usd is not None]):
                return "Error: need agent and amount_usd"
            if agent not in api:
                return f"Error: agent '{agent}' not found"
            api[agent]["limit_usd"] = amount_usd
            _save_data(data)
            return f"Limit set: {agent} = ${amount_usd}/month"

        if action == "alerts":
            alerts = []
            for k, a in api.items():
                pct = a["used_usd"] / a["limit_usd"] * 100 if a["limit_usd"] > 0 else 0
                if pct >= 100:
                    alerts.append(f"CRITICAL: {a['name']} ({k}) at {pct:.0f}% — OVER BUDGET!")
                elif pct >= 80:
                    alerts.append(f"WARNING: {a['name']} ({k}) at {pct:.0f}% — approaching limit")
            return "\n".join(alerts) if alerts else "All agents within budget limits."

        if action == "reset":
            for a in api.values():
                a["used_usd"] = 0
            _save_data(data)
            return "API usage reset to 0 for all agents (new month)."

        return f"Unknown action: {action}"
