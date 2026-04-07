"""Tests for agentos.orchestrators.events — Streaming events."""

import json

from agentos.orchestrators.events import OrchestrationEvent, OrchestrationEventType


class TestOrchestrationEvent:
    def test_create_event(self):
        e = OrchestrationEvent(
            event_type=OrchestrationEventType.PLAN_CREATED,
            request_id="r1",
            data={"subtask_count": 3},
        )
        assert e.event_type == OrchestrationEventType.PLAN_CREATED
        assert e.data["subtask_count"] == 3
        assert e.timestamp

    def test_to_sse_format(self):
        e = OrchestrationEvent(
            event_type=OrchestrationEventType.COMPLETED,
            request_id="r1",
            data={"output": "done"},
        )
        sse = e.to_sse()
        assert sse.startswith("data: ")
        assert sse.endswith("\n\n")
        payload = json.loads(sse.replace("data: ", "").strip())
        assert payload["event"] == "completed"
        assert payload["output"] == "done"

    def test_all_event_types(self):
        for evt_type in OrchestrationEventType:
            e = OrchestrationEvent(event_type=evt_type)
            assert e.event_type.value == evt_type.value
