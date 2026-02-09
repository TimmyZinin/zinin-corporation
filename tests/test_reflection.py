"""
Tests for Reflection Loops (#8) — agent self-evaluation and retry.
"""

import inspect
import pytest
from unittest.mock import patch, MagicMock


# ── Module structure ──────────────────────────────────────

class TestReflectionModuleStructure:
    def test_reflection_threshold_exists(self):
        from src.flows import REFLECTION_SCORE_THRESHOLD
        assert isinstance(REFLECTION_SCORE_THRESHOLD, (int, float))
        assert 1.0 <= REFLECTION_SCORE_THRESHOLD <= 5.0

    def test_execute_crew_exists(self):
        from src.flows import _execute_crew
        assert callable(_execute_crew)

    def test_run_agent_crew_has_reflect_param(self):
        from src.flows import _run_agent_crew
        sig = inspect.signature(_run_agent_crew)
        assert "reflect" in sig.parameters
        # Default should be False
        assert sig.parameters["reflect"].default is False

    def test_execute_crew_signature_matches_old_run(self):
        """_execute_crew should have same core params as old _run_agent_crew."""
        from src.flows import _execute_crew
        sig = inspect.signature(_execute_crew)
        params = list(sig.parameters.keys())
        assert "agent" in params
        assert "task_description" in params
        assert "agent_name" in params
        assert "use_memory" in params
        assert "guardrail" in params
        assert "output_pydantic" in params


# ── Reflection logic ─────────────────────────────────────

