"""Telegram bot configuration."""

import os
from dataclasses import dataclass, field


@dataclass
class TelegramConfig:
    bot_token: str = ""
    allowed_user_ids: list[int] = field(default_factory=list)

    # Schedule (UTC hours)
    weekly_summary_day: str = "mon"
    weekly_summary_hour: int = 9
    screenshot_reminder_day: str = "fri"
    screenshot_reminder_hour: int = 10
    anomaly_check_hour: int = 18

    # Agent
    default_agent: str = "accountant"
    max_message_length: int = 4096

    @classmethod
    def from_env(cls) -> "TelegramConfig":
        return cls(
            bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            allowed_user_ids=[
                int(uid.strip())
                for uid in os.getenv("TELEGRAM_ALLOWED_USERS", "").split(",")
                if uid.strip()
            ],
            weekly_summary_hour=int(os.getenv("TG_WEEKLY_SUMMARY_HOUR", "9")),
            screenshot_reminder_hour=int(os.getenv("TG_SCREENSHOT_REMINDER_HOUR", "10")),
            anomaly_check_hour=int(os.getenv("TG_ANOMALY_CHECK_HOUR", "18")),
        )
