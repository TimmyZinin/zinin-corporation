"""CrewAI Tool: ElevenLabs usage tracking (characters, subscription tier)."""

import logging
import os
from datetime import datetime

import httpx
from crewai.tools import BaseTool

logger = logging.getLogger(__name__)

ELEVENLABS_API = "https://api.elevenlabs.io/v1"


def _get_headers() -> dict:
    key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not key:
        raise EnvironmentError("ELEVENLABS_API_KEY not set")
    return {"xi-api-key": key}


def get_elevenlabs_usage() -> dict:
    """Fetch subscription and usage data from ElevenLabs API."""
    headers = _get_headers()

    resp = httpx.get(f"{ELEVENLABS_API}/user/subscription", headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    char_count = data.get("character_count", 0)
    char_limit = data.get("character_limit", 0)
    remaining = char_limit - char_count
    reset_unix = data.get("next_character_count_reset_unix", 0)
    reset_date = datetime.fromtimestamp(reset_unix).strftime("%d.%m.%Y") if reset_unix else "N/A"

    # Next invoice info
    next_invoice = data.get("next_invoice", {})
    next_payment_cents = next_invoice.get("amount_due_cents", 0)

    return {
        "tier": data.get("tier", "unknown"),
        "status": data.get("status", "unknown"),
        "characters_used": char_count,
        "characters_limit": char_limit,
        "characters_remaining": remaining,
        "usage_pct": round(char_count / char_limit * 100, 1) if char_limit > 0 else 0,
        "reset_date": reset_date,
        "next_payment_usd": round(next_payment_cents / 100, 2) if next_payment_cents else 0,
        "currency": data.get("currency", "usd"),
    }


class ElevenLabsUsageTool(BaseTool):
    name: str = "ElevenLabs Usage"
    description: str = (
        "Расходы и лимиты ElevenLabs (генерация голоса).\n"
        "Показывает: символы использовано/лимит, тариф, дата сброса.\n"
        "Не требует параметров."
    )

    def _run(self, argument: str = "") -> str:
        try:
            data = get_elevenlabs_usage()

            lines = [
                "ElevenLabs — генерация голоса:",
                "",
                f"Тариф: {data['tier']} ({data['status']})",
                f"Символов: {data['characters_used']:,} / {data['characters_limit']:,}",
                f"Осталось: {data['characters_remaining']:,} ({100 - data['usage_pct']:.0f}%)",
                f"Сброс лимита: {data['reset_date']}",
            ]

            if data["next_payment_usd"] > 0:
                lines.append(f"Следующий платёж: ${data['next_payment_usd']:.2f}")

            if data["usage_pct"] > 80:
                lines.append(f"\nВНИМАНИЕ: Израсходовано {data['usage_pct']:.0f}% символов!")
            elif data["usage_pct"] > 50:
                lines.append(f"\nИзрасходовано {data['usage_pct']:.0f}% символов.")

            return "\n".join(lines)

        except EnvironmentError:
            return "ELEVENLABS_API_KEY не настроен."
        except Exception as e:
            logger.error(f"ElevenLabs usage fetch failed: {e}")
            return f"Ошибка ElevenLabs: {e}"
