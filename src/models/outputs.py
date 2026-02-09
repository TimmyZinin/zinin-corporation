"""
🏢 Zinin Corp — Structured Output Models
Pydantic models for typed agent responses.
Used with CrewAI output_pydantic for structured data extraction.
"""

from pydantic import BaseModel, Field


# ── Financial (Маттиас) ────────────────────────────────────

class FinancialReport(BaseModel):
    """Structured financial report from CFO."""
    summary: str = Field(description="Краткая сводка финансового состояния (2-3 предложения)")
    total_revenue_rub: float = Field(default=0, description="Общий доход в рублях")
    total_expenses_rub: float = Field(default=0, description="Общие расходы в рублях")
    net_profit_rub: float = Field(default=0, description="Чистая прибыль в рублях")
    mrr_rub: float = Field(default=0, description="Ежемесячный повторяющийся доход (MRR)")
    api_costs_usd: float = Field(default=0, description="Расходы на API в долларах")
    crypto_portfolio_usd: float = Field(default=0, description="Криптопортфель в долларах")
    bank_balance_rub: float = Field(default=0, description="Банковский баланс в рублях")
    recommendations: list[str] = Field(default_factory=list, description="Рекомендации (3-5 пунктов)")
    data_sources: list[str] = Field(default_factory=list, description="Какие инструменты/источники были использованы")


class BudgetAlert(BaseModel):
    """Budget alert from CFO when spending exceeds threshold."""
    category: str = Field(description="Категория расхода (API, инфраструктура, подписки)")
    current_spend_usd: float = Field(default=0, description="Текущие расходы USD")
    budget_limit_usd: float = Field(default=0, description="Лимит бюджета USD")
    overspend_percent: float = Field(default=0, description="Превышение в процентах")
    recommendation: str = Field(default="", description="Рекомендация по оптимизации")


# ── Technical (Мартин) ─────────────────────────────────────

class HealthCheckReport(BaseModel):
    """Structured health check from CTO."""
    overall_status: str = Field(description="Общий статус: healthy, degraded, critical")
    services_up: int = Field(default=0, description="Сервисов работает")
    services_down: int = Field(default=0, description="Сервисов не работает")
    services_total: int = Field(default=0, description="Всего сервисов")
    details: list[str] = Field(default_factory=list, description="Детали по каждому сервису")
    errors: list[str] = Field(default_factory=list, description="Текущие ошибки")
    recommendations: list[str] = Field(default_factory=list, description="Рекомендации")


class APIHealthDetail(BaseModel):
    """Health status of a single API."""
    name: str = Field(description="Название API")
    status: str = Field(description="up, down, degraded")
    latency_ms: float = Field(default=0, description="Время отклика в мс")
    error: str = Field(default="", description="Сообщение об ошибке (если есть)")


class TechReport(BaseModel):
    """Full technical report from CTO."""
    overall_status: str = Field(description="healthy, degraded, critical")
    api_health: list[APIHealthDetail] = Field(default_factory=list, description="Статус каждого API")
    active_integrations: int = Field(default=0, description="Активных интеграций")
    errors_count: int = Field(default=0, description="Количество ошибок")
    recommendations: list[str] = Field(default_factory=list, description="Рекомендации")


# ── Content (Юки) ──────────────────────────────────────────

class ContentReport(BaseModel):
    """Content/SMM report from Юки."""
    posts_generated: int = Field(default=0, description="Постов сгенерировано")
    posts_published: int = Field(default=0, description="Постов опубликовано")
    linkedin_status: str = Field(default="unknown", description="Статус LinkedIn: connected, expired, error")
    avg_quality_score: float = Field(default=0, description="Средний score качества (0-1)")
    top_topics: list[str] = Field(default_factory=list, description="Топ-темы контента")
    recommendations: list[str] = Field(default_factory=list, description="Рекомендации")


# ── Product (Софи) ─────────────────────────────────────────

class ProductReport(BaseModel):
    """Product health report from CPO."""
    overall_health: str = Field(description="Общее здоровье продукта: healthy, degraded, critical")
    features_total: int = Field(default=0, description="Всего фич в бэклоге")
    features_done: int = Field(default=0, description="Завершённых фич")
    features_in_progress: int = Field(default=0, description="Фич в работе")
    features_blocked: int = Field(default=0, description="Заблокированных фич")
    current_sprint: str = Field(default="", description="Название текущего спринта")
    sprint_progress_pct: int = Field(default=0, description="Прогресс спринта в %")
    blockers: list[str] = Field(default_factory=list, description="Список блокеров")
    priorities: list[str] = Field(default_factory=list, description="Приоритеты на неделю")
    recommendations: list[str] = Field(default_factory=list, description="Рекомендации CPO")


# ── CEO (Алексей) ──────────────────────────────────────────

class StrategicReviewReport(BaseModel):
    """CEO strategic review output."""
    executive_summary: str = Field(description="Краткое резюме для Тима (3-5 предложений)")
    financial_highlights: list[str] = Field(default_factory=list, description="Ключевые финансовые показатели")
    tech_highlights: list[str] = Field(default_factory=list, description="Ключевые технические показатели")
    content_highlights: list[str] = Field(default_factory=list, description="Ключевые показатели контента")
    priorities: list[str] = Field(default_factory=list, description="Приоритеты на неделю")
    risks: list[str] = Field(default_factory=list, description="Риски и предупреждения")
    action_items: list[str] = Field(default_factory=list, description="Конкретные задачи для агентов")


# ── Universal ──────────────────────────────────────────────

class AgentResponse(BaseModel):
    """Generic structured response for any agent."""
    answer: str = Field(description="Основной ответ на запрос")
    key_facts: list[str] = Field(default_factory=list, description="Ключевые факты и цифры")
    recommendations: list[str] = Field(default_factory=list, description="Рекомендации")
    data_sources: list[str] = Field(default_factory=list, description="Использованные инструменты/источники")


# ── Model registry (agent_name → output model for report tasks) ──

REPORT_OUTPUT_MODELS = {
    "accountant": FinancialReport,
    "automator": HealthCheckReport,
    "smm": ContentReport,
    "cpo": ProductReport,
    "manager": StrategicReviewReport,
}


def get_output_model(agent_name: str, task_type: str = "report"):
    """Get the appropriate output model for an agent and task type.

    Args:
        agent_name: Agent key (manager, accountant, etc.)
        task_type: "report" for structured reports, "chat" for free text.

    Returns:
        Pydantic model class or None (for free-text responses).
    """
    if task_type == "chat":
        return None
    return REPORT_OUTPUT_MODELS.get(agent_name)
