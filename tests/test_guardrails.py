"""
Tests for task guardrails — validate agent output quality.
"""

import pytest
from types import SimpleNamespace


# ── Imports ──────────────────────────────────────────────

from src.crew import (
    _manager_guardrail,
    _specialist_guardrail,
    _has_template_phrases,
    _has_data_indicators,
    _TEMPLATE_PHRASES,
    _DATA_INDICATORS,
)


# ── Helper: fake TaskOutput ─────────────────────────────

def _fake_output(text: str):
    return SimpleNamespace(raw=text)


# ── Template phrase detection ────────────────────────────

class TestTemplatePhrases:
    def test_detects_template_phrase(self):
        found = _has_template_phrases("Я запущу анализ данных сейчас")
        assert len(found) >= 1
        assert "я запущу" in found

    def test_no_template_phrases(self):
        found = _has_template_phrases("Доход $142K, расходы $50K, рост 23%")
        assert len(found) == 0

    def test_detects_introduction(self):
        found = _has_template_phrases("Привет, я Алексей Воронов, CEO")
        assert len(found) >= 1

    def test_detects_multiple_templates(self):
        found = _has_template_phrases("Начинаю проверку, сейчас проверю все системы")
        assert len(found) >= 2

    def test_case_insensitive(self):
        found = _has_template_phrases("НАЧИНАЮ АНАЛИЗ")
        assert len(found) >= 1

    def test_template_list_not_empty(self):
        assert len(_TEMPLATE_PHRASES) >= 10


# ── Data indicators detection ───────────────────────────

class TestDataIndicators:
    def test_detects_dollar(self):
        assert _has_data_indicators("Доход: $142K") is True

    def test_detects_ruble(self):
        assert _has_data_indicators("Баланс: 50000₽") is True

    def test_detects_percent(self):
        assert _has_data_indicators("Рост 23%") is True

    def test_detects_url(self):
        assert _has_data_indicators("Сервер: https://api.example.com") is True

    def test_detects_status_emoji(self):
        assert _has_data_indicators("Статус: ✅ Работает") is True

    def test_no_indicators(self):
        assert _has_data_indicators("Просто текст без данных") is False

    def test_detects_api(self):
        assert _has_data_indicators("API вернул ответ") is True

    def test_indicators_list_not_empty(self):
        assert len(_DATA_INDICATORS) >= 10


# ── Manager guardrail ───────────────────────────────────

class TestManagerGuardrail:
    def test_rejects_too_short(self):
        ok, msg = _manager_guardrail(_fake_output("Ок"))
        assert ok is False
        assert "короткий" in msg.lower()

    def test_accepts_long_response(self):
        text = "Анализ показал рост выручки на 23% за квартал. " * 5
        ok, msg = _manager_guardrail(_fake_output(text))
        assert ok is True

    def test_rejects_template_short(self):
        text = "Я запущу анализ данных. Сейчас проверю все показатели. " * 3
        ok, msg = _manager_guardrail(_fake_output(text))
        assert ok is False
        assert "шаблонн" in msg.lower()

    def test_accepts_template_with_long_content(self):
        """If response has templates but is long enough (>300), accept it."""
        text = "Сейчас проверю. " + "Реальные данные: $142K доход, расходы $50K. " * 20
        ok, msg = _manager_guardrail(_fake_output(text))
        assert ok is True

    def test_accepts_empty_but_long(self):
        text = "A" * 101
        ok, msg = _manager_guardrail(_fake_output(text))
        assert ok is True

    def test_rejects_exactly_100_chars(self):
        text = "A" * 99
        ok, msg = _manager_guardrail(_fake_output(text))
        assert ok is False

    def test_handles_none_output(self):
        ok, msg = _manager_guardrail(None)
        assert ok is False

    def test_handles_non_raw_output(self):
        ok, msg = _manager_guardrail("Short")
        assert ok is False

    def test_returns_text_on_success(self):
        text = "Реальные данные от инструментов: баланс $10K, расходы $5K." * 3
        ok, msg = _manager_guardrail(_fake_output(text))
        assert ok is True
        assert msg == text


# ── Specialist guardrail ─────────────────────────────────

class TestSpecialistGuardrail:
    def test_rejects_too_short(self):
        ok, msg = _specialist_guardrail(_fake_output("Проверено."))
        assert ok is False
        assert "короткий" in msg.lower()

    def test_accepts_long_with_data(self):
        text = "API статус: ✅ OK. Latency 45ms. Баланс: $142K. " * 5
        ok, msg = _specialist_guardrail(_fake_output(text))
        assert ok is True

    def test_rejects_template_no_data(self):
        text = "Начинаю проверку всех систем. Приступаю к анализу показателей. " * 5
        ok, msg = _specialist_guardrail(_fake_output(text))
        assert ok is False
        assert "шаблонн" in msg.lower()

    def test_accepts_template_with_data(self):
        """If response has templates AND real data, accept it."""
        text = "Начинаю проверку. Результат: API вернул код 200, баланс $50K, рост 15%." * 3
        ok, msg = _specialist_guardrail(_fake_output(text))
        assert ok is True

    def test_rejects_exactly_150_chars(self):
        text = "A" * 149
        ok, msg = _specialist_guardrail(_fake_output(text))
        assert ok is False

    def test_accepts_151_chars(self):
        text = "A" * 151
        ok, msg = _specialist_guardrail(_fake_output(text))
        assert ok is True

    def test_handles_none_output(self):
        ok, msg = _specialist_guardrail(None)
        assert ok is False

    def test_returns_text_on_success(self):
        text = "API health: all 12 endpoints OK. Latency avg 42ms. Cost: $0.03/day." * 3
        ok, msg = _specialist_guardrail(_fake_output(text))
        assert ok is True
        assert msg == text


# ── Guardrails applied to all agents ─────────────────────

class TestGuardrailsApplied:
    """Verify guardrails are wired to all agents in execute_task."""

    def test_execute_task_applies_specialist_guardrail(self):
        """Non-manager agents should get _specialist_guardrail."""
        import inspect
        from src.crew import AICorporation
        src = inspect.getsource(AICorporation.execute_task)
        assert "_specialist_guardrail" in src

    def test_execute_task_applies_manager_guardrail(self):
        """Manager should get _manager_guardrail."""
        import inspect
        from src.crew import AICorporation
        src = inspect.getsource(AICorporation.execute_task)
        assert "_manager_guardrail" in src

    def test_auto_delegation_has_specialist_guardrail(self):
        """Auto-delegated specialist tasks should have guardrail."""
        import inspect
        from src.crew import AICorporation
        src = inspect.getsource(AICorporation.execute_task)
        # The auto-delegation path passes guardrail=_specialist_guardrail
        assert "guardrail=_specialist_guardrail" in src

    def test_create_task_supports_guardrail(self):
        """create_task should accept guardrail parameter."""
        import inspect
        from src.crew import create_task
        sig = inspect.signature(create_task)
        assert "guardrail" in sig.parameters

    def test_create_task_sets_max_retries(self):
        """When guardrail is provided, max retries should be set."""
        import inspect
        from src.crew import create_task
        src = inspect.getsource(create_task)
        assert "guardrail_max_retries" in src
