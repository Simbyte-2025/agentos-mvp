"""Tests for agentos.memory.session_transcript — JSONL persistence."""

import json
import pytest
from agentos.memory.session_transcript import SessionTranscript


@pytest.fixture
def transcript(tmp_path):
    return SessionTranscript("test-session", base_dir=str(tmp_path))


class TestSessionTranscript:
    def test_append_and_load(self, transcript):
        transcript.append("user", "Hello")
        transcript.append("agent", "Hi there")
        msgs = transcript.load()
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "Hello"
        assert msgs[1]["role"] == "agent"
        assert "ts" in msgs[0]

    def test_append_with_meta(self, transcript):
        transcript.append("system", "init", meta={"tool": "read_file"})
        msgs = transcript.load()
        assert msgs[0]["meta"]["tool"] == "read_file"

    def test_load_empty(self, transcript):
        assert transcript.load() == []

    def test_message_count(self, transcript):
        assert transcript.message_count() == 0
        transcript.append("user", "a")
        transcript.append("user", "b")
        assert transcript.message_count() == 2

    def test_delete(self, transcript):
        transcript.append("user", "temp")
        assert transcript.path.exists()
        assert transcript.delete() is True
        assert transcript.path.exists() is False
        assert transcript.delete() is False

    def test_list_sessions(self, tmp_path):
        SessionTranscript("alpha", base_dir=str(tmp_path)).append("user", "x")
        SessionTranscript("beta", base_dir=str(tmp_path)).append("user", "y")
        sessions = SessionTranscript.list_sessions(base_dir=str(tmp_path))
        assert sessions == ["alpha", "beta"]

    def test_corrupted_lines_skipped(self, transcript):
        transcript.append("user", "good")
        # Inject corrupted line
        with open(transcript.path, "a") as f:
            f.write("NOT VALID JSON\n")
        transcript.append("user", "also good")
        msgs = transcript.load()
        assert len(msgs) == 2
        assert msgs[0]["content"] == "good"
        assert msgs[1]["content"] == "also good"

    def test_jsonl_format_is_one_json_per_line(self, transcript):
        transcript.append("user", "line1")
        transcript.append("agent", "line2")
        lines = transcript.path.read_text().strip().split("\n")
        assert len(lines) == 2
        for line in lines:
            parsed = json.loads(line)
            assert "role" in parsed
            assert "content" in parsed
            assert "ts" in parsed

    def test_unicode_content(self, transcript):
        transcript.append("user", "café ñoño 日本語")
        msgs = transcript.load()
        assert msgs[0]["content"] == "café ñoño 日本語"
