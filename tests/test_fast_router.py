"""Tests for src/telegram_ceo/fast_router.py — Fast Router (0 LLM routing)."""

import pytest

from src.telegram_ceo.fast_router import (
    route_message,
    RouteResult,
    INTENT_CONFIDENCE_THRESHOLD,
    AGENT_CONFIDENCE_THRESHOLD,
)


class TestRouteMessageIntent:
    """Intent detection routes (priority 1)."""

    def test_status_intent(self):
        result = route_message("статус")
        assert result.route_type == "intent"
        assert result.intent_command == "/status"
        assert result.confidence >= INTENT_CONFIDENCE_THRESHOLD

    def test_help_intent(self):
        result = route_message("помощь")
        assert result.route_type == "intent"
        assert result.intent_command == "/help"

    def test_tasks_intent(self):
        result = route_message("задачи")
        assert result.route_type == "intent"
        assert result.intent_command == "/tasks"

    def test_balance_intent(self):
        result = route_message("баланс")
        assert result.route_type == "intent"
        assert result.intent_command == "/balance"

    def test_analytics_intent(self):
        result = route_message("аналитика")
        assert result.route_type == "intent"
        assert result.intent_command == "/analytics"

    def test_review_intent(self):
        result = route_message("стратегический обзор")
        assert result.route_type == "intent"
        assert result.intent_command == "/review"

    def test_report_intent(self):
        result = route_message("отчёт")
        assert result.route_type == "intent"
        assert result.intent_command == "/report"

    def test_content_intent(self):
        result = route_message("напиши пост")
        assert result.route_type == "intent"
        assert result.intent_command == "/content"

    def test_linkedin_intent(self):
        result = route_message("linkedin статус")
        assert result.route_type == "intent"
        assert result.intent_command == "/linkedin"


class TestRouteMessageAgent:
    """Agent detection routes (priority 2)."""

    def test_yuki_by_name(self):
        result = route_message("юки напиши пост про AI")
        # Could be intent (/content) or agent (smm) — both valid
        assert result.route_type in ("intent", "agent")
        if result.route_type == "agent":
            assert result.agent_name == "smm"

    def test_mattias_by_name(self):
        result = route_message("маттиас проверь портфель")
        assert result.route_type in ("intent", "agent")
        if result.route_type == "agent":
            assert result.agent_name == "accountant"

    def test_martin_by_name(self):
        result = route_message("мартин проверь API")
        assert result.route_type in ("intent", "agent")
        if result.route_type == "agent":
            assert result.agent_name == "automator"

    def test_ryan_by_name(self):
        result = route_message("райан создай картинку")
        assert result.route_type == "agent"
        assert result.agent_name == "designer"

    def test_sophie_by_name(self):
        result = route_message("софи покажи спринт")
        assert result.route_type == "agent"
        assert result.agent_name == "cpo"

    def test_agent_by_topic_finance(self):
        result = route_message("проверь бюджет и выручку за квартал")
        assert result.route_type == "agent"
        assert result.agent_name == "accountant"

    def test_agent_by_topic_design(self):
        result = route_message("нужна инфографика для LinkedIn")
        assert result.route_type in ("intent", "agent")  # could match /content or designer

    def test_agent_by_topic_server(self):
        result = route_message("сервер не отвечает деплой упал")
        assert result.route_type == "agent"
        assert result.agent_name == "automator"


class TestRouteMessageFallback:
    """Fallback routes (priority 3)."""

    def test_generic_text_fallback(self):
        result = route_message("расскажи мне что-нибудь интересное")
        assert result.route_type == "fallback"
        assert result.agent_name == "manager"
        assert result.confidence == 0.0

    def test_short_text_fallback(self):
        result = route_message("ок")
        assert result.route_type == "fallback"
        assert result.agent_name == "manager"

    def test_empty_like_text_fallback(self):
        result = route_message("хм")
        assert result.route_type == "fallback"
        assert result.agent_name == "manager"


class TestRouteMessagePriority:
    """Intent takes priority over agent detection."""

    def test_intent_over_agent(self):
        # "помощь" matches /help intent AND could match agent
        result = route_message("помощь")
        assert result.route_type == "intent"
        assert result.intent_command == "/help"

    def test_status_over_agent(self):
        result = route_message("статус")
        assert result.route_type == "intent"
        assert result.intent_command == "/status"


class TestRouteResultDataclass:
    """RouteResult structure tests."""

    def test_intent_result_has_command(self):
        result = route_message("статус")
        assert result.intent_command is not None

    def test_agent_result_has_no_command(self):
        result = route_message("райан создай визуал")
        if result.route_type == "agent":
            assert result.intent_command is None

    def test_fallback_result_zero_confidence(self):
        result = route_message("абракадабра")
        assert result.route_type == "fallback"
        assert result.confidence == 0.0

    def test_route_result_fields(self):
        r = RouteResult(route_type="test", agent_name="smm", confidence=0.9, intent_command="/test")
        assert r.route_type == "test"
        assert r.agent_name == "smm"
        assert r.confidence == 0.9
        assert r.intent_command == "/test"
