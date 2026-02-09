"""
Tests for LLM-as-Judge (#7) — Quality scoring for agent responses.
"""

import json
import inspect
import pytest
from unittest.mock import patch, MagicMock
from pydantic import BaseModel


# ── JudgeResult model ─────────────────────────────────────

class TestJudgeResultModel:
    def test_module_exists(self):
        from src.tools.llm_judge import JudgeResult
        assert JudgeResult is not None

    def test_is_pydantic_model(self):
        from src.tools.llm_judge import JudgeResult
        assert issubclass(JudgeResult, BaseModel)

    def test_default_values(self):
        from src.tools.llm_judge import JudgeResult
        r = JudgeResult()
        assert r.relevance == 3
        assert r.completeness == 3
        assert r.accuracy == 3
        assert r.format_score == 3
        assert r.overall == 3.0
        assert r.feedback == ""
        assert r.passed is True

    def test_custom_values(self):
        from src.tools.llm_judge import JudgeResult
        r = JudgeResult(relevance=5, completeness=4, accuracy=5, format_score=4,
                        overall=4.6, feedback="Excellent", passed=True)
        assert r.relevance == 5
        assert r.overall == 4.6

    def test_failed_result(self):
        from src.tools.llm_judge import JudgeResult
        r = JudgeResult(relevance=1, completeness=2, accuracy=1, format_score=1,
                        overall=1.25, feedback="Poor", passed=False)
        assert r.passed is False
        assert r.overall < 3.0

    def test_fields(self):
        from src.tools.llm_judge import JudgeResult
        fields = JudgeResult.model_fields
        assert "relevance" in fields
        assert "completeness" in fields
        assert "accuracy" in fields
        assert "format_score" in fields
        assert "overall" in fields
        assert "feedback" in fields
        assert "passed" in fields


# ── Parse helper ──────────────────────────────────────────

class TestParseJudgeResponse:
    def test_parse_clean_json(self):
        from src.tools.llm_judge import _parse_judge_response
        raw = '{"relevance": 4, "completeness": 3, "accuracy": 5, "format_score": 4, "feedback": "Good"}'
        result = _parse_judge_response(raw)
        assert result is not None
        assert result["relevance"] == 4
        assert result["accuracy"] == 5

    def test_parse_with_markdown_fences(self):
        from src.tools.llm_judge import _parse_judge_response
        raw = '```json\n{"relevance": 4, "completeness": 3, "accuracy": 5, "format_score": 4, "feedback": "ok"}\n```'
        result = _parse_judge_response(raw)
        assert result is not None
        assert result["relevance"] == 4

    def test_parse_with_extra_text(self):
        from src.tools.llm_judge import _parse_judge_response
        raw = 'Here is my evaluation:\n{"relevance": 3, "completeness": 4, "accuracy": 2, "format_score": 3, "feedback": "x"}'
        result = _parse_judge_response(raw)
        assert result is not None
        assert result["accuracy"] == 2

    def test_parse_invalid_json(self):
        from src.tools.llm_judge import _parse_judge_response
        result = _parse_judge_response("not json at all")
        assert result is None

    def test_parse_empty(self):
        from src.tools.llm_judge import _parse_judge_response
        result = _parse_judge_response("")
        assert result is None

    def test_parse_json_without_expected_keys(self):
        from src.tools.llm_judge import _parse_judge_response
        raw = '{"foo": "bar"}'
        result = _parse_judge_response(raw)
        assert result is None


# ── Clamp helper ──────────────────────────────────────────

class TestClamp:
    def test_clamp_normal(self):
        from src.tools.llm_judge import _clamp
        assert _clamp(3) == 3

    def test_clamp_too_low(self):
        from src.tools.llm_judge import _clamp
        assert _clamp(0) == 1

    def test_clamp_too_high(self):
        from src.tools.llm_judge import _clamp
        assert _clamp(10) == 5

    def test_clamp_string(self):
        from src.tools.llm_judge import _clamp
        assert _clamp("4") == 4

    def test_clamp_invalid(self):
        from src.tools.llm_judge import _clamp
        assert _clamp("abc") == 3

    def test_clamp_none(self):
        from src.tools.llm_judge import _clamp
        assert _clamp(None) == 3


# ── judge_response function ──────────────────────────────

