"""Tests for cross-module integrations (INT-1 through INT-7).

Verifies that the wiring between components works correctly:
- MetricsCollector tracks requests in orchestrator
- DenialTracker records denials during tool selection
- SessionTranscript persists messages during orchestration
- PromptCache integrates with AnthropicClient
- ContextCompactor trims during orchestration
- AppState.healthz() includes metrics
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentos.bootstrap.state import AppState
from agentos.llm.cache import PromptCache
from agentos.memory.compaction import ContextCompactor
from agentos.memory.long_term import LongTermMemory
from agentos.memory.session_transcript import SessionTranscript
from agentos.memory.short_term import ShortTermMemory
from agentos.memory.working_state import WorkingStateStore
from agentos.observability.metrics import MetricsCollector
from agentos.security.denial_tracking import DenialTracker
from agentos.security.permissions import PermissionValidator
from agentos.tools.executor import ToolExecutor


# --- Fixtures ---

PROFILES = {
    "test_agent": {
        "permissions": [
            {"tool": "read_file", "actions": ["read"]},
        ],
        "forbidden": [
            {"tool": "*", "actions": ["execute"]},
        ],
    }
}


class FakeAgent:
    name = "test_agent"
    description = "test"
    profile = "test_agent"
    max_turns = 10

    def can_handle(self, task):
        return True

    def execute(self, task, ctx):
        from agentos.agents.base.agent_base import ExecutionResult
        return ExecutionResult(agent_name=self.name, success=True, output=f"Done: {task}")


class FakeTool:
    def __init__(self, name, risk="read"):
        self.name = name
        self.description = f"Tool {name}"
        self.risk = risk
        self.tool_timeout = 30
        self.is_concurrent_safe = False
        self.input_schema = {}
        self.tags = []

    def is_read_only(self, tool_input=None):
        return self.risk == "read"

    def validate(self, tool_input):
        from agentos.tools.base import ValidationResult
        return ValidationResult(valid=True)

    def dispatch(self, tool_input):
        return self.execute(tool_input)

    def execute(self, tool_input):
        from agentos.tools.base import ToolOutput
        return ToolOutput(success=True, data={"tool": self.name})


@pytest.fixture
def tmp_db(tmp_path):
    return tmp_path / "test.db"


# --- INT-1: ToolExecutor in AppState ---

class TestToolExecutorIntegration:
    def test_app_state_has_tool_executor(self):
        state = AppState()
        assert isinstance(state.tool_executor, ToolExecutor)

    def test_tool_executor_shutdown_registered(self):
        state = AppState()
        # Just verify executor exists and can be shut down
        state.tool_executor.shutdown(wait=False)


# --- INT-2: MetricsCollector in orchestrator ---

class TestMetricsIntegration:
    def test_sequential_records_metrics(self, tmp_db):
        from agentos.orchestrators.sequential import SequentialOrchestrator

        metrics = MetricsCollector()
        orch = SequentialOrchestrator(
            agents=[FakeAgent()],
            tools=[FakeTool("read_file")],
            permission_validator=PermissionValidator(PROFILES),
            short_term=ShortTermMemory(max_items=50),
            working_state=WorkingStateStore(db_path=tmp_db),
            long_term=LongTermMemory(),
            metrics=metrics,
        )

        orch.run("test task", "s1", "u1")

        assert metrics.request_count == 1
        assert metrics.success_count == 1
        assert metrics.error_count == 0

    def test_healthz_includes_metrics(self):
        state = AppState()
        state.metrics.record_request()
        state.metrics.record_success(duration_ms=50)
        h = state.healthz()
        assert "metrics" in h
        assert h["metrics"]["requests"]["total"] == 1


# --- INT-3: SessionTranscript in orchestrator ---

class TestSessionTranscriptIntegration:
    def test_sequential_persists_transcript(self, tmp_db, tmp_path):
        from agentos.orchestrators.sequential import SequentialOrchestrator

        with patch.dict(os.environ, {"AGENTOS_SESSIONS_DIR": str(tmp_path)}):
            orch = SequentialOrchestrator(
                agents=[FakeAgent()],
                tools=[FakeTool("read_file")],
                permission_validator=PermissionValidator(PROFILES),
                short_term=ShortTermMemory(max_items=50),
                working_state=WorkingStateStore(db_path=tmp_db),
                long_term=LongTermMemory(),
            )

            orch.run("do something", "sess_123", "u1")

            transcript = SessionTranscript("sess_123", base_dir=str(tmp_path))
            msgs = transcript.load()
            assert len(msgs) >= 2  # user + agent
            assert msgs[0]["role"] == "user"
            assert msgs[0]["content"] == "do something"
            assert msgs[1]["role"] == "agent"


# --- INT-4: DenialTracker in orchestrator ---

class TestDenialTrackerIntegration:
    def test_sequential_tracks_denials(self, tmp_db):
        from agentos.orchestrators.sequential import SequentialOrchestrator

        tracker = DenialTracker()
        orch = SequentialOrchestrator(
            agents=[FakeAgent()],
            tools=[FakeTool("read_file"), FakeTool("run_command", risk="execute")],
            permission_validator=PermissionValidator(PROFILES),
            short_term=ShortTermMemory(max_items=50),
            working_state=WorkingStateStore(db_path=tmp_db),
            long_term=LongTermMemory(),
            denial_tracker=tracker,
        )

        orch.run("test", "s1", "u1")

        stats = tracker.get_stats("s1")
        # run_command should be denied (execute forbidden for test_agent)
        assert stats["total"] >= 1

    def test_denial_stats_in_healthz(self):
        state = AppState()
        state.denial_tracker.record_denial("s1", "run_command", "execute")
        h = state.healthz()
        assert h["denial_stats"]["s1"]["total"] == 1


# --- INT-5: PromptCache in AnthropicClient ---

class TestPromptCacheIntegration:
    def test_anthropic_client_has_cache(self):
        from agentos.llm.anthropic_client import AnthropicClient
        client = AnthropicClient(api_key="test-key")
        assert isinstance(client.cache, PromptCache)

    def test_cache_stats_accessible(self):
        from agentos.llm.anthropic_client import AnthropicClient
        client = AnthropicClient(api_key="test-key")
        stats = client.cache.stats.to_dict()
        assert stats["total"] == 0


# --- INT-6: Compaction in orchestrator ---

class TestCompactionIntegration:
    def test_sequential_has_compactor(self, tmp_db):
        from agentos.orchestrators.sequential import SequentialOrchestrator

        orch = SequentialOrchestrator(
            agents=[FakeAgent()],
            tools=[],
            permission_validator=PermissionValidator(PROFILES),
            short_term=ShortTermMemory(max_items=50),
            working_state=WorkingStateStore(db_path=tmp_db),
            long_term=LongTermMemory(),
        )

        assert isinstance(orch.compactor, ContextCompactor)


# --- INT-7: GET /metrics endpoint ---

class TestMetricsEndpoint:
    def test_metrics_in_healthz_response(self):
        state = AppState()
        state.metrics.record_request()
        state.metrics.record_request()
        state.metrics.record_error("TIMEOUT")
        h = state.healthz()
        assert h["metrics"]["requests"]["total"] == 2
        assert h["metrics"]["requests"]["error"] == 1
        assert h["metrics"]["errors_by_code"]["TIMEOUT"] == 1
