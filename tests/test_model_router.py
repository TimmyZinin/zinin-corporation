"""Tests for Smart Model Router."""

import pytest
from unittest.mock import patch

from src.model_router import (
    TaskComplexity,
    MODEL_TIERS,
    AGENT_COMPLEXITY,
    COMPLEX_KEYWORDS,
    SIMPLE_KEYWORDS,
    is_smart_routing_enabled,
    assess_complexity,
    select_model,
    get_routing_summary,
    _complexity_rank,
)


# ──────────────────────────────────────────────────────────
# TaskComplexity enum
# ──────────────────────────────────────────────────────────

class TestTaskComplexity:
    def test_values(self):
        assert TaskComplexity.SIMPLE == "simple"
        assert TaskComplexity.MODERATE == "moderate"
        assert TaskComplexity.COMPLEX == "complex"

    def test_count(self):
        assert len(TaskComplexity) == 3


# ──────────────────────────────────────────────────────────
# Model tiers config
# ──────────────────────────────────────────────────────────

class TestModelTiers:
    def test_has_all_complexities(self):
        assert TaskComplexity.SIMPLE in MODEL_TIERS
        assert TaskComplexity.MODERATE in MODEL_TIERS
        assert TaskComplexity.COMPLEX in MODEL_TIERS

    def test_each_has_model(self):
        for complexity, tier in MODEL_TIERS.items():
            assert "model" in tier
            assert "description" in tier
            assert "requires_key" in tier

    def test_groq_for_simple(self):
        assert "groq" in MODEL_TIERS[TaskComplexity.SIMPLE]["model"]

    def test_haiku_for_moderate(self):
        assert "haiku" in MODEL_TIERS[TaskComplexity.MODERATE]["model"]

    def test_sonnet_for_complex(self):
        assert "sonnet" in MODEL_TIERS[TaskComplexity.COMPLEX]["model"]


# ──────────────────────────────────────────────────────────
# Agent complexity defaults
# ──────────────────────────────────────────────────────────

class TestAgentComplexity:
    def test_manager_is_complex(self):
        assert AGENT_COMPLEXITY["manager"] == TaskComplexity.COMPLEX

    def test_accountant_is_complex(self):
        assert AGENT_COMPLEXITY["accountant"] == TaskComplexity.COMPLEX

    def test_smm_is_moderate(self):
        assert AGENT_COMPLEXITY["smm"] == TaskComplexity.MODERATE

    def test_has_all_agents(self):
        expected = {"manager", "accountant", "automator", "smm", "designer", "cpo"}
        assert set(AGENT_COMPLEXITY.keys()) == expected


# ──────────────────────────────────────────────────────────
# Keywords
# ──────────────────────────────────────────────────────────

class TestKeywords:
    def test_complex_keywords_non_empty(self):
        assert len(COMPLEX_KEYWORDS) >= 5

    def test_simple_keywords_non_empty(self):
        assert len(SIMPLE_KEYWORDS) >= 5

    def test_no_overlap(self):
        assert not COMPLEX_KEYWORDS.intersection(SIMPLE_KEYWORDS)


# ──────────────────────────────────────────────────────────
# is_smart_routing_enabled
# ──────────────────────────────────────────────────────────

class TestIsSmartRoutingEnabled:
    def test_disabled_by_default(self):
        with patch.dict("os.environ", {}, clear=True):
            assert is_smart_routing_enabled() is False

    def test_enabled_with_1(self):
        with patch.dict("os.environ", {"SMART_ROUTING_ENABLED": "1"}):
            assert is_smart_routing_enabled() is True

    def test_enabled_with_true(self):
        with patch.dict("os.environ", {"SMART_ROUTING_ENABLED": "true"}):
            assert is_smart_routing_enabled() is True

    def test_enabled_with_yes(self):
        with patch.dict("os.environ", {"SMART_ROUTING_ENABLED": "yes"}):
            assert is_smart_routing_enabled() is True

    def test_disabled_with_0(self):
        with patch.dict("os.environ", {"SMART_ROUTING_ENABLED": "0"}):
            assert is_smart_routing_enabled() is False


# ──────────────────────────────────────────────────────────
# assess_complexity
# ──────────────────────────────────────────────────────────

