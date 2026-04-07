"""Tests for agentos.tools.executor — Concurrent tool executor."""

import time
from unittest.mock import MagicMock

from agentos.tools.base import BaseTool, ToolInput, ToolOutput
from agentos.tools.executor import ToolExecutor, ToolCallStatus


class FakeTool(BaseTool):
    is_concurrent_safe = False

    def __init__(self, name="fake", delay=0, fail=False):
        super().__init__(name=name, description="test", risk="read")
        self._delay = delay
        self._fail = fail

    def execute(self, tool_input):
        if self._delay:
            time.sleep(self._delay)
        if self._fail:
            raise RuntimeError("tool failed")
        return ToolOutput(success=True, data={"name": self.name})


class ConcurrentFakeTool(FakeTool):
    is_concurrent_safe = True


class TestExecuteOne:
    def test_success(self):
        executor = ToolExecutor()
        tool = FakeTool(name="read")
        inp = ToolInput(request_id="r1")
        tracked = executor.execute_one(tool, inp)
        assert tracked.status == ToolCallStatus.COMPLETED
        assert tracked.result.success is True
        assert tracked.duration_ms is not None
        assert tracked.duration_ms >= 0
        executor.shutdown()

    def test_failure(self):
        executor = ToolExecutor()
        tool = FakeTool(name="bad", fail=True)
        inp = ToolInput(request_id="r1")
        tracked = executor.execute_one(tool, inp)
        assert tracked.status == ToolCallStatus.FAILED
        assert "tool failed" in tracked.error
        executor.shutdown()

    def test_timeout(self):
        executor = ToolExecutor()
        tool = FakeTool(name="slow", delay=5)
        inp = ToolInput(request_id="r1")
        tracked = executor.execute_one(tool, inp, timeout=0.1)
        assert tracked.status == ToolCallStatus.TIMEOUT
        executor.shutdown()


class TestExecuteBatch:
    def test_sequential_tools(self):
        executor = ToolExecutor()
        calls = [
            {"tool": FakeTool(name="a"), "input": ToolInput(request_id="r1")},
            {"tool": FakeTool(name="b"), "input": ToolInput(request_id="r2")},
        ]
        results = executor.execute_batch(calls)
        assert len(results) == 2
        assert results[0].tool_name == "a"
        assert results[1].tool_name == "b"
        assert all(r.status == ToolCallStatus.COMPLETED for r in results)
        executor.shutdown()

    def test_concurrent_tools_run_parallel(self):
        executor = ToolExecutor(max_workers=4)
        calls = [
            {"tool": ConcurrentFakeTool(name="c1", delay=0.1), "input": ToolInput(request_id="r1")},
            {"tool": ConcurrentFakeTool(name="c2", delay=0.1), "input": ToolInput(request_id="r2")},
        ]
        start = time.monotonic()
        results = executor.execute_batch(calls, timeout=5)
        elapsed = time.monotonic() - start
        # Both should complete in ~0.1s (parallel), not ~0.2s (sequential)
        assert elapsed < 0.3
        assert all(r.status == ToolCallStatus.COMPLETED for r in results)
        executor.shutdown()

    def test_mixed_concurrent_sequential(self):
        executor = ToolExecutor()
        calls = [
            {"tool": ConcurrentFakeTool(name="c1"), "input": ToolInput(request_id="r1")},
            {"tool": FakeTool(name="s1"), "input": ToolInput(request_id="r2")},
            {"tool": ConcurrentFakeTool(name="c2"), "input": ToolInput(request_id="r3")},
        ]
        results = executor.execute_batch(calls)
        assert len(results) == 3
        # Order preserved
        assert results[0].tool_name == "c1"
        assert results[1].tool_name == "s1"
        assert results[2].tool_name == "c2"
        executor.shutdown()

    def test_empty_batch(self):
        executor = ToolExecutor()
        assert executor.execute_batch([]) == []
        executor.shutdown()


class TestTracking:
    def test_get_tracked(self):
        executor = ToolExecutor()
        tool = FakeTool(name="tracked")
        inp = ToolInput(request_id="r1")
        result = executor.execute_one(tool, inp)
        assert executor.get_tracked(result.call_id) is result
        assert executor.get_tracked("nonexistent") is None
        executor.shutdown()