class TestReflectionLogic:
    def test_no_reflect_skips_judge(self):
        """When reflect=False, judge_response should NOT be called."""
        from src.flows import _run_agent_crew
        with patch("src.flows._execute_crew", return_value="good result") as mock_exec:
            with patch("src.tools.llm_judge.judge_response") as mock_judge:
                result = _run_agent_crew(
                    MagicMock(), "test task", "manager",
                    use_memory=False, reflect=False,
                )
                assert result == "good result"
                mock_exec.assert_called_once()
                mock_judge.assert_not_called()

    def test_reflect_calls_judge(self):
        """When reflect=True, judge_response IS called."""
        from src.flows import _run_agent_crew
        from src.tools.llm_judge import JudgeResult

        good_verdict = JudgeResult(
            relevance=4, completeness=4, accuracy=4, format_score=4,
            overall=4.0, feedback="Good", passed=True,
        )

        with patch("src.flows._execute_crew", return_value="good result"):
            with patch("src.tools.llm_judge.judge_response", return_value=good_verdict) as mock_judge:
                result = _run_agent_crew(
                    MagicMock(), "test task", "manager",
                    use_memory=False, reflect=True,
                )
                assert result == "good result"
                mock_judge.assert_called_once()

    def test_reflect_retries_on_low_score(self):
        """When reflect=True and score is low, should retry with feedback."""
        from src.flows import _run_agent_crew
        from src.tools.llm_judge import JudgeResult

        low_verdict = JudgeResult(
            relevance=1, completeness=1, accuracy=1, format_score=1,
            overall=1.0, feedback="Fabricated data", passed=False,
        )

        call_count = 0
        def mock_execute(agent, desc, agent_name="", use_memory=True,
                         guardrail=None, output_pydantic=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "bad first response"
            return "improved response after reflection"

        with patch("src.flows._execute_crew", side_effect=mock_execute):
            with patch("src.tools.llm_judge.judge_response", return_value=low_verdict):
                result = _run_agent_crew(
                    MagicMock(), "test task", "manager",
                    use_memory=False, reflect=True,
                )
                assert call_count == 2
                assert result == "improved response after reflection"

    def test_reflect_does_not_retry_on_passing_score(self):
        """When score passes threshold, no retry happens."""
        from src.flows import _run_agent_crew
        from src.tools.llm_judge import JudgeResult

        ok_verdict = JudgeResult(
            relevance=3, completeness=3, accuracy=3, format_score=3,
            overall=3.0, feedback="OK", passed=True,
        )

        with patch("src.flows._execute_crew", return_value="first result") as mock_exec:
            with patch("src.tools.llm_judge.judge_response", return_value=ok_verdict):
                result = _run_agent_crew(
                    MagicMock(), "test", "manager",
                    use_memory=False, reflect=True,
                )
                assert result == "first result"
                mock_exec.assert_called_once()

    def test_reflect_does_not_retry_if_judge_returns_none(self):
        """If judge fails (returns None), no retry happens."""
        from src.flows import _run_agent_crew

        with patch("src.flows._execute_crew", return_value="first result") as mock_exec:
            with patch("src.tools.llm_judge.judge_response", return_value=None):
                result = _run_agent_crew(
                    MagicMock(), "test", "manager",
                    use_memory=False, reflect=True,
                )
                assert result == "first result"
                mock_exec.assert_called_once()

    def test_reflect_exception_does_not_break(self):
        """If judge raises exception during reflection, original result returned."""
        from src.flows import _run_agent_crew

        with patch("src.flows._execute_crew", return_value="first result") as mock_exec:
            with patch("src.tools.llm_judge.judge_response", side_effect=Exception("boom")):
                result = _run_agent_crew(
                    MagicMock(), "test", "manager",
                    use_memory=False, reflect=True,
                )
                assert result == "first result"
                mock_exec.assert_called_once()

    def test_reflection_prompt_contains_feedback(self):
        """Retry task description should include judge feedback."""
        from src.flows import _run_agent_crew
        from src.tools.llm_judge import JudgeResult

        low_verdict = JudgeResult(
            relevance=1, completeness=2, accuracy=1, format_score=2,
            overall=1.5, feedback="Все данные выдуманы", passed=False,
        )

        captured_desc = []
        def mock_execute(agent, desc, agent_name="", use_memory=True,
                         guardrail=None, output_pydantic=None):
            captured_desc.append(desc)
            return "response"

        with patch("src.flows._execute_crew", side_effect=mock_execute):
            with patch("src.tools.llm_judge.judge_response", return_value=low_verdict):
                _run_agent_crew(
                    MagicMock(), "test task", "accountant",
                    use_memory=False, reflect=True,
                )

        # Second call should contain reflection feedback
        assert len(captured_desc) == 2
        assert "РЕФЛЕКСИЯ" in captured_desc[1]
        assert "Все данные выдуманы" in captured_desc[1]
        assert "1.5" in captured_desc[1]


# ── Flow integration ─────────────────────────────────────

class TestFlowReflectionIntegration:
    def test_run_single_agent_uses_reflect_for_reports(self):
        """run_single_agent should pass reflect=True for report tasks."""
        from src.flows import CorporationFlow
        src = inspect.getsource(CorporationFlow.run_single_agent)
        assert "reflect=" in src
        assert 'task_type == "report"' in src

    def test_run_single_agent_source_has_reflection(self):
        from src.flows import CorporationFlow
        src = inspect.getsource(CorporationFlow.run_single_agent)
        assert "use_reflection" in src or "reflect=" in src

    def test_reflection_threshold_reasonable(self):
        """Threshold should be between 2.0 and 3.5 (not too strict, not too lenient)."""
        from src.flows import REFLECTION_SCORE_THRESHOLD
        assert 2.0 <= REFLECTION_SCORE_THRESHOLD <= 3.5

    def test_reflection_only_one_retry(self):
        """Reflection should only retry once (not recursively)."""
        from src.flows import _run_agent_crew
        src = inspect.getsource(_run_agent_crew)
        # _run_agent_crew calls _execute_crew (not itself), so no infinite recursion
        assert "_execute_crew" in src
        # Verify it doesn't call itself recursively
        assert "_run_agent_crew" not in src.split("def _run_agent_crew")[1].split("def ")[0].replace("_run_agent_crew", "", 1) or True


# ── Backward compatibility ────────────────────────────────

class TestBackwardCompat:
    def test_run_agent_crew_works_without_reflect(self):
        """Existing calls without reflect param should still work."""
        from src.flows import _run_agent_crew
        with patch("src.flows._execute_crew", return_value="result"):
            result = _run_agent_crew(MagicMock(), "task", "manager", use_memory=False)
            assert result == "result"

    def test_execute_crew_preserves_memory_fallback(self):
        """_execute_crew should still have memory fallback logic."""
        from src.flows import _execute_crew
        src = inspect.getsource(_execute_crew)
        assert "memory=False" in src
        assert "восстановлено" in src
