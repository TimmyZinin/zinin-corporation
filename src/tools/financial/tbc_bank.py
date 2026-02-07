"""
TBC Bank — Georgian banking (personal account).

API Status: DBI request sent to bank, pending approval.
Current mode: MANUAL — Маттиас asks Тим for screenshots.
"""

from typing import Optional, Type
from pydantic import BaseModel, Field
from .base import FinancialBaseTool


class TBCBalanceInput(BaseModel):
    account_id: Optional[str] = Field(None, description="Account ID")


class TBCBalanceTool(FinancialBaseTool):
    name: str = "tbc_balance"
    description: str = (
        "Get TBC Bank account balances (Georgia, GEL/USD). "
        "Currently manual mode — ask Тим for a screenshot."
    )
    args_schema: Type[BaseModel] = TBCBalanceInput
    service_name: str = "tbc"

    def _run(self, account_id: str = None) -> str:
        return (
            "⚠️ TBC Bank (Грузия) — API пока не подключён (DBI запрос отправлен в банк).\n"
            "ДЕЙСТВИЕ: Попроси Тима прислать скриншот баланса из TBC Online.\n"
            "Формат: «Тим, для финансового отчёта мне нужен актуальный баланс TBC Bank. "
            "Пришли, пожалуйста, скриншот из интернет-банка.»\n"
            "После получения скриншота — распознай данные и включи в отчёт."
        )


class TBCStatementInput(BaseModel):
    account_id: str = Field(..., description="Account ID")
    date_from: Optional[str] = Field(None, description="Start date YYYY-MM-DD")
    date_to: Optional[str] = Field(None, description="End date YYYY-MM-DD")


class TBCStatementTool(FinancialBaseTool):
    name: str = "tbc_statement"
    description: str = (
        "Get TBC Bank statement (Georgia). "
        "Currently manual mode — ask Тим for screenshots."
    )
    args_schema: Type[BaseModel] = TBCStatementInput
    service_name: str = "tbc"

    def _run(self, account_id: str, date_from: str = None, date_to: str = None) -> str:
        return (
            "⚠️ TBC Bank выписка — API пока не подключён.\n"
            "ДЕЙСТВИЕ: Попроси Тима прислать скриншот выписки из TBC Online "
            f"за период {date_from or '...'} — {date_to or 'сегодня'}.\n"
            "После получения — распознай транзакции и включи в анализ."
        )
