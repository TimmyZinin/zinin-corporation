"""CrewAI Tool: OpenAI API cost tracking via Admin API."""

import logging
import os
import time

import httpx
from crewai.tools import BaseTool

logger = logging.getLogger(__name__)

OPENAI_API = "https://api.openai.com/v1"


def _get_headers() -> dict:
    key = os.environ.get("OPENAI_ADMIN_KEY", "")
    if not key:
        raise EnvironmentError("OPENAI_ADMIN_KEY not set")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def get_openai_costs(days: int = 30) -> dict:
    """Fetch cost data from OpenAI Admin API."""
    headers = _get_headers()

    now = int(time.time())
    start = now - (days * 86400)

    resp = httpx.get(
        f"{OPENAI_API}/organization/costs",
        headers=headers,
        params={
            "start_time": start,
            "end_time": now,
            "bucket_width": "1d",
            "limit": min(days, 180),
        },
        timeout=15,
    )
    resp.raise_for_status()
    page = resp.json()

    total = 0.0
    daily = []
    for bucket in page.get("data", []):
        day_total = 0.0
        for result in bucket.get("results", []):
            amount = result.get("amount", {})
            day_total += amount.get("value", 0)
        total += day_total
        daily.append({"date": bucket.get("start_time", 0), "cost": round(day_total, 4)})

    # Last 7 days subtotal
    week_cutoff = now - (7 * 86400)
    week_total = sum(d["cost"] for d in daily if d["date"] >= week_cutoff)

    # Today
    today_cutoff = now - 86400
    today_total = sum(d["cost"] for d in daily if d["date"] >= today_cutoff)

    return {
        "period_days": days,
        "total_usd": round(total, 4),
        "week_usd": round(week_total, 4),
        "today_usd": round(today_total, 4),
        "daily_avg_usd": round(total / max(len(daily), 1), 4),
        "days_with_data": len([d for d in daily if d["cost"] > 0]),
    }


class OpenAIUsageTool(BaseTool):
    name: str = "OpenAI API Usage"
    description: str = (
        "Расходы на OpenAI API (GPT, DALL-E, Whisper и др.).\n"
        "Показывает: потрачено за период, за неделю, сегодня.\n"
        "Параметр: количество дней (по умолчанию 30)."
    )

    def _run(self, argument: str = "30") -> str:
        try:
            days = 30
            if argument.strip().isdigit():
                days = min(int(argument.strip()), 180)

            data = get_openai_costs(days)

            lines = [
                f"OpenAI API — расходы за {data['period_days']} дней:",
                "",
                f"Всего: ${data['total_usd']:.4f}",
                f"За неделю: ${data['week_usd']:.4f}",
                f"Сегодня: ${data['today_usd']:.4f}",
                f"Среднее/день: ${data['daily_avg_usd']:.4f}",
                f"Дней с расходами: {data['days_with_data']}",
            ]

            return "\n".join(lines)

        except EnvironmentError:
            return "OPENAI_ADMIN_KEY не настроен. Нужен Admin API key из console.openai.com."
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                return "Нет доступа к OpenAI Admin API. Убедись, что используется Admin key (не обычный API key)."
            return f"Ошибка OpenAI API: {e.response.status_code}"
        except Exception as e:
            logger.error(f"OpenAI usage fetch failed: {e}")
            return f"Ошибка OpenAI: {e}"