class TestJudgeResponse:
    def test_empty_response_returns_low_score(self):
        from src.tools.llm_judge import judge_response
        result = judge_response("test task", "", "manager")
        assert result is not None
        assert result.overall == 1.0
        assert result.passed is False

    def test_short_response_returns_low_score(self):
        from src.tools.llm_judge import judge_response
        result = judge_response("test task", "ok", "manager")
        assert result is not None
        assert result.overall == 1.0
        assert result.passed is False

    @patch("src.tools.tech_tools._call_llm_tech")
    def test_successful_judge(self, mock_llm):
        from src.tools.llm_judge import judge_response
        mock_llm.return_value = json.dumps({
            "relevance": 4, "completeness": 4, "accuracy": 5,
            "format_score": 4, "feedback": "Solid response"
        })
        result = judge_response("analyze finances", "A" * 200, "accountant")
        assert result is not None
        assert result.relevance == 4
        assert result.accuracy == 5
        assert result.passed is True
        assert result.overall >= 4.0

    @patch("src.tools.tech_tools._call_llm_tech")
    def test_low_score_fails(self, mock_llm):
        from src.tools.llm_judge import judge_response
        mock_llm.return_value = json.dumps({
            "relevance": 1, "completeness": 2, "accuracy": 1,
            "format_score": 2, "feedback": "Fabricated data"
        })
        result = judge_response("give me facts", "B" * 200, "manager")
        assert result is not None
        assert result.passed is False
        assert result.overall < 3.0

    @patch("src.tools.tech_tools._call_llm_tech")
    def test_llm_returns_none(self, mock_llm):
        from src.tools.llm_judge import judge_response
        mock_llm.return_value = None
        result = judge_response("task", "A" * 200, "manager")
        assert result is None

    @patch("src.tools.tech_tools._call_llm_tech")
    def test_llm_returns_unparseable(self, mock_llm):
        from src.tools.llm_judge import judge_response
        mock_llm.return_value = "I cannot evaluate this because..."
        result = judge_response("task", "A" * 200, "manager")
        assert result is None

    @patch("src.tools.tech_tools._call_llm_tech", side_effect=Exception("API down"))
    def test_llm_exception_returns_none(self, mock_llm):
        from src.tools.llm_judge import judge_response
        result = judge_response("task", "A" * 200, "manager")
        assert result is None

    @patch("src.tools.tech_tools._call_llm_tech")
    def test_weighted_average_calculation(self, mock_llm):
        from src.tools.llm_judge import judge_response
        mock_llm.return_value = json.dumps({
            "relevance": 5, "completeness": 5, "accuracy": 5,
            "format_score": 5, "feedback": "Perfect"
        })
        result = judge_response("task", "A" * 200, "manager")
        assert result is not None
        assert result.overall == 5.0

    @patch("src.tools.tech_tools._call_llm_tech")
    def test_weighted_average_mixed(self, mock_llm):
        from src.tools.llm_judge import judge_response
        # relevance=4*0.30 + completeness=2*0.25 + accuracy=4*0.30 + format=2*0.15
        # = 1.2 + 0.5 + 1.2 + 0.3 = 3.2
        mock_llm.return_value = json.dumps({
            "relevance": 4, "completeness": 2, "accuracy": 4,
            "format_score": 2, "feedback": "Mixed"
        })
        result = judge_response("task", "A" * 200, "manager")
        assert result is not None
        assert abs(result.overall - 3.2) < 0.01


# ── Judge prompt constants ────────────────────────────────

class TestJudgePrompt:
    def test_system_prompt_exists(self):
        from src.tools.llm_judge import _JUDGE_SYSTEM
        assert "relevance" in _JUDGE_SYSTEM
        assert "completeness" in _JUDGE_SYSTEM
        assert "accuracy" in _JUDGE_SYSTEM
        assert "format" in _JUDGE_SYSTEM
        assert "1-5" in _JUDGE_SYSTEM

    def test_prompt_template_has_placeholders(self):
        from src.tools.llm_judge import _JUDGE_PROMPT
        assert "{task}" in _JUDGE_PROMPT
        assert "{response}" in _JUDGE_PROMPT
        assert "{agent_name}" in _JUDGE_PROMPT


# ── Integration with flows ───────────────────────────────

class TestFlowsIntegration:
    def test_judge_and_log_exists(self):
        from src.flows import _judge_and_log
        assert callable(_judge_and_log)

    def test_judge_and_log_signature(self):
        from src.flows import _judge_and_log
        sig = inspect.signature(_judge_and_log)
        params = list(sig.parameters.keys())
        assert "agent_name" in params
        assert "short_desc" in params
        assert "task_description" in params
        assert "result" in params

    def test_run_single_agent_calls_judge(self):
        from src.flows import CorporationFlow
        src = inspect.getsource(CorporationFlow.run_single_agent)
        assert "_judge_and_log" in src

    def test_run_specialist_calls_judge(self):
        from src.flows import CorporationFlow
        src = inspect.getsource(CorporationFlow.run_specialist)
        assert "_judge_and_log" in src

    def test_judge_and_log_never_raises(self):
        """_judge_and_log should catch all exceptions."""
        from src.flows import _judge_and_log
        # Should not raise even with broken imports
        _judge_and_log("manager", "test", "test task", "test result")


# ── Activity tracker integration ──────────────────────────

class TestActivityTrackerIntegration:
    def test_log_quality_score_exists(self):
        from src.activity_tracker import log_quality_score
        assert callable(log_quality_score)

    def test_log_quality_score_imported_in_flows(self):
        import src.flows as flows_module
        src = inspect.getsource(flows_module)
        assert "log_quality_score" in src

    def test_log_quality_score_writes_event(self, tmp_path):
        """log_quality_score should add quality_score event to log."""
        import json
        from unittest.mock import patch as p
        log_file = tmp_path / "activity_log.json"
        log_file.write_text('{"events": [], "agent_status": {}}')

        with p("src.activity_tracker._log_path", return_value=str(log_file)):
            from src.activity_tracker import log_quality_score
            log_quality_score("accountant", "финансовый отчёт", 4.2, {
                "relevance": 4, "accuracy": 5,
            })

        data = json.loads(log_file.read_text())
        events = data["events"]
        assert len(events) == 1
        assert events[0]["type"] == "quality_score"
        assert events[0]["agent"] == "accountant"
        assert events[0]["score"] == 4.2
        assert events[0]["details"]["accuracy"] == 5
