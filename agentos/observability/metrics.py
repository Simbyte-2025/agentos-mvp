"""Metrics collector for AgentOS.

Inspired by jan-research src/bootstrap/state.ts tracking of
totalCostUSD, totalAPIDuration, totalToolDuration, per-model usage.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class MetricsCollector:
    """Thread-safe metrics collector for runtime statistics."""

    # Counters
    request_count: int = 0
    success_count: int = 0
    error_count: int = 0

    # Duration accumulators (ms)
    total_api_duration_ms: float = 0.0
    total_tool_duration_ms: float = 0.0

    # Token usage
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    # Per-model tracking
    model_usage: Dict[str, Dict[str, int]] = field(
        default_factory=lambda: defaultdict(lambda: {"calls": 0, "input_tokens": 0, "output_tokens": 0})
    )

    # Error breakdown
    errors_by_code: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    # Tool usage
    tool_calls: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    tool_errors: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_request(self) -> None:
        with self._lock:
            self.request_count += 1

    def record_success(self, duration_ms: float = 0.0) -> None:
        with self._lock:
            self.success_count += 1
            self.total_api_duration_ms += duration_ms

    def record_error(self, error_code: str = "UNKNOWN") -> None:
        with self._lock:
            self.error_count += 1
            self.errors_by_code[error_code] += 1

    def record_llm_usage(self, model: str, input_tokens: int, output_tokens: int, duration_ms: float = 0.0) -> None:
        with self._lock:
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            self.total_api_duration_ms += duration_ms
            usage = self.model_usage[model]
            usage["calls"] += 1
            usage["input_tokens"] += input_tokens
            usage["output_tokens"] += output_tokens

    def record_tool_call(self, tool_name: str, duration_ms: float = 0.0, success: bool = True) -> None:
        with self._lock:
            self.tool_calls[tool_name] += 1
            self.total_tool_duration_ms += duration_ms
            if not success:
                self.tool_errors[tool_name] += 1

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "requests": {
                    "total": self.request_count,
                    "success": self.success_count,
                    "error": self.error_count,
                },
                "tokens": {
                    "total_input": self.total_input_tokens,
                    "total_output": self.total_output_tokens,
                },
                "duration_ms": {
                    "api": round(self.total_api_duration_ms, 1),
                    "tools": round(self.total_tool_duration_ms, 1),
                },
                "model_usage": dict(self.model_usage),
                "errors_by_code": dict(self.errors_by_code),
                "tool_calls": dict(self.tool_calls),
                "tool_errors": dict(self.tool_errors),
            }

    def reset(self) -> None:
        with self._lock:
            self.request_count = 0
            self.success_count = 0
            self.error_count = 0
            self.total_api_duration_ms = 0.0
            self.total_tool_duration_ms = 0.0
            self.total_input_tokens = 0
            self.total_output_tokens = 0
            self.model_usage.clear()
            self.errors_by_code.clear()
            self.tool_calls.clear()
            self.tool_errors.clear()
