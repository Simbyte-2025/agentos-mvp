"""Context compaction to prevent context window overflow.

Inspired by jan-research multi-level compaction:
1. Tool Result Trimming — replace old tool outputs with "[trimmed]"
2. LLM Summarization — summarize conversation when tokens exceed threshold

This is a pragmatic 2-level approach for the MVP.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English/Spanish."""
    return max(1, len(text) // 4)


def estimate_messages_tokens(messages: List[Dict[str, Any]]) -> int:
    """Estimate total tokens across a list of messages."""
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += estimate_tokens(content)
        # meta/tool results can be large
        meta = msg.get("meta", {})
        if meta:
            total += estimate_tokens(str(meta))
    return total


class ContextCompactor:
    """Two-level context compaction.

    Level 1 (trim): Replace old tool results with "[trimmed]" markers.
    Level 2 (summarize): Use LLM to summarize the oldest portion of conversation.

    Args:
        max_context_tokens: Approximate context window size (default 100k).
        trim_threshold: Fraction of max at which trimming triggers (default 0.6).
        summarize_threshold: Fraction of max at which summarization triggers (default 0.8).
        keep_recent: Number of recent messages to always preserve (default 10).
    """

    def __init__(
        self,
        max_context_tokens: int = 100_000,
        trim_threshold: float = 0.6,
        summarize_threshold: float = 0.8,
        keep_recent: int = 10,
    ):
        self.max_context_tokens = max_context_tokens
        self.trim_threshold = trim_threshold
        self.summarize_threshold = summarize_threshold
        self.keep_recent = keep_recent

    def should_trim(self, messages: List[Dict[str, Any]]) -> bool:
        tokens = estimate_messages_tokens(messages)
        return tokens > int(self.max_context_tokens * self.trim_threshold)

    def should_summarize(self, messages: List[Dict[str, Any]]) -> bool:
        tokens = estimate_messages_tokens(messages)
        return tokens > int(self.max_context_tokens * self.summarize_threshold)

    def trim_tool_results(
        self,
        messages: List[Dict[str, Any]],
        marker: str = "[resultado recortado]",
    ) -> List[Dict[str, Any]]:
        """Level 1: Replace tool result content in old messages with a trim marker.

        Preserves the most recent ``keep_recent`` messages untouched.
        Only trims messages whose role is 'system' or 'agent' and whose
        content looks like a tool result (contains known patterns).
        """
        if len(messages) <= self.keep_recent:
            return list(messages)

        boundary = len(messages) - self.keep_recent
        result: List[Dict[str, Any]] = []

        for i, msg in enumerate(messages):
            if i < boundary and _is_tool_result(msg):
                trimmed = dict(msg)
                trimmed["content"] = marker
                # Clear meta to free space
                trimmed.pop("meta", None)
                result.append(trimmed)
            else:
                result.append(msg)

        return result

    def summarize(
        self,
        messages: List[Dict[str, Any]],
        llm_generate: Callable[[str], str],
    ) -> List[Dict[str, Any]]:
        """Level 2: Summarize the oldest portion of conversation using LLM.

        Splits messages into old (to summarize) and recent (to keep).
        Replaces old messages with a single summary message.
        """
        if len(messages) <= self.keep_recent:
            return list(messages)

        boundary = len(messages) - self.keep_recent
        old_messages = messages[:boundary]
        recent_messages = messages[boundary:]

        # Build conversation text for summarization
        conv_text = _format_messages_for_summary(old_messages)

        prompt = (
            "Resume la siguiente conversación en un párrafo conciso. "
            "Mantén los hechos clave, decisiones tomadas, y resultados de herramientas importantes. "
            "No incluyas detalles innecesarios.\n\n"
            f"Conversación:\n{conv_text}"
        )

        try:
            summary = llm_generate(prompt)
        except Exception:
            # If summarization fails, fall back to trimming
            return self.trim_tool_results(messages)

        summary_msg: Dict[str, Any] = {
            "role": "system",
            "content": f"[Resumen de conversación anterior]\n{summary}",
        }

        return [summary_msg] + list(recent_messages)

    def compact(
        self,
        messages: List[Dict[str, Any]],
        llm_generate: Optional[Callable[[str], str]] = None,
    ) -> List[Dict[str, Any]]:
        """Auto-compact: apply the appropriate level based on token count.

        Returns a (possibly shorter) message list.
        """
        if self.should_summarize(messages) and llm_generate:
            return self.summarize(messages, llm_generate)
        if self.should_trim(messages):
            return self.trim_tool_results(messages)
        return list(messages)


# --- Helpers ---

_TOOL_RESULT_PATTERNS = re.compile(
    r"(exit_code|stdout|stderr|status_code|data|result|output)",
    re.IGNORECASE,
)


def _is_tool_result(msg: Dict[str, Any]) -> bool:
    """Heuristic: message looks like a tool result if it's from agent/system
    and contains typical tool output keywords."""
    role = msg.get("role", "")
    if role not in ("system", "agent"):
        return False
    content = msg.get("content", "")
    if not isinstance(content, str):
        return False
    return bool(_TOOL_RESULT_PATTERNS.search(content))


def _format_messages_for_summary(messages: List[Dict[str, Any]], max_chars: int = 8000) -> str:
    """Format messages into a readable conversation string, truncated to max_chars."""
    parts: List[str] = []
    total = 0
    for msg in messages:
        role = msg.get("role", "?")
        content = msg.get("content", "")
        if not isinstance(content, str):
            content = str(content)
        line = f"{role}: {content[:500]}"
        if total + len(line) > max_chars:
            parts.append("... [conversación truncada]")
            break
        parts.append(line)
        total += len(line)
    return "\n".join(parts)
