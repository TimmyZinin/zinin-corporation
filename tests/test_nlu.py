"""Tests for CEO NLU module — Russian intent detection."""

import pytest
from unittest.mock import patch

from src.telegram_ceo.nlu import (
    Intent,
    INTENT_MAP,
    AGENT_INTENT_MAP,
    _normalize_text,
    detect_intent,
    detect_agent,
)


# ──────────────────────────────────────────────────────────
# Normalization tests
# ──────────────────────────────────────────────────────────

class TestNormalize:
    def test_lowercase(self):
        assert _normalize_text("HELLO") == "hello"

    def test_strip_spaces(self):
        assert _normalize_text("  hello  ") == "hello"

    def test_strip_punctuation(self):
        assert _normalize_text("hello!") == "hello"
        assert _normalize_text("что?") == "что"

    def test_collapse_spaces(self):
        assert _normalize_text("hello   world") == "hello world"

    def test_empty(self):
        assert _normalize_text("") == ""

    def test_mixed(self):
        assert _normalize_text("  Привет,  Мир!  ") == "привет мир"


# ──────────────────────────────────────────────────────────
# Intent detection tests
# ──────────────────────────────────────────────────────────

class TestDetectIntent:
    def test_exact_balance(self):
        intent = detect_intent("баланс")
        assert intent is not None
        assert intent.command == "/balance"
        assert intent.confidence == 1.0

    def test_exact_tasks(self):
        intent = detect_intent("задачи")
        assert intent is not None
        assert intent.command == "/tasks"

    def test_exact_status(self):
        intent = detect_intent("статус")
        assert intent is not None
        assert intent.command == "/status"

    def test_exact_help(self):
        intent = detect_intent("помощь")
        assert intent is not None
        assert intent.command == "/help"

    def test_phrase_balance(self):
        intent = detect_intent("покажи баланс")
        assert intent is not None
        assert intent.command == "/balance"
        assert intent.confidence >= 0.8

    def test_phrase_tasks(self):
        intent = detect_intent("что с задачами")
        assert intent is not None
        assert intent.command == "/tasks"

    def test_phrase_report(self):
        intent = detect_intent("отчёт")
        assert intent is not None
        assert intent.command == "/report"

    def test_phrase_analytics(self):
        intent = detect_intent("аналитика")
        assert intent is not None
        assert intent.command == "/analytics"

    def test_starts_with(self):
        intent = detect_intent("покажи баланс на счету")
        assert intent is not None
        assert intent.command == "/balance"
        assert intent.confidence >= 0.8

    def test_contained_in_text(self):
        intent = detect_intent("скажи пожалуйста какой баланс сейчас")
        assert intent is not None
        assert intent.command == "/balance"

    def test_case_insensitive(self):
        intent = detect_intent("БАЛАНС")
        assert intent is not None
        assert intent.command == "/balance"

    def test_with_punctuation(self):
        intent = detect_intent("баланс?")
        assert intent is not None
        assert intent.command == "/balance"

    def test_no_match(self):
        intent = detect_intent("расскажи анекдот про программиста")
        assert intent is None

    def test_too_short(self):
        intent = detect_intent("ок")
        assert intent is None

    def test_empty(self):
        intent = detect_intent("")
        assert intent is None

    def test_content_command(self):
        intent = detect_intent("напиши пост")
        assert intent is not None
        assert intent.command == "/content"

    def test_linkedin_command(self):
        intent = detect_intent("linkedin статус")
        assert intent is not None
        assert intent.command == "/linkedin"

    def test_review(self):
        intent = detect_intent("стратегический обзор")
        assert intent is not None
        assert intent.command == "/review"

    def test_task_pool(self):
        intent = detect_intent("task pool")
        assert intent is not None
        assert intent.command == "/tasks"

    def test_report_alias(self):
        intent = detect_intent("сводка")
        assert intent is not None
        assert intent.command == "/report"

    def test_what_commands(self):
        intent = detect_intent("какие команды")
        assert intent is not None
        assert intent.command == "/help"

    def test_full_report(self):
        intent = detect_intent("полный отчёт")
        assert intent is not None
        assert intent.command == "/report"

    def test_cost_analytics(self):
        intent = detect_intent("сколько потратили")
        assert intent is not None
        assert intent.command == "/analytics"


# ──────────────────────────────────────────────────────────
# Intent model tests
# ──────────────────────────────────────────────────────────

class TestIntentModel:
    def test_defaults(self):
        intent = Intent(command="/test", confidence=0.8)
        assert intent.agent == ""
        assert intent.params == {}

    def test_with_agent(self):
        intent = Intent(command="/test", confidence=0.9, agent="accountant")
        assert intent.agent == "accountant"

    def test_with_params(self):
        intent = Intent(command="/test", confidence=0.7, params={"topic": "crypto"})
        assert intent.params["topic"] == "crypto"


# ──────────────────────────────────────────────────────────
# Agent detection tests
# ──────────────────────────────────────────────────────────

class TestDetectAgent:
    def test_direct_mention_mattias(self):
        result = detect_agent("спроси маттиаса про бюджет")
        assert result is not None
        assert result[0] == "accountant"
        assert result[1] >= 0.9

    def test_direct_mention_martin(self):
        result = detect_agent("мартин, проверь API")
        assert result is not None
        assert result[0] == "automator"

    def test_direct_mention_yuki(self):
        result = detect_agent("юки, напиши пост")
        assert result is not None
        assert result[0] == "smm"

    def test_direct_mention_ryan(self):
        result = detect_agent("райан, нужна инфографика")
        assert result is not None
        assert result[0] == "designer"

    def test_direct_mention_sophie(self):
        result = detect_agent("софи, обнови бэклог")
        assert result is not None
        assert result[0] == "cpo"

    def test_role_mention_cfo(self):
        result = detect_agent("спроси cfo")
        assert result is not None
        assert result[0] == "accountant"

    def test_role_mention_cto(self):
        result = detect_agent("cto должен проверить")
        assert result is not None
        assert result[0] == "automator"

    def test_keyword_finance(self):
        result = detect_agent("расход и бюджет")
        assert result is not None
        assert result[0] == "accountant"

    def test_keyword_deploy(self):
        result = detect_agent("нужно задеплоить")
        assert result is not None
        assert result[0] == "automator"

    def test_no_match(self):
        result = detect_agent("привет как дела")
        assert result is None

    def test_empty(self):
        result = detect_agent("")
        assert result is None


# ──────────────────────────────────────────────────────────
# Coverage tests
# ──────────────────────────────────────────────────────────

class TestIntentMapCoverage:
    def test_all_commands_have_phrases(self):
        for cmd, phrases in INTENT_MAP.items():
            assert len(phrases) >= 2, f"{cmd} has too few phrases"

    def test_all_agents_have_phrases(self):
        for agent, phrases in AGENT_INTENT_MAP.items():
            assert len(phrases) >= 3, f"{agent} has too few phrases"

    def test_intent_map_commands_start_with_slash(self):
        for cmd in INTENT_MAP:
            assert cmd.startswith("/"), f"{cmd} doesn't start with /"
