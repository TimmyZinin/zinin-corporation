"""Tool for Маттиас to access data extracted from screenshots."""

from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class ScreenshotDataInput(BaseModel):
    source: str = Field(
        "",
        description=(
            "Filter by source: 'TBC Bank', 'Telegram @wallet', "
            "or leave empty for all sources."
        ),
    )


class ScreenshotDataTool(BaseTool):
    name: str = "screenshot_balances"
    description: str = (
        "Get financial data extracted from screenshots sent by Тим via Telegram. "
        "Includes TBC Bank balances, Telegram @wallet crypto balances. "
        "Data is extracted via vision when Тим sends photos."
    )
    args_schema: Type[BaseModel] = ScreenshotDataInput

    def _run(self, source: str = "") -> str:
        try:
            from ...telegram.screenshot_storage import (
                get_latest_balances,
                load_all_screenshots,
            )
        except ImportError:
            return "Screenshot storage module not available."

        latest = get_latest_balances()
        if not latest:
            return (
                "Данных из скриншотов пока нет. "
                "Попроси Тима прислать скриншот банка/кошелька в Telegram."
            )

        lines = ["SCREENSHOT-EXTRACTED BALANCES:"]
        for src, data in latest.items():
            if source and source.lower() not in src.lower():
                continue
            lines.append(f"\n{src} (extracted: {data['extracted_at'][:16]})")
            for acc in data.get("accounts", []):
                name = acc.get("name", "N/A")
                balance = acc.get("balance", "?")
                currency = acc.get("currency", "")
                lines.append(f"  {name}: {balance} {currency}")

        return "\n".join(lines)
