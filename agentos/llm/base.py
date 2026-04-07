"""Base LLM client interface with streaming support."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator


class LLMClient(ABC):
    """Abstract base class for LLM clients.

    This interface allows AgentOS to be provider-agnostic,
    supporting different LLM backends (OpenAI, Anthropic, local models, etc.)
    """

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate text from a prompt.

        Args:
            prompt: The input prompt for the LLM

        Returns:
            The generated text response

        Raises:
            Exception: If generation fails
        """
        raise NotImplementedError

    def generate_stream(self, prompt: str) -> Iterator[str]:
        """Generate text as a stream of chunks.

        Default implementation yields the full result from generate().
        Override for true streaming support.
        """
        yield self.generate(prompt)
