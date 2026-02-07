"""
TBC Bank — Georgian banking API (PSD2 Open Banking).

API Docs: https://developers.tbcbank.ge
Auth: OAuth 2.0 + mTLS (JWS signature)

STATUS: Not connected yet. Requires PSD2/eIDAS certificate.
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
        "Currently not connected — requires PSD2 certificate setup."
    )
    args_schema: Type[BaseModel] = TBCBalanceInput
    service_name: str = "tbc"

    def _run(self, account_id: str = None) -> str:
        return (
            "⚠️ TBC Bank (Georgia) is not connected yet. "
            "Requires PSD2/eIDAS certificate for Open Banking API access. "
            "Contact TBC developers portal: developers.tbcbank.ge"
        )


class TBCStatementInput(BaseModel):
    account_id: str = Field(..., description="Account ID")
    date_from: Optional[str] = Field(None, description="Start date YYYY-MM-DD")
    date_to: Optional[str] = Field(None, description="End date YYYY-MM-DD")


class TBCStatementTool(FinancialBaseTool):
    name: str = "tbc_statement"
    description: str = (
        "Get TBC Bank statement (Georgia). "
        "Currently not connected."
    )
    args_schema: Type[BaseModel] = TBCStatementInput
    service_name: str = "tbc"

    def _run(self, account_id: str, date_from: str = None, date_to: str = None) -> str:
        return (
            "⚠️ TBC Bank (Georgia) is not connected yet. "
            "Requires PSD2/eIDAS certificate."
        )
