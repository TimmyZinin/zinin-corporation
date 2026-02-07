"""
T-Bank (ex-Tinkoff) — Russian business banking API.

API Docs: https://developer.tbank.ru/docs/api/t-api
Base URL: https://business.tbank.ru/openapi/api/
Auth: Bearer token (from T-Business personal account)

Endpoints (business API):
- GET /accounts — list of business accounts
- GET /bank-statement — account statement for period
- GET /bank-accounts — account balances
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Type

import httpx
from pydantic import BaseModel, Field

from .base import FinancialBaseTool

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# Tool: T-Bank Balance
# ──────────────────────────────────────────────────────────

class TBankBalanceInput(BaseModel):
    account_number: Optional[str] = Field(
        None,
        description=(
            "Specific account number to check. "
            "Leave empty to get all accounts."
        ),
    )


class TBankBalanceTool(FinancialBaseTool):
    name: str = "tbank_balance"
    description: str = (
        "Get current balances of all T-Bank business accounts (RUB, USD, EUR). "
        "Returns: account number, currency, current/available balance. "
        "Russia, main business bank."
    )
    args_schema: Type[BaseModel] = TBankBalanceInput
    service_name: str = "tbank"

    def _run(self, account_number: str = None) -> str:
        return self._safe_run(self._fetch_balance, account_number)

    def _fetch_balance(self, account_number: str = None) -> str:
        creds = self._get_credentials()
        headers = {
            "Authorization": f"Bearer {creds['api_key']}",
            "Accept": "application/json",
        }
        client = httpx.Client(
            base_url=creds["base_url"],
            headers=headers,
            timeout=30.0,
        )
        try:
            response = client.get("/bank-accounts")
            response.raise_for_status()
            data = response.json()
        finally:
            client.close()

        accounts = data if isinstance(data, list) else data.get("accounts", data.get("items", []))

        if account_number:
            accounts = [
                a for a in accounts
                if a.get("accountNumber", a.get("account_number", "")) == account_number
            ]

        if not accounts:
            return "No T-Bank accounts found."

        lines = ["T-BANK BALANCES:"]
        total_rub = Decimal("0")
        for acc in accounts:
            acc_num = acc.get("accountNumber", acc.get("account_number", "N/A"))
            currency = acc.get("currency", "RUB")
            balance = acc.get("balance", acc.get("amount", 0))
            available = acc.get("availableBalance", acc.get("available", balance))
            status = acc.get("status", "active")

            # Mask account number for security (show last 4)
            masked = f"***{acc_num[-4:]}" if len(acc_num) > 4 else acc_num

            lines.append(
                f"  {masked} ({currency}): "
                f"balance {balance:,.2f} / available {available:,.2f} "
                f"[{status}]"
            )
            if currency == "RUB":
                total_rub += Decimal(str(balance))

        if total_rub > 0:
            lines.append(f"  TOTAL RUB: {total_rub:,.2f}")
        return "\n".join(lines)


# ──────────────────────────────────────────────────────────
# Tool: T-Bank Statement
# ──────────────────────────────────────────────────────────

class TBankStatementInput(BaseModel):
    account_number: str = Field(
        ...,
        description="Account number to get statement for.",
    )
    date_from: Optional[str] = Field(
        None,
        description="Start date (YYYY-MM-DD). Default: 30 days ago.",
    )
    date_to: Optional[str] = Field(
        None,
        description="End date (YYYY-MM-DD). Default: today.",
    )


class TBankStatementTool(FinancialBaseTool):
    name: str = "tbank_statement"
    description: str = (
        "Get account statement (transactions) from T-Bank for a date range. "
        "Input: account_number, date_from, date_to. "
        "Returns: list of transactions with amounts, counterparties, purposes."
    )
    args_schema: Type[BaseModel] = TBankStatementInput
    service_name: str = "tbank"

    def _run(
        self,
        account_number: str,
        date_from: str = None,
        date_to: str = None,
    ) -> str:
        return self._safe_run(
            self._fetch_statement, account_number, date_from, date_to
        )

    def _fetch_statement(
        self,
        account_number: str,
        date_from: str,
        date_to: str,
    ) -> str:
        if not date_to:
            date_to = datetime.utcnow().strftime("%Y-%m-%d")
        if not date_from:
            dt = datetime.utcnow() - timedelta(days=30)
            date_from = dt.strftime("%Y-%m-%d")

        creds = self._get_credentials()
        headers = {
            "Authorization": f"Bearer {creds['api_key']}",
            "Accept": "application/json",
        }
        client = httpx.Client(
            base_url=creds["base_url"],
            headers=headers,
            timeout=30.0,
        )
        try:
            params = {
                "accountNumber": account_number,
                "from": date_from,
                "to": date_to,
            }
            response = client.get("/bank-statement", params=params)
            response.raise_for_status()
            data = response.json()
        finally:
            client.close()

        operations = data if isinstance(data, list) else data.get(
            "operations", data.get("transactions", data.get("items", []))
        )

        if not operations:
            return f"No transactions for account {account_number} ({date_from} — {date_to})."

        lines = [f"T-BANK STATEMENT ({date_from} — {date_to}):"]
        total_in = Decimal("0")
        total_out = Decimal("0")

        for op in operations[:50]:  # Limit to 50 for readability
            amount = Decimal(str(op.get("amount", op.get("operationAmount", 0))))
            currency = op.get("currency", "RUB")
            date = op.get("date", op.get("operationDate", "N/A"))
            if isinstance(date, str) and "T" in date:
                date = date[:10]  # Trim to date only
            description = op.get(
                "description",
                op.get("purpose", op.get("paymentPurpose", "N/A")),
            )
            counterparty = op.get(
                "counterparty",
                op.get("counterpartyName", op.get("payerName", "")),
            )

            sign = "+" if amount >= 0 else ""
            if amount >= 0:
                total_in += amount
            else:
                total_out += abs(amount)

            cp_str = f" | {counterparty}" if counterparty else ""
            desc_short = str(description)[:60]
            lines.append(
                f"  {date} | {sign}{amount:,.2f} {currency}{cp_str} | {desc_short}"
            )

        if len(operations) > 50:
            lines.append(f"  ... and {len(operations) - 50} more transactions")

        lines.append(f"\n  SUMMARY: +{total_in:,.2f} / -{total_out:,.2f} = {total_in - total_out:,.2f} RUB")
        return "\n".join(lines)
