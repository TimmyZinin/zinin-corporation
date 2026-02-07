"""CrewAI Tool: Real-time OpenRouter API usage and cost tracking."""

import json
import logging
import os

import httpx
from crewai.tools import BaseTool

logger = logging.getLogger(__name__)

OPENROUTER_API = "https://openrouter.ai/api/v1"


def _get_headers() -> dict:
    """Get auth headers for OpenRouter API."""
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise EnvironmentError("OPENROUTER_API_KEY not set")
    return {"Authorization": f"Bearer {key}"}


def get_openrouter_usage() -> dict:
    """Fetch real usage data from OpenRouter API."""
    headers = _get_headers()

    # Get key info (usage stats)
    key_resp = httpx.get(f"{OPENROUTER_API}/auth/key", headers=headers, timeout=15)
    key_resp.raise_for_status()
    key_data = key_resp.json().get("data", {})

    # Get credits balance
    credits_resp = httpx.get(f"{OPENROUTER_API}/credits", headers=headers, timeout=15)
    credits_resp.raise_for_status()
    credits_data = credits_resp.json().get("data", {})

    total_credits = credits_data.get("total_credits", 0)
    total_usage = credits_data.get("total_usage", 0)
    remaining = total_credits - total_usage

    return {
        "total_credits_usd": total_credits,
        "total_usage_usd": round(total_usage, 4),
        "remaining_usd": round(remaining, 4),
        "usage_today_usd": round(key_data.get("usage_daily", 0), 4),
        "usage_week_usd": round(key_data.get("usage_weekly", 0), 4),
        "usage_month_usd": round(key_data.get("usage_monthly", 0), 4),
        "byok_usage_usd": round(key_data.get("byok_usage", 0), 4),
        "is_free_tier": key_data.get("is_free_tier", False),
        "limit_usd": key_data.get("limit"),
        "limit_remaining_usd": key_data.get("limit_remaining"),
    }


class OpenRouterUsageTool(BaseTool):
    name: str = "OpenRouter API Usage"
    description: str = (
        "Реальные расходы на AI API через OpenRouter.\n"
        "Показывает: потрачено сегодня/за неделю/за месяц, остаток кредитов.\n"
        "Не требует параметров — вызови для получения актуальных данных."
    )

    def _run(self, argument: str = "") -> str:
        try:
            data = get_openrouter_usage()

            lines = [
                "OpenRouter API — расходы на AI:",
                "",
                f"Кредиты: ${data['total_credits_usd']:.2f}",
                f"Потрачено: ${data['total_usage_usd']:.4f}",
                f"Остаток: ${data['remaining_usd']:.4f}",
                "",
                f"Сегодня: ${data['usage_today_usd']:.4f}",
                f"За неделю: ${data['usage_week_usd']:.4f}",
                f"За месяц: ${data['usage_month_usd']:.4f}",
            ]

            if data["byok_usage_usd"] > 0:
                lines.append(f"BYOK (свой ключ): ${data['byok_usage_usd']:.4f}")

            if data.get("limit_usd"):
                lines.append(f"Лимит: ${data['limit_usd']:.2f}")
                if data.get("limit_remaining_usd"):
                    lines.append(f"Лимит остаток: ${data['limit_remaining_usd']:.2f}")

            # Budget alert
            pct_used = (data["total_usage_usd"] / data["total_credits_usd"] * 100) if data["total_credits_usd"] > 0 else 0
            if pct_used > 80:
                lines.append(f"\nВНИМАНИЕ: Израсходовано {pct_used:.0f}% кредитов!")
            elif pct_used > 50:
                lines.append(f"\nИзрасходовано {pct_used:.0f}% кредитов.")

            return "\n".join(lines)

        except EnvironmentError:
            return "OPENROUTER_API_KEY не настроен. Невозможно получить данные о расходах."
        except Exception as e:
            logger.error(f"OpenRouter usage fetch failed: {e}")
            return f"Ошибка при получении данных OpenRouter: {e}"