class TestAssessComplexity:
    def test_delegation_always_complex(self):
        result = assess_complexity("simple message", has_delegation=True)
        assert result == TaskComplexity.COMPLEX

    def test_complex_keyword(self):
        result = assess_complexity("подготовь стратегию на Q1")
        assert result == TaskComplexity.COMPLEX

    def test_simple_keyword(self):
        result = assess_complexity("покажи статус")
        assert result == TaskComplexity.SIMPLE

    def test_agent_override_manager(self):
        result = assess_complexity("привет", agent_name="manager")
        # manager default is COMPLEX, but "привет" is simple keyword
        # simple < complex, so min should win
        assert result == TaskComplexity.SIMPLE

    def test_agent_override_smm(self):
        result = assess_complexity("обычное сообщение средней длины", agent_name="smm")
        assert result == TaskComplexity.MODERATE

    def test_short_message(self):
        result = assess_complexity("окей")
        assert result in (TaskComplexity.SIMPLE, TaskComplexity.MODERATE)

    def test_long_message(self):
        result = assess_complexity("x" * 400)
        assert result in (TaskComplexity.MODERATE, TaskComplexity.COMPLEX)

    def test_many_tools(self):
        result = assess_complexity("test", tool_count=15)
        assert result in (TaskComplexity.MODERATE, TaskComplexity.COMPLEX)

    def test_unknown_agent(self):
        result = assess_complexity("test message here", agent_name="unknown_agent")
        assert result == TaskComplexity.MODERATE

    def test_balance_keyword_simple(self):
        result = assess_complexity("баланс")
        assert result == TaskComplexity.SIMPLE

    def test_review_keyword_complex(self):
        result = assess_complexity("нужен review кода")
        assert result == TaskComplexity.COMPLEX

    def test_budget_keyword_complex(self):
        result = assess_complexity("бюджет на следующий месяц")
        assert result == TaskComplexity.COMPLEX


# ──────────────────────────────────────────────────────────
# select_model
# ──────────────────────────────────────────────────────────

class TestSelectModel:
    def test_disabled_uses_default(self):
        with patch.dict("os.environ", {"SMART_ROUTING_ENABLED": "0"}):
            result = select_model(TaskComplexity.SIMPLE)
            assert "sonnet" in result  # default model

    def test_disabled_uses_agent_config(self):
        with patch.dict("os.environ", {"SMART_ROUTING_ENABLED": "0"}):
            config = {"llm": "openrouter/anthropic/claude-haiku-4-5-20251001"}
            result = select_model(TaskComplexity.SIMPLE, agent_config=config)
            assert "haiku" in result

    def test_enabled_simple_with_groq(self):
        with patch.dict("os.environ", {
            "SMART_ROUTING_ENABLED": "1",
            "GROQ_API_KEY": "test-key",
        }):
            result = select_model(TaskComplexity.SIMPLE)
            assert "groq" in result

    def test_enabled_simple_no_groq_fallback(self):
        with patch.dict("os.environ", {
            "SMART_ROUTING_ENABLED": "1",
            "GROQ_API_KEY": "",
            "OPENROUTER_API_KEY": "test",
        }, clear=False):
            result = select_model(TaskComplexity.SIMPLE)
            assert "haiku" in result  # falls back to moderate

    def test_enabled_moderate(self):
        with patch.dict("os.environ", {
            "SMART_ROUTING_ENABLED": "1",
            "OPENROUTER_API_KEY": "test",
        }):
            result = select_model(TaskComplexity.MODERATE)
            assert "haiku" in result

    def test_enabled_complex(self):
        with patch.dict("os.environ", {
            "SMART_ROUTING_ENABLED": "1",
            "OPENROUTER_API_KEY": "test",
        }):
            result = select_model(TaskComplexity.COMPLEX)
            assert "sonnet" in result


# ──────────────────────────────────────────────────────────
# get_routing_summary
# ──────────────────────────────────────────────────────────

class TestGetRoutingSummary:
    def test_returns_string(self):
        result = get_routing_summary()
        assert isinstance(result, str)

    def test_contains_status(self):
        result = get_routing_summary()
        assert "Smart Model Routing" in result

    def test_contains_tiers(self):
        result = get_routing_summary()
        assert "simple" in result
        assert "moderate" in result
        assert "complex" in result


# ──────────────────────────────────────────────────────────
# _complexity_rank
# ──────────────────────────────────────────────────────────

class TestComplexityRank:
    def test_ordering(self):
        assert _complexity_rank(TaskComplexity.SIMPLE) < _complexity_rank(TaskComplexity.MODERATE)
        assert _complexity_rank(TaskComplexity.MODERATE) < _complexity_rank(TaskComplexity.COMPLEX)
