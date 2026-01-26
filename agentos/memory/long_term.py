from __future__ import annotations

import logging
import os
import re
from typing import List, Tuple

from .base import LongTermMemoryBackend, MemoryItem

logger = logging.getLogger(__name__)


class NaiveMemoryBackend(LongTermMemoryBackend):
    """Naive in-memory backend with token-overlap search.
    
    This is the default/fallback implementation that requires no external dependencies.
    Search is based on simple token overlap rather than semantic similarity.
    """

    def __init__(self):
        self._items: List[MemoryItem] = []

    def add(self, text: str, tags: List[str] | None = None) -> None:
        self._items.append(MemoryItem(text=text, tags=tags or []))

    def retrieve(self, query: str, top_k: int = 5) -> List[MemoryItem]:
        qtok = set(re.findall(r"[a-zA-ZáéíóúÁÉÍÓÚñÑ0-9_]+", query.lower()))
        scored: List[Tuple[int, MemoryItem]] = []
        for it in self._items:
            itok = set(re.findall(r"[a-zA-ZáéíóúÁÉÍÓÚñÑ0-9_]+", it.text.lower()))
            score = len(qtok.intersection(itok))
            scored.append((score, it))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [it for score, it in scored[:top_k] if score > 0]


class LongTermMemory:
    """Memoria a largo plazo (MVP): almacén en memoria con búsqueda por overlap.

    En producción: vector store + embeddings.
    
    Backend can be selected via AGENTOS_LTM_BACKEND environment variable:
    - "naive" (default): In-memory token-overlap search
    - "chroma": ChromaDB-based backend (requires chromadb installed)
    """

    def __init__(self):
        self._backend = self._select_backend()

    def _select_backend(self) -> LongTermMemoryBackend:
        """Select memory backend based on AGENTOS_LTM_BACKEND env var.
        
        Returns:
            Selected backend instance (falls back to NaiveMemoryBackend on error)
        """
        backend_type = os.getenv("AGENTOS_LTM_BACKEND", "naive").lower()
        
        if backend_type == "naive":
            return NaiveMemoryBackend()
        
        elif backend_type == "chroma":
            # Try to import chroma backend (lazy import)
            try:
                from .chroma import ChromaMemoryBackend
                return ChromaMemoryBackend()
            except (ImportError, ModuleNotFoundError) as e:
                logger.warning(
                    f"ChromaDB backend requested but not available: {e}. "
                    "Falling back to naive backend. "
                    "To use chroma backend, install chromadb: pip install chromadb"
                )
                return NaiveMemoryBackend()
        
        else:
            logger.warning(
                f"Unknown memory backend '{backend_type}'. "
                f"Valid options: 'naive', 'chroma'. Falling back to naive backend."
            )
            return NaiveMemoryBackend()

    def add(self, text: str, tags: List[str] | None = None) -> None:
        self._backend.add(text, tags)

    def retrieve(self, query: str, top_k: int = 5) -> List[MemoryItem]:
        return self._backend.retrieve(query, top_k)
