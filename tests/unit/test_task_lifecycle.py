"""Tests for agentos.tasks.lifecycle — Task state machine."""

import pytest
from agentos.tasks.lifecycle import TaskState, TaskStatus, InvalidTransitionError, is_terminal


class TestTaskStatus:
    def test_is_terminal(self):
        assert is_terminal(TaskStatus.COMPLETED) is True
        assert is_terminal(TaskStatus.FAILED) is True
        assert is_terminal(TaskStatus.KILLED) is True
        assert is_terminal(TaskStatus.PENDING) is False
        assert is_terminal(TaskStatus.RUNNING) is False


class TestTaskState:
    def test_initial_state(self):
        ts = TaskState(task="test task", session_id="s1", user_id="u1")
        assert ts.status == TaskStatus.PENDING
        assert ts.task_id.startswith("task_")
        assert ts.started_at is None
        assert ts.completed_at is None
        assert ts.is_terminal is False

    def test_start(self):
        ts = TaskState()
        ts.start()
        assert ts.status == TaskStatus.RUNNING
        assert ts.started_at is not None

    def test_complete(self):
        ts = TaskState()
        ts.start()
        ts.complete("done", meta={"key": "val"})
        assert ts.status == TaskStatus.COMPLETED
        assert ts.output == "done"
        assert ts.meta["key"] == "val"
        assert ts.completed_at is not None
        assert ts.is_terminal is True

    def test_fail(self):
        ts = TaskState()
        ts.start()
        ts.fail("boom")
        assert ts.status == TaskStatus.FAILED
        assert ts.error == "boom"
        assert ts.is_terminal is True

    def test_kill_from_pending(self):
        ts = TaskState()
        ts.kill()
        assert ts.status == TaskStatus.KILLED
        assert ts.is_terminal is True

    def test_kill_from_running(self):
        ts = TaskState()
        ts.start()
        ts.kill()
        assert ts.status == TaskStatus.KILLED

    def test_invalid_transition_complete_from_pending(self):
        ts = TaskState()
        with pytest.raises(InvalidTransitionError):
            ts.complete("nope")

    def test_invalid_transition_start_from_completed(self):
        ts = TaskState()
        ts.start()
        ts.complete("ok")
        with pytest.raises(InvalidTransitionError):
            ts.start()

    def test_invalid_double_start(self):
        ts = TaskState()
        ts.start()
        with pytest.raises(InvalidTransitionError):
            ts.start()

    def test_duration_ms(self):
        ts = TaskState()
        ts.start()
        ts.complete("done")
        assert ts.duration_ms is not None
        assert ts.duration_ms >= 0

    def test_duration_ms_none_when_not_started(self):
        ts = TaskState()
        assert ts.duration_ms is None

    def test_to_dict(self):
        ts = TaskState(task="x", session_id="s", user_id="u")
        ts.start()
        ts.complete("result")
        d = ts.to_dict()
        assert d["status"] == "completed"
        assert d["output"] == "result"
        assert d["task_id"].startswith("task_")
        assert d["duration_ms"] is not None
        assert d["started_at"] is not None
        assert d["completed_at"] is not None
