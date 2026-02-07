"""CEO Telegram bot configuration."""

import os
from dataclasses import dataclass, field


@dataclass
class CeoTelegramConfig:
    bot_token: str = ""
    allowed_user_ids: list[int] = field(default_factory=list)
    default_agent: str = "manager"
    morning_briefing_hour: int = 8  # UTC
    weekly_review_day: str = "mon"
    weekly_review_hour: int = 10  # UTC

    @classmethod
    def from_env(cls) -> "CeoTelegramConfig":
        return cls(
            bot_token=os.getenv("TELEGRAM_CEO_BOT_TOKEN", ""),
            allowed_user_ids=[
                int(uid.strip())
                for uid in os.getenv("TELEGRAM_CEO_ALLOWED_USERS", "").split(",")
                if uid.strip()
            ],
            morning_briefing_hour=int(os.getenv("TG_CEO_MORNING_HOUR", "8")),
            weekly_review_hour=int(os.getenv("TG_CEO_WEEKLY_HOUR", "10")),
        )
