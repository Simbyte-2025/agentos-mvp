"""Memory consolidation — summarize short-term into long-term.

Inspired by jan-research src/services/extractMemories/:
background extraction of structured memories from conversation transcripts.

When ShortTermMemory reaches capacity, older messages are summarized via LLM
and stored in LongTermMemory with auto-generated tags, preventing knowledge
loss between sessions.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional

from agentos.memory.long_term import LongTermMemory
from agentos.memory.short_term import ShortTermMemory
from agentos.observability.logging import get_logger

logger = get_logger("agentos.memory.consolidation")


def _extract_tags(text: str) -> List[str]:
    """Heuristic tag extraction from text content."""
    tags: List[str] = []
    # Detect common topic patterns
    if re.search(r"(código|code|script|función|function|class)", text, re.I):
        tags.append("code")
    if re.search(r"(error|fallo|failed|exception|bug)", text, re.I):
        tags.append("error")
    if re.search(r"(resultado|result|output|respuesta|response)", text, re.I):
        tags.append("result")
    if re.search(r"(plan|subtask|tarea|task)", text, re.I):
        tags.append("planning")
    if re.search(r"(http|url|api|fetch|request)", text, re.I):
        tags.append("http")
    if re.search(r"(archivo|file|read_file|write)", text, re.I):
        tags.append("filesystem")
    return tags or ["general"]


class ConsolidationJob:
    """Consolidates short-term memory into long-term memory.

    Usage:
        job = ConsolidationJob(short_term, long_term, llm_generate)
        job.run(session_id)  # Summarize and persist
    """

    def __init__(
        self,
        short_term: ShortTermMemory,
        long_term: LongTermMemory,
        llm_generate: Optional[Callable[[str], str]] = None,
        consolidation_threshold: int = 20,
    ):
        self.short_term = short_term
        self.long_term = long_term
        self.llm_generate = llm_generate
        self.consolidation_threshold = consolidation_threshold

    def should_consolidate(self, session_id: str) -> bool:
        """Return True if session has enough messages to warrant consolidation."""
        messages = self.short_term.get(session_id)
        return len(messages) >= self.consolidation_threshold

    def run(self, session_id: str) -> int:
        """Consolidate short-term memory for a session.

        Returns the number of memory items added to LTM.
        """
        messages = self.short_term.get(session_id)
        if not messages:
            return 0

        added = 0

        if self.llm_generate:
            added = self._consolidate_with_llm(messages, session_id)
        else:
            added = self._consolidate_heuristic(messages, session_id)

        logger.info(
            "Consolidation complete",
            extra={"session_id": session_id, "messages_processed": len(messages), "items_added": added},
        )
        return added

    def _consolidate_with_llm(self, messages: List[Dict[str, Any]], session_id: str) -> int:
        """Summarize conversation via LLM and store in LTM."""
        conv_text = self._format_conversation(messages)

        prompt = (
            "Extrae los hechos clave, decisiones, y resultados importantes de esta conversación. "
            "Devuelve cada hecho en una línea separada, sin numeración ni viñetas.\n\n"
            f"Conversación:\n{conv_text}"
        )

        try:
            response = self.llm_generate(prompt)
        except Exception as e:
            logger.warning(f"LLM consolidation failed, falling back to heuristic: {e}")
            return self._consolidate_heuristic(messages, session_id)

        # Split response into individual facts
        facts = [line.strip() for line in response.split("\n") if line.strip()]
        added = 0
        for fact in facts:
            tags = _extract_tags(fact)
            tags.append(f"session:{session_id}")
            tags.append("consolidated")
            self.long_term.add(fact, tags=tags)
            added += 1

        return added

    def _consolidate_heuristic(self, messages: List[Dict[str, Any]], session_id: str) -> int:
        """Deterministic consolidation: store agent outputs directly."""
        added = 0
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if not isinstance(content, str) or not content.strip():
                continue
            # Only store substantive agent responses (>50 chars)
            if role == "agent" and len(content) > 50:
                tags = _extract_tags(content)
                tags.append(f"session:{session_id}")
                tags.append("consolidated")
                self.long_term.add(content, tags=tags)
                added += 1
        return added

    @staticmethod
    def _format_conversation(messages: List[Dict[str, Any]], max_chars: int = 6000) -> str:
        parts: List[str] = []
        total = 0
        for msg in messages:
            role = msg.get("role", "?")
            content = msg.get("content", "")
            if not isinstance(content, str):
                content = str(content)
            line = f"{role}: {content[:300]}"
            if total + len(line) > max_chars:
                parts.append("... [truncado]")
                break
            parts.append(line)
            total += len(line)
        return "\n".join(parts)
