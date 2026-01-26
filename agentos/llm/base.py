"""Base LLM client interface."""

from __future__ import annotations

from abc import ABC, abstractmethod


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
