"""Tests for tests/evals/eval_runner.py — Eval framework."""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from tests.evals.eval_runner import EvalCase, EvalResult, EvalRunner, EvalSummary


@dataclass
class FakeResult:
    success: bool = True
    output: str = ""
    error: Optional[str] = None
    meta: Dict[str, Any] = None

    def __post_init__(self):
        if self.meta is None:
            self.meta = {}


class TestEvalCase:
    def test_defaults(self):
        c = EvalCase(name="test", task="do something")
        assert c.expect_success is True
        assert c.expected_output_contains == []


class TestEvalResult:
    def test_score_all_pass(self):
        r = EvalResult(case_name="t", passed=True, duration_seconds=1.0, checks={"a": True, "b": True})
        assert r.score == 1.0

    def test_score_partial(self):
        r = EvalResult(case_name="t", passed=False, duration_seconds=1.0, checks={"a": True, "b": False})
        assert r.score == 0.5

    def test_score_no_checks(self):
        r = EvalResult(case_name="t", passed=True, duration_seconds=1.0)
        assert r.score == 1.0


class TestEvalRunner:
    def test_run_case_success(self):
        def run_fn(task, session_id, user_id):
            return FakeResult(success=True, output="Python es un lenguaje de programación")

        runner = EvalRunner(run_fn)
        case = EvalCase(name="basic", task="¿Qué es Python?", expected_output_contains=["python"])
        result = runner.run_case(case)
        assert result.passed is True
        assert result.checks["success_match"] is True
        assert result.checks["contains:python"] is True

    def test_run_case_failure(self):
        def run_fn(task, session_id, user_id):
            return FakeResult(success=False, output="", error="crashed")

        runner = EvalRunner(run_fn)
        case = EvalCase(name="fail", task="crash", expect_success=True)
        result = runner.run_case(case)
        assert result.passed is False
        assert result.checks["success_match"] is False

    def test_run_case_exception(self):
        def run_fn(task, session_id, user_id):
            raise RuntimeError("kaboom")

        runner = EvalRunner(run_fn)
        case = EvalCase(name="boom", task="explode")
        result = runner.run_case(case)
        assert result.passed is False
        assert result.error == "kaboom"

    def test_run_all_summary(self):
        call_count = 0

        def run_fn(task, session_id, user_id):
            nonlocal call_count
            call_count += 1
            return FakeResult(success=True, output=f"result {call_count}")

        runner = EvalRunner(run_fn)
        cases = [
            EvalCase(name="a", task="task a"),
            EvalCase(name="b", task="task b"),
        ]
        summary = runner.run_all(cases)
        assert summary.total == 2
        assert summary.passed == 2
        assert summary.failed == 0
        assert summary.avg_score == 1.0

    def test_summary_to_dict(self):
        summary = EvalSummary(total=2, passed=1, failed=1, avg_score=0.5, avg_duration=1.5)
        d = summary.to_dict()
        assert d["pass_rate"] == 0.5
        assert d["avg_score"] == 0.5

    def test_tool_check(self):
        def run_fn(task, session_id, user_id):
            return FakeResult(success=True, output="file content", meta={"tool_calls": [{"tool": "read_file"}]})

        runner = EvalRunner(run_fn)
        case = EvalCase(name="tools", task="read", expected_tools_used=["read_file"])
        result = runner.run_case(case)
        assert result.checks["tool:read_file"] is True

    def test_duration_check(self):
        def run_fn(task, session_id, user_id):
            return FakeResult(success=True, output="fast")

        runner = EvalRunner(run_fn)
        case = EvalCase(name="speed", task="go", max_duration_seconds=10.0)
        result = runner.run_case(case)
        assert result.checks["within_time"] is True
