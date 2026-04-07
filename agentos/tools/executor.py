"""Concurrent tool executor with shared thread pool.

Inspired by jan-research src/services/tools/StreamingToolExecutor.ts:
- Shared thread pool (not per-call)
- Concurrent execution of safe tools
- Status tracking per tool call
- Ordered result collection
"""

from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from agentos.tools.base import BaseTool, ToolInput, ToolOutput, ToolTimeoutError


class ToolCallStatus(str, Enum):
    QUEUED = "queued"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class TrackedToolCall:
    """Tracks the lifecycle of a single tool execution."""

    call_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    tool_name: str = ""
    status: ToolCallStatus = ToolCallStatus.QUEUED
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[ToolOutput] = None
    error: Optional[str] = None

    @property
    def duration_ms(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at) * 1000
        return None


class ToolExecutor:
    """Executes tools with a shared thread pool and concurrency control.

    Args:
        max_workers: Maximum concurrent tool executions (default 4).
        default_timeout: Default timeout per tool in seconds (default 30).
    """

    def __init__(self, max_workers: int = 4, default_timeout: int = 30):
        self.max_workers = max_workers
        self.default_timeout = default_timeout
        self._pool = ThreadPoolExecutor(max_workers=max_workers)
        self._tracked: Dict[str, TrackedToolCall] = {}

    def execute_one(
        self,
        tool: BaseTool,
        tool_input: ToolInput,
        timeout: Optional[int] = None,
    ) -> TrackedToolCall:
        """Execute a single tool synchronously with tracking."""
        tracked = TrackedToolCall(tool_name=tool.name)
        self._tracked[tracked.call_id] = tracked
        timeout = timeout or getattr(tool, "tool_timeout", self.default_timeout)

        tracked.status = ToolCallStatus.EXECUTING
        tracked.started_at = time.monotonic()

        try:
            future = self._pool.submit(tool.dispatch, tool_input)
            result = future.result(timeout=timeout)
            tracked.result = result
            tracked.status = ToolCallStatus.COMPLETED
        except Exception as e:
            if "TimeoutError" in type(e).__name__:
                tracked.status = ToolCallStatus.TIMEOUT
                tracked.error = f"Timeout after {timeout}s"
            else:
                tracked.status = ToolCallStatus.FAILED
                tracked.error = str(e)
        finally:
            tracked.completed_at = time.monotonic()

        return tracked

    def execute_batch(
        self,
        calls: List[Dict[str, Any]],
        timeout: Optional[int] = None,
    ) -> List[TrackedToolCall]:
        """Execute multiple tool calls, running concurrent-safe tools in parallel.

        Each call dict must have: {"tool": BaseTool, "input": ToolInput}
        Optional: {"timeout": int}

        Concurrent-safe tools run in parallel; others run sequentially.
        Results are returned in the same order as the input calls.
        """
        if not calls:
            return []

        # Separate concurrent-safe from sequential
        concurrent_calls: List[Dict[str, Any]] = []
        sequential_calls: List[Dict[str, Any]] = []

        for i, call in enumerate(calls):
            call["_index"] = i
            tool: BaseTool = call["tool"]
            if getattr(tool, "is_concurrent_safe", False):
                concurrent_calls.append(call)
            else:
                sequential_calls.append(call)

        results: List[Optional[TrackedToolCall]] = [None] * len(calls)

        # Execute concurrent-safe tools in parallel
        if concurrent_calls:
            futures: Dict[Future, int] = {}
            for call in concurrent_calls:
                tool = call["tool"]
                tool_input = call["input"]
                t = call.get("timeout", timeout or getattr(tool, "tool_timeout", self.default_timeout))

                tracked = TrackedToolCall(tool_name=tool.name)
                tracked.status = ToolCallStatus.EXECUTING
                tracked.started_at = time.monotonic()
                self._tracked[tracked.call_id] = tracked

                future = self._pool.submit(tool.dispatch, tool_input)
                futures[future] = call["_index"]
                # Store tracked for this index
                results[call["_index"]] = tracked

            for future in as_completed(futures, timeout=timeout or self.default_timeout):
                idx = futures[future]
                tracked = results[idx]
                try:
                    tracked.result = future.result(timeout=0)
                    tracked.status = ToolCallStatus.COMPLETED
                except Exception as e:
                    tracked.status = ToolCallStatus.FAILED
                    tracked.error = str(e)
                finally:
                    tracked.completed_at = time.monotonic()

        # Execute sequential tools one by one
        for call in sequential_calls:
            tracked = self.execute_one(
                call["tool"],
                call["input"],
                timeout=call.get("timeout", timeout),
            )
            results[call["_index"]] = tracked

        return [r for r in results if r is not None]

    def get_tracked(self, call_id: str) -> Optional[TrackedToolCall]:
        return self._tracked.get(call_id)

    def shutdown(self, wait: bool = True) -> None:
        self._pool.shutdown(wait=wait)
