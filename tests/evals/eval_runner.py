"""Evaluation framework for AgentOS agent quality measurement.

Defines EvalCase dataclass and EvalRunner for running canonical evaluation
cases against the /run endpoint and scoring results.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class EvalCase:
    """A single evaluation case."""

    name: str
    task: str
    expected_output_contains: List[str] = field(default_factory=list)
    expected_tools_used: List[str] = field(default_factory=list)
    expect_success: bool = True
    max_duration_seconds: float = 30.0
    tags: List[str] = field(default_factory=list)


@dataclass
class EvalResult:
    """Result of running a single eval case."""

    case_name: str
    passed: bool
    duration_seconds: float
    checks: Dict[str, bool] = field(default_factory=dict)
    output: str = ""
    error: Optional[str] = None

    @property
    def score(self) -> float:
        if not self.checks:
            return 1.0 if self.passed else 0.0
        return sum(self.checks.values()) / len(self.checks)


@dataclass
class EvalSummary:
    """Aggregate summary of an eval run."""

    total: int = 0
    passed: int = 0
    failed: int = 0
    avg_score: float = 0.0
    avg_duration: float = 0.0
    results: List[EvalResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": round(self.passed / self.total, 3) if self.total else 0,
            "avg_score": round(self.avg_score, 3),
            "avg_duration_s": round(self.avg_duration, 2),
            "results": [
                {"name": r.case_name, "passed": r.passed, "score": round(r.score, 3), "duration_s": round(r.duration_seconds, 2)}
                for r in self.results
            ],
        }


class EvalRunner:
    """Runs eval cases against an orchestrator or run function.

    Args:
        run_fn: Callable(task, session_id, user_id) -> ExecutionResult-like object
                with attributes: success, output, error, meta
    """

    def __init__(self, run_fn: Callable):
        self.run_fn = run_fn

    def run_case(self, case: EvalCase) -> EvalResult:
        """Run a single eval case and score the result."""
        checks: Dict[str, bool] = {}
        start = time.monotonic()
        error = None

        try:
            result = self.run_fn(case.task, f"eval_{case.name}", "eval_user")
            duration = time.monotonic() - start

            # Check success
            checks["success_match"] = result.success == case.expect_success

            # Check output contains expected strings
            output_text = getattr(result, "output", "") or ""
            for expected in case.expected_output_contains:
                checks[f"contains:{expected[:30]}"] = expected.lower() in output_text.lower()

            # Check tools used
            meta = getattr(result, "meta", {}) or {}
            tools_used = [tc.get("tool", "") for tc in meta.get("tool_calls", [])]
            for tool in case.expected_tools_used:
                checks[f"tool:{tool}"] = tool in tools_used

            # Check duration
            checks["within_time"] = duration <= case.max_duration_seconds

            passed = all(checks.values())

        except Exception as e:
            duration = time.monotonic() - start
            error = str(e)
            output_text = ""
            passed = False

        return EvalResult(
            case_name=case.name,
            passed=passed,
            duration_seconds=duration,
            checks=checks,
            output=output_text[:500],
            error=error,
        )

    def run_all(self, cases: List[EvalCase]) -> EvalSummary:
        """Run all eval cases and return summary."""
        results = [self.run_case(c) for c in cases]

        total = len(results)
        passed = sum(1 for r in results if r.passed)
        scores = [r.score for r in results]
        durations = [r.duration_seconds for r in results]

        return EvalSummary(
            total=total,
            passed=passed,
            failed=total - passed,
            avg_score=sum(scores) / total if total else 0,
            avg_duration=sum(durations) / total if total else 0,
            results=results,
        )


# --- Canonical eval cases ---

CANONICAL_CASES = [
    EvalCase(
        name="simple_question",
        task="¿Qué es Python?",
        expected_output_contains=["python"],
        expect_success=True,
        tags=["basic"],
    ),
    EvalCase(
        name="file_read",
        task="Lee el archivo README.md",
        expected_tools_used=["read_file"],
        expect_success=True,
        tags=["tools", "filesystem"],
    ),
    EvalCase(
        name="multi_step",
        task="Investiga qué archivos hay y luego resume el contenido del README",
        expected_output_contains=["readme"],
        expect_success=True,
        max_duration_seconds=60.0,
        tags=["multi-step"],
    ),
    EvalCase(
        name="unknown_task",
        task="xyzzy_nonexistent_impossible_task_12345",
        expect_success=True,  # Should succeed with fallback response
        tags=["edge-case"],
    ),
]
