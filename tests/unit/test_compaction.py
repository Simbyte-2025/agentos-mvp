"""Tests for agentos.memory.compaction — Context compaction."""

from agentos.memory.compaction import (
    ContextCompactor,
    estimate_tokens,
    estimate_messages_tokens,
)


def _make_msg(role: str, content: str, meta=None) -> dict:
    msg = {"role": role, "content": content}
    if meta:
        msg["meta"] = meta
    return msg


class TestTokenEstimation:
    def test_estimate_tokens(self):
        assert estimate_tokens("") == 1  # min 1
        assert estimate_tokens("hello world") == 2  # 11 chars / 4

    def test_estimate_messages_tokens(self):
        msgs = [_make_msg("user", "hello " * 100)]
        tokens = estimate_messages_tokens(msgs)
        assert tokens > 100


class TestTrimToolResults:
    def test_preserves_recent(self):
        compactor = ContextCompactor(keep_recent=2)
        msgs = [
            _make_msg("system", "exit_code: 0, stdout: lots of data"),
            _make_msg("agent", "result: some output"),
            _make_msg("user", "what next?"),
            _make_msg("agent", "let me help"),
        ]
        trimmed = compactor.trim_tool_results(msgs)
        assert trimmed[0]["content"] == "[resultado recortado]"
        assert trimmed[1]["content"] == "[resultado recortado]"
        assert trimmed[2]["content"] == "what next?"
        assert trimmed[3]["content"] == "let me help"

    def test_preserves_user_messages(self):
        compactor = ContextCompactor(keep_recent=1)
        msgs = [
            _make_msg("user", "do something"),
            _make_msg("system", "stdout: hello"),
            _make_msg("user", "final"),
        ]
        trimmed = compactor.trim_tool_results(msgs)
        # user messages are not tool results
        assert trimmed[0]["content"] == "do something"
        assert trimmed[1]["content"] == "[resultado recortado]"

    def test_no_trim_when_few_messages(self):
        compactor = ContextCompactor(keep_recent=10)
        msgs = [_make_msg("user", "hello")]
        assert compactor.trim_tool_results(msgs) == msgs


class TestSummarize:
    def test_summarize_uses_llm(self):
        compactor = ContextCompactor(keep_recent=2)
        msgs = [
            _make_msg("user", "task A"),
            _make_msg("agent", "done A, result: important_data"),
            _make_msg("user", "task B"),
            _make_msg("agent", "done B"),
        ]

        def mock_llm(prompt: str) -> str:
            return "Se completaron las tareas A y B exitosamente."

        result = compactor.summarize(msgs, mock_llm)
        assert len(result) == 3  # 1 summary + 2 recent
        assert "[Resumen de conversación anterior]" in result[0]["content"]
        assert result[1]["content"] == "task B"
        assert result[2]["content"] == "done B"

    def test_summarize_fallback_on_error(self):
        compactor = ContextCompactor(keep_recent=1)
        msgs = [
            _make_msg("system", "exit_code: 0, stdout: data"),
            _make_msg("user", "next"),
        ]

        def failing_llm(prompt: str) -> str:
            raise RuntimeError("LLM unavailable")

        result = compactor.summarize(msgs, failing_llm)
        # Falls back to trim
        assert result[0]["content"] == "[resultado recortado]"


class TestCompact:
    def test_compact_no_action_when_small(self):
        compactor = ContextCompactor(max_context_tokens=100_000)
        msgs = [_make_msg("user", "hello")]
        assert compactor.compact(msgs) == msgs

    def test_compact_trims_at_threshold(self):
        # 500 chars ≈ 125 tokens. With max=150, trim at 0.5 (75), summarize at 0.99 (148).
        # 125 > 75 → trim triggers. 125 < 148 → summarize does NOT trigger.
        compactor = ContextCompactor(max_context_tokens=150, trim_threshold=0.5, summarize_threshold=0.99, keep_recent=1)
        msgs = [
            _make_msg("system", "exit_code: 0, stdout: " + "x" * 500),
            _make_msg("user", "ok"),
        ]
        result = compactor.compact(msgs)
        assert result[0]["content"] == "[resultado recortado]"

    def test_compact_summarizes_at_high_threshold(self):
        compactor = ContextCompactor(max_context_tokens=100, summarize_threshold=0.8, keep_recent=1)
        msgs = [
            _make_msg("agent", "result: " + "x" * 400),
            _make_msg("user", "ok"),
        ]
        result = compactor.compact(msgs, llm_generate=lambda p: "Summary here")
        assert "[Resumen" in result[0]["content"]


class TestShouldThresholds:
    def test_should_trim(self):
        c = ContextCompactor(max_context_tokens=100, trim_threshold=0.5)
        small = [_make_msg("user", "hi")]
        big = [_make_msg("user", "x" * 300)]
        assert c.should_trim(small) is False
        assert c.should_trim(big) is True

    def test_should_summarize(self):
        c = ContextCompactor(max_context_tokens=100, summarize_threshold=0.8)
        big = [_make_msg("user", "x" * 400)]
        assert c.should_summarize(big) is True
