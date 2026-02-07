"""
Stripe — Payment processing.

API Docs: https://stripe.com/docs/api
Auth: Secret Key (Bearer)

STATUS: Not connected. Integration planned for future.
"""

from typing import Optional, Type
from pydantic import BaseModel, Field
from .base import FinancialBaseTool


class StripeRevenueInput(BaseModel):
    action: str = Field(
        default="balance",
        description="Action: balance, transactions, payouts",
    )
    date_from: Optional[str] = Field(None, description="Start date YYYY-MM-DD")
    date_to: Optional[str] = Field(None, description="End date YYYY-MM-DD")


class StripeRevenueTool(FinancialBaseTool):
    name: str = "stripe_revenue"
    description: str = (
        "Get Stripe payment data: balance, transactions, payouts. "
        "Currently not connected."
    )
    args_schema: Type[BaseModel] = StripeRevenueInput
    service_name: str = "stripe"

    def _run(self, action: str = "balance", date_from: str = None, date_to: str = None) -> str:
        return (
            "⚠️ Stripe is not connected yet. "
            "Integration is planned for a future update."
        )
