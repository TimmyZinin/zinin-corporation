"""CrewAI Tool: Tinkoff bank transaction data from CSV statements."""

import json
from crewai.tools import BaseTool


class TinkoffDataTool(BaseTool):
    name: str = "Tinkoff Bank Data"
    description: str = (
        "Данные банковских операций Т-Банка (Тинькофф) из CSV-выписок.\n"
        "Действия (action):\n"
        "- summary: Общая сводка (доходы, расходы, топ категорий, по месяцам)\n"
        "- recent: Последние N операций (параметр limit, по умолчанию 20)\n"
        "- category: Операции по категории (параметр category, например 'Супермаркеты')\n"
        "- search: Поиск по описанию (параметр query)\n"
        "Формат: action=summary или action=recent&limit=20 или action=category&category=ЖКХ"
    )

    def _run(self, argument: str = "action=summary") -> str:
        from src.telegram.transaction_storage import get_summary, load_transactions

        params = _parse_params(argument)
        action = params.get("action", "summary")

        if action == "summary":
            summary = get_summary()
            if not summary:
                return "Нет данных по Т-Банку. Тим ещё не присылал CSV-выписку."
            return json.dumps(summary, ensure_ascii=False, indent=2, default=str)

        elif action == "recent":
            limit = int(params.get("limit", "20"))
            txs = load_transactions(limit=limit)
            if not txs:
                return "Нет данных по Т-Банку."
            return json.dumps(txs, ensure_ascii=False, indent=2)

        elif action == "category":
            cat = params.get("category", "")
            if not cat:
                return "Укажи категорию: action=category&category=Супермаркеты"
            txs = load_transactions(limit=100, category=cat)
            total = sum(abs(t["amount"]) for t in txs)
            return (
                f"Категория '{cat}': {len(txs)} операций на {total:,.2f} RUB\n"
                + json.dumps(txs[:20], ensure_ascii=False, indent=2)
            )

        elif action == "search":
            query = params.get("query", "").lower()
            if not query:
                return "Укажи запрос: action=search&query=Яндекс"
            txs = load_transactions(limit=500)
            matched = [t for t in txs if query in t.get("description", "").lower()]
            total = sum(abs(t["amount"]) for t in matched)
            return (
                f"Поиск '{query}': {len(matched)} операций на {total:,.2f} RUB\n"
                + json.dumps(matched[:20], ensure_ascii=False, indent=2)
            )

        return f"Неизвестное действие: {action}. Используй: summary, recent, category, search."


def _parse_params(argument: str) -> dict:
    """Parse 'action=summary&limit=20' into dict."""
    params = {}
    for part in argument.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            params[k.strip()] = v.strip()
        else:
            params["action"] = part.strip()
    return params
