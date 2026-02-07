"""
Vakıfbank — Turkish banking API.

API Docs: https://apiportal.vakifbank.com.tr
Auth: API Key + mTLS

STATUS: Not connected yet. Requires API portal registration.
"""

from typing import Optional, Type
from pydantic import BaseModel, Field
from .base import FinancialBaseTool


class VakifbankBalanceInput(BaseModel):
    account_id: Optional[str] = Field(None, description="Account ID")


class VakifbankBalanceTool(FinancialBaseTool):
    name: str = "vakifbank_balance"
    description: str = (
        "Get Vakıfbank account balances (Turkey, TRY). "
        "Currently not connected."
    )
    args_schema: Type[BaseModel] = VakifbankBalanceInput
    service_name: str = "vakifbank"

    def _run(self, account_id: str = None) -> str:
        return (
            "⚠️ Vakıfbank (Turkey) is not connected yet. "
            "Requires API portal registration: apiportal.vakifbank.com.tr"
        )


class VakifbankStatementInput(BaseModel):
    account_id: str = Field(..., description="Account ID")
    date_from: Optional[str] = Field(None, description="Start date YYYY-MM-DD")
    date_to: Optional[str] = Field(None, description="End date YYYY-MM-DD")


class VakifbankStatementTool(FinancialBaseTool):
    name: str = "vakifbank_statement"
    description: str = "Get Vakıfbank statement (Turkey). Currently not connected."
    args_schema: Type[BaseModel] = VakifbankStatementInput
    service_name: str = "vakifbank"

    def _run(self, account_id: str, date_from: str = None, date_to: str = None) -> str:
        return "⚠️ Vakıfbank (Turkey) is not connected yet."
