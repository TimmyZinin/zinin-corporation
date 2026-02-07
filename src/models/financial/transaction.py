"""
Unified transaction model for all financial sources.

Rules:
- amount: ONLY Decimal. float FORBIDDEN for money.
- Sign: + = income, - = expense (normalize on import)
- timestamp: always UTC
- original_timezone: store separately for tax jurisdictions
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class Source(str, Enum):
    TBANK = "tbank"
    TBC = "tbc"
    VAKIFBANK = "vakifbank"
    KRUNGSRI = "krungsri"
    TRIBUTE = "tribute"
    STRIPE = "stripe"
    MORALIS = "moralis"
    HELIUS = "helius"
    TONAPI = "tonapi"


class Category(str, Enum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"
    TAX = "tax"
    FEE = "fee"
    SWAP = "swap"
    STAKING = "staking_reward"


class UnifiedTransaction(BaseModel):
    """Unified transaction from any financial source."""

    id: UUID = Field(default_factory=uuid4)
    source: Source
    source_id: str  # ID in source system (for deduplication)

    amount: Decimal
    currency: str  # ISO 4217 (USD, RUB, GEL, TRY, THB) or crypto (ETH, SOL, TON)
    amount_usd: Optional[Decimal] = None

    category: Category
    description: Optional[str] = None
    counterparty: Optional[str] = None

    timestamp: datetime  # UTC
    original_timezone: Optional[str] = None

    metadata: dict = Field(default_factory=dict)

    @field_validator("amount", mode="before")
    @classmethod
    def no_float(cls, v):
        if isinstance(v, float):
            raise ValueError(
                "float is forbidden for money. Use Decimal or str."
            )
        return Decimal(str(v))

    @field_validator("currency", mode="before")
    @classmethod
    def uppercase_currency(cls, v):
        return str(v).upper()

    def to_display(self) -> str:
        """Format transaction for agent display."""
        sign = "+" if self.amount >= 0 else ""
        usd_part = ""
        if self.amount_usd is not None:
            usd_sign = "+" if self.amount_usd >= 0 else ""
            usd_part = f" ({usd_sign}{self.amount_usd:.2f} USD)"
        return (
            f"{self.timestamp:%Y-%m-%d %H:%M} | "
            f"{sign}{self.amount:.2f} {self.currency}{usd_part} | "
            f"{self.category.value} | "
            f"{self.description or 'N/A'}"
        )
