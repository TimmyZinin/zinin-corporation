"""
Krungsri — Thai banking API.

API Docs: https://developers.krungsri.com
Auth: OAuth 2.0

STATUS: Not connected yet. Requires API portal registration.
"""

from typing import Optional, Type
from pydantic import BaseModel, Field
from .base import FinancialBaseTool


class KrungsriBalanceInput(BaseModel):
    account_id: Optional[str] = Field(None, description="Account ID")


class KrungsriBalanceTool(FinancialBaseTool):
    name: str = "krungsri_balance"
    description: str = (
        "Get Krungsri account balances (Thailand, THB). "
        "Currently not connected."
    )
    args_schema: Type[BaseModel] = KrungsriBalanceInput
    service_name: str = "krungsri"

    def _run(self, account_id: str = None) -> str:
        return (
            "⚠️ Krungsri (Thailand) is not connected yet. "
            "Requires API portal registration: developers.krungsri.com"
        )


class KrungsriStatementInput(BaseModel):
    account_id: str = Field(..., description="Account ID")
    date_from: Optional[str] = Field(None, description="Start date YYYY-MM-DD")
    date_to: Optional[str] = Field(None, description="End date YYYY-MM-DD")


class KrungsriStatementTool(FinancialBaseTool):
    name: str = "krungsri_statement"
    description: str = "Get Krungsri statement (Thailand). Currently not connected."
    args_schema: Type[BaseModel] = KrungsriStatementInput
    service_name: str = "krungsri"

    def _run(self, account_id: str, date_from: str = None, date_to: str = None) -> str:
        return "⚠️ Krungsri (Thailand) is not connected yet."
