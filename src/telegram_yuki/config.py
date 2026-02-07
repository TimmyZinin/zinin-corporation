"""Yuki SMM Telegram bot configuration."""

import os
from dataclasses import dataclass, field


@dataclass
class YukiTelegramConfig:
    bot_token: str = ""
    allowed_user_ids: list[int] = field(default_factory=list)
    default_agent: str = "smm"
    team_chat_id: int = 0
    content_hour: int = 10  # UTC, daily content reminder

    @classmethod
    def from_env(cls) -> "YukiTelegramConfig":
        return cls(
            bot_token=os.getenv("TELEGRAM_YUKI_BOT_TOKEN", ""),
            allowed_user_ids=[
                int(uid.strip())
                for uid in os.getenv("TELEGRAM_YUKI_ALLOWED_USERS", "").split(",")
                if uid.strip()
            ],
            team_chat_id=int(os.getenv("TELEGRAM_YUKI_TEAM_CHAT_ID", "0")),
            content_hour=int(os.getenv("TG_YUKI_CONTENT_HOUR", "10")),
        )
