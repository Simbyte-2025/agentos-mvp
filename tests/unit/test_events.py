"""Tests for agentos.observability.events — Structured events."""

from agentos.observability.events import (
    BaseEvent,
    LLMCalled,
    LLMCompleted,
    PermissionDenied,
    TaskCompleted,
    TaskFailed,
    TaskStarted,
    ToolCalled,
    ToolTimeout,
)


class TestEvents:
    def test_base_event_has_timestamp(self):
        e = BaseEvent(request_id="r1")
        assert e.timestamp
        assert e.request_id == "r1"

    def test_task_started(self):
        e = TaskStarted(request_id="r1", task="do stuff", user_id="u1")
        d = e.to_dict()
        assert d["event_type"] == "task.started"
        assert d["task"] == "do stuff"

    def test_task_completed(self):
        e = TaskCompleted(agent_name="researcher", duration_ms=123.4, output_length=500)
        d = e.to_dict()
        assert d["event_type"] == "task.completed"
        assert d["duration_ms"] == 123.4

    def test_task_failed(self):
        e = TaskFailed(agent_name="writer", error="boom", error_code="TOOL_TIMEOUT")
        assert e.error_code == "TOOL_TIMEOUT"

    def test_tool_called(self):
        e = ToolCalled(tool_name="read_file", action="read")
        assert e.event_type == "tool.called"

    def test_tool_timeout(self):
        e = ToolTimeout(tool_name="run_command", timeout_seconds=30)
        d = e.to_dict()
        assert d["timeout_seconds"] == 30

    def test_llm_called(self):
        e = LLMCalled(provider="anthropic", model="claude-sonnet", prompt_length=1000)
        assert e.event_type == "llm.called"

    def test_llm_completed(self):
        e = LLMCompleted(provider="anthropic", model="claude-sonnet", input_tokens=100, output_tokens=50)
        d = e.to_dict()
        assert d["input_tokens"] == 100

    def test_permission_denied(self):
        e = PermissionDenied(tool_name="run_command", action="execute", profile="researcher", behavior="deny")
        d = e.to_dict()
        assert d["event_type"] == "permission.denied"
        assert d["behavior"] == "deny"

    def test_to_dict_skips_empty(self):
        e = BaseEvent()
        d = e.to_dict()
        assert "request_id" not in d  # empty string skipped
        assert "timestamp" in d  # non-empty kept
