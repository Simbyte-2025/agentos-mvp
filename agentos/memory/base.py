from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List


@dataclass
class MemoryItem:
    """Item stored in long-term memory."""
    text: str
    tags: List[str] = field(default_factory=list)


class LongTermMemoryBackend(ABC):
    """Abstract interface for long-term memory backends."""

    @abstractmethod
    def add(self, text: str, tags: List[str] | None = None) -> None:
        """Add a memory item.
        
        Args:
            text: The text content to store
            tags: Optional list of tags/metadata
        """
        pass

    @abstractmethod
    def retrieve(self, query: str, top_k: int = 5) -> List[MemoryItem]:
        """Retrieve relevant memory items.
        
        Args:
            query: Search query
            top_k: Maximum number of results to return
            
        Returns:
            List of matching MemoryItem instances
        """
        pass
