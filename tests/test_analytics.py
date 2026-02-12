"""Tests for Analytics module — aggregated reports."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from src.analytics import (
    COST_PER_REQUEST,
    get_token_usage_report,
    get_agent_activity_report,
    get_cost_estimates,
    get_alert_summary,
    get_quality_report,
    format_analytics_report,
    format_weekly_digest,
)


# ──────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────

def _mock_all_usage(calls_per_provider=10, failed=1, latency=50):
    return {
        "openrouter": {
            "provider": "openrouter",
            "total_calls": calls_per_provider,
            "success": calls_per_provider - failed,
            "failed": failed,
            "avg_latency_ms": latency,
        },
        "elevenlabs": {
            "provider": "elevenlabs",
            "total_calls": 0, "success": 0, "failed": 0, "avg_latency_ms": 0,
        },
        "openai": {
            "provider": "openai",
            "total_calls": calls_per_provider // 2,
            "success": calls_per_provider // 2,
            "failed": 0,
            "avg_latency_ms": latency,
        },
        "coingecko": {
            "provider": "coingecko",
            "total_calls": 0, "success": 0, "failed": 0, "avg_latency_ms": 0,
        },
        "groq": {
            "provider": "groq",
            "total_calls": calls_per_provider * 2,
            "success": calls_per_provider * 2,
            "failed": 0,
            "avg_latency_ms": latency // 2,
        },
    }


def _mock_events(count=5):
    events = []
    for i in range(count):
        events.append({
            "type": "task_end",
            "agent": "manager" if i % 2 == 0 else "accountant",
            "success": True,
            "duration_sec": 30 + i * 10,
            "timestamp": datetime.now().isoformat(),
        })
    events.append({
        "type": "delegation",
        "from_agent": "manager",
        "to_agent": "smm",
        "timestamp": datetime.now().isoformat(),
    })
    events.append({
        "type": "communication",
        "from_agent": "accountant",
        "to_agent": "automator",
        "timestamp": datetime.now().isoformat(),
    })
    return events


def _mock_statuses():
    return {
        "manager": {"status": "working", "queued_tasks": 0},
        "accountant": {"status": "idle", "queued_tasks": 1},
        "smm": {"status": "idle", "queued_tasks": 0},
        "automator": {"status": "idle", "queued_tasks": 0},
        "designer": {"status": "idle", "queued_tasks": 0},
        "cpo": {"status": "idle", "queued_tasks": 0},
    }


def _mock_quality():
    return {
        "count": 10,
        "avg": 0.85,
        "passed_pct": 80,
        "by_agent": {"manager": 0.90, "accountant": 0.80},
    }


# ──────────────────────────────────────────────────────────
# Cost estimates config
# ──────────────────────────────────────────────────────────

class TestCostConfig:
    def test_has_all_providers(self):
        assert "openrouter" in COST_PER_REQUEST
        assert "groq" in COST_PER_REQUEST
        assert "coingecko" in COST_PER_REQUEST

    def test_groq_is_free(self):
        assert COST_PER_REQUEST["groq"] == 0.0

    def test_coingecko_is_free(self):
        assert COST_PER_REQUEST["coingecko"] == 0.0


# ──────────────────────────────────────────────────────────
# Token usage report
# ──────────────────────────────────────────────────────────

class TestTokenUsageReport:
    @patch("src.analytics.get_all_usage")
    def test_with_data(self, mock_usage):
        mock_usage.return_value = _mock_all_usage(10)
        report = get_token_usage_report(24)
        assert "API вызовы" in report
        assert "24ч" in report
        assert "OpenRouter" in report

    @patch("src.analytics.get_all_usage")
    def test_no_data(self, mock_usage):
        mock_usage.return_value = _mock_all_usage(0, 0, 0)
        report = get_token_usage_report(24)
        assert "Нет API-вызовов" in report

    @patch("src.analytics.get_all_usage")
    def test_shows_failures(self, mock_usage):
        mock_usage.return_value = _mock_all_usage(10, 3)
        report = get_token_usage_report(24)
        assert "❌" in report

    @patch("src.analytics.get_all_usage")
    def test_shows_total(self, mock_usage):
        mock_usage.return_value = _mock_all_usage(10)
        report = get_token_usage_report(24)
        assert "Итого" in report

    @patch("src.analytics.get_all_usage")
    def test_custom_hours(self, mock_usage):
        mock_usage.return_value = _mock_all_usage(5)
        report = get_token_usage_report(12)
        assert "12ч" in report


# ──────────────────────────────────────────────────────────
# Agent activity report
# ──────────────────────────────────────────────────────────

class TestAgentActivityReport:
    @patch("src.analytics.get_all_statuses")
    @patch("src.analytics.get_recent_events")
    def test_basic(self, mock_events, mock_statuses):
        mock_events.return_value = _mock_events()
        mock_statuses.return_value = _mock_statuses()
        report = get_agent_activity_report(24)
        assert "Активность агентов" in report
        assert "Алексей" in report

    @patch("src.analytics.get_all_statuses")
    @patch("src.analytics.get_recent_events")
    def test_shows_tasks(self, mock_events, mock_statuses):
        mock_events.return_value = _mock_events(6)
        mock_statuses.return_value = _mock_statuses()
        report = get_agent_activity_report(24)
        assert "✅" in report

    @patch("src.analytics.get_all_statuses")
    @patch("src.analytics.get_recent_events")
    def test_shows_communications(self, mock_events, mock_statuses):
        mock_events.return_value = _mock_events()
        mock_statuses.return_value = _mock_statuses()
        report = get_agent_activity_report(24)
        assert "Коммуникаций" in report

    @patch("src.analytics.get_all_statuses")
    @patch("src.analytics.get_recent_events")
    def test_shows_delegations(self, mock_events, mock_statuses):
        mock_events.return_value = _mock_events()
        mock_statuses.return_value = _mock_statuses()
        report = get_agent_activity_report(24)
        assert "📨" in report


# ──────────────────────────────────────────────────────────
# Cost estimates
# ──────────────────────────────────────────────────────────

class TestCostEstimates:
    @patch("src.analytics.get_all_usage")
    def test_basic(self, mock_usage):
        mock_usage.return_value = _mock_all_usage(100)
        report = get_cost_estimates(24)
        assert "Оценка расходов" in report
        assert "$" in report

    @patch("src.analytics.get_all_usage")
    def test_shows_total(self, mock_usage):
        mock_usage.return_value = _mock_all_usage(100)
        report = get_cost_estimates(24)
        assert "Итого" in report

    @patch("src.analytics.get_all_usage")
    def test_free_providers_not_shown(self, mock_usage):
        usage = _mock_all_usage(0)
        usage["groq"]["total_calls"] = 100
        mock_usage.return_value = usage
        report = get_cost_estimates(24)
        # Groq is free, cost is $0 so line should not appear
        assert "Groq" not in report


# ──────────────────────────────────────────────────────────
# Alert summary
# ──────────────────────────────────────────────────────────

class TestAlertSummary:
    @patch("src.analytics.get_rate_alerts")
    def test_no_alerts(self, mock_alerts):
        mock_alerts.return_value = []
        report = get_alert_summary(24)
        assert "Нет алертов" in report

    @patch("src.analytics.get_rate_alerts")
    def test_with_alerts(self, mock_alerts):
        alert = MagicMock()
        alert.provider = "openrouter"
        alert.pct = 85.0
        alert.window = "minute"
        mock_alerts.return_value = [alert]
        report = get_alert_summary(24)
        assert "Алерты" in report
        assert "85%" in report


# ──────────────────────────────────────────────────────────
# Quality report
# ──────────────────────────────────────────────────────────

class TestQualityReport:
    @patch("src.analytics.get_quality_summary")
    def test_no_data(self, mock_quality):
        mock_quality.return_value = {"count": 0, "avg": 0.0, "passed_pct": 0, "by_agent": {}}
        report = get_quality_report()
        assert "Нет данных" in report

    @patch("src.analytics.get_quality_summary")
    def test_with_data(self, mock_quality):
        mock_quality.return_value = _mock_quality()
        report = get_quality_report()
        assert "Качество" in report
        assert "0.85" in report
        assert "80%" in report

    @patch("src.analytics.get_quality_summary")
    def test_shows_agents(self, mock_quality):
        mock_quality.return_value = _mock_quality()
        report = get_quality_report()
        assert "По агентам" in report


# ──────────────────────────────────────────────────────────
# Full analytics report
# ──────────────────────────────────────────────────────────

class TestFormatAnalyticsReport:
    @patch("src.analytics.get_quality_summary")
    @patch("src.analytics.get_rate_alerts")
    @patch("src.analytics.get_all_statuses")
    @patch("src.analytics.get_recent_events")
    @patch("src.analytics.get_all_usage")
    def test_contains_all_sections(self, mock_usage, mock_events, mock_statuses,
                                    mock_alerts, mock_quality):
        mock_usage.return_value = _mock_all_usage(10)
        mock_events.return_value = _mock_events()
        mock_statuses.return_value = _mock_statuses()
        mock_alerts.return_value = []
        mock_quality.return_value = _mock_quality()

        report = format_analytics_report(24)
        assert "Аналитика Zinin Corp" in report
        assert "API вызовы" in report
        assert "Активность агентов" in report
        assert "Оценка расходов" in report
        assert "Качество" in report

    @patch("src.analytics.get_quality_summary")
    @patch("src.analytics.get_rate_alerts")
    @patch("src.analytics.get_all_statuses")
    @patch("src.analytics.get_recent_events")
    @patch("src.analytics.get_all_usage")
    def test_has_timestamp(self, mock_usage, mock_events, mock_statuses,
                            mock_alerts, mock_quality):
        mock_usage.return_value = _mock_all_usage(0, 0, 0)
        mock_events.return_value = []
        mock_statuses.return_value = _mock_statuses()
        mock_alerts.return_value = []
        mock_quality.return_value = {"count": 0, "avg": 0.0, "passed_pct": 0, "by_agent": {}}

        report = format_analytics_report(24)
        assert "🕐" in report

    @patch("src.analytics.get_quality_summary")
    @patch("src.analytics.get_rate_alerts")
    @patch("src.analytics.get_all_statuses")
    @patch("src.analytics.get_recent_events")
    @patch("src.analytics.get_all_usage")
    def test_custom_hours(self, mock_usage, mock_events, mock_statuses,
                           mock_alerts, mock_quality):
        mock_usage.return_value = _mock_all_usage(5)
        mock_events.return_value = []
        mock_statuses.return_value = _mock_statuses()
        mock_alerts.return_value = []
        mock_quality.return_value = {"count": 0, "avg": 0.0, "passed_pct": 0, "by_agent": {}}

        report = format_analytics_report(12)
        assert "12ч" in report


# ──────────────────────────────────────────────────────────
# Weekly digest
# ──────────────────────────────────────────────────────────

class TestFormatWeeklyDigest:
    @patch("src.analytics.get_quality_summary")
    @patch("src.analytics.get_rate_alerts")
    @patch("src.analytics.get_all_usage")
    @patch("src.analytics.get_recent_events")
    def test_basic_structure(self, mock_events, mock_usage, mock_alerts, mock_quality):
        mock_events.return_value = _mock_events(3)
        mock_usage.return_value = _mock_all_usage(50)
        mock_alerts.return_value = []
        mock_quality.return_value = _mock_quality()

        with patch("src.task_pool.get_all_tasks", return_value=[]), \
             patch("src.task_pool.get_archive_stats", return_value={"total_archived": 15}):
            digest = format_weekly_digest()

        assert "Еженедельный дайджест" in digest
        assert "Задачи" in digest
        assert "Task Pool" in digest
        assert "API" in digest

    @patch("src.analytics.get_quality_summary")
    @patch("src.analytics.get_rate_alerts")
    @patch("src.analytics.get_all_usage")
    @patch("src.analytics.get_recent_events")
    def test_shows_agent_stats(self, mock_events, mock_usage, mock_alerts, mock_quality):
        mock_events.return_value = _mock_events(6)
        mock_usage.return_value = _mock_all_usage(50)
        mock_alerts.return_value = []
        mock_quality.return_value = _mock_quality()

        with patch("src.task_pool.get_all_tasks", return_value=[]), \
             patch("src.task_pool.get_archive_stats", return_value={"total_archived": 0}):
            digest = format_weekly_digest()

        assert "Агенты" in digest

    @patch("src.analytics.get_quality_summary")
    @patch("src.analytics.get_rate_alerts")
    @patch("src.analytics.get_all_usage")
    @patch("src.analytics.get_recent_events")
    def test_shows_quality(self, mock_events, mock_usage, mock_alerts, mock_quality):
        mock_events.return_value = []
        mock_usage.return_value = _mock_all_usage(0, 0, 0)
        mock_alerts.return_value = []
        mock_quality.return_value = _mock_quality()

        with patch("src.task_pool.get_all_tasks", return_value=[]), \
             patch("src.task_pool.get_archive_stats", return_value={"total_archived": 0}):
            digest = format_weekly_digest()

        assert "Качество" in digest
        assert "0.85" in digest

    @patch("src.analytics.get_quality_summary")
    @patch("src.analytics.get_rate_alerts")
    @patch("src.analytics.get_all_usage")
    @patch("src.analytics.get_recent_events")
    def test_task_pool_import_failure(self, mock_events, mock_usage, mock_alerts, mock_quality):
        """Digest should work even if task_pool import fails."""
        mock_events.return_value = []
        mock_usage.return_value = _mock_all_usage(0, 0, 0)
        mock_alerts.return_value = []
        mock_quality.return_value = {"count": 0, "avg": 0.0, "passed_pct": 0, "by_agent": {}}

        with patch("src.task_pool.get_all_tasks", side_effect=Exception("no module")):
            digest = format_weekly_digest()

        assert "Еженедельный дайджест" in digest
        assert "TODO: 0" in digest

    @patch("src.analytics.get_quality_summary")
    @patch("src.analytics.get_rate_alerts")
    @patch("src.analytics.get_all_usage")
    @patch("src.analytics.get_recent_events")
    def test_has_timestamp(self, mock_events, mock_usage, mock_alerts, mock_quality):
        mock_events.return_value = []
        mock_usage.return_value = _mock_all_usage(0, 0, 0)
        mock_alerts.return_value = []
        mock_quality.return_value = {"count": 0, "avg": 0.0, "passed_pct": 0, "by_agent": {}}

        with patch("src.task_pool.get_all_tasks", return_value=[]), \
             patch("src.task_pool.get_archive_stats", return_value={"total_archived": 0}):
            digest = format_weekly_digest()

        assert "🕐" in digest
