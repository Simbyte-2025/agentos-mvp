from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import List, Tuple
from uuid import uuid4

from .base import LongTermMemoryBackend, MemoryItem

logger = logging.getLogger(__name__)

# Maximum documents to retrieve for scoring to prevent OOM
MAX_DOCS_FOR_RETRIEVAL = 1000


class ChromaMemoryBackend(LongTermMemoryBackend):
    """Minimal ChromaDB backend for architecture validation.
    
    This implementation provides persistent storage WITHOUT embeddings or semantic search.
    It uses simple token-overlap scoring (same logic as NaiveMemoryBackend) to avoid
    model downloads during this phase.
    
    Real semantic search with embeddings will be added in Phase 4.2.3+.
    
    Configuration:
        AGENTOS_LTM_PERSIST_DIR: Directory for persistent storage (default: .agentos_memory)
    """

    def __init__(self, persist_directory: str | None = None):
        """Initialize ChromaDB backend with local persistence.
        
        Args:
            persist_directory: Optional override for persistence directory.
                              If not provided, uses AGENTOS_LTM_PERSIST_DIR env var
                              or defaults to '.agentos_memory'
        
        Raises:
            ImportError: If chromadb is not installed
        """
        # Lazy import - only import chromadb when backend is created
        try:
            import chromadb
        except ImportError as e:
            raise ImportError(
                "ChromaDB backend requires chromadb package. "
                "Install it with: pip install chromadb"
            ) from e
        
        # Determine persistence directory
        if persist_directory is None:
            persist_directory = os.getenv("AGENTOS_LTM_PERSIST_DIR", ".agentos_memory")
        
        # Create directory if it doesn't exist (using pathlib for Windows compatibility)
        persist_path = Path(persist_directory)
        persist_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Initializing ChromaDB backend with persistence at: {persist_path.absolute()}")
        
        # Initialize ChromaDB client with persistence
        # NOTE: We do NOT use an embedding function to avoid model downloads
        self._client = chromadb.PersistentClient(path=str(persist_path))
        
        # Get or create collection without embedding function
        # This stores raw text only, no vector embeddings
        self._collection = self._client.get_or_create_collection(
            name="agentos_ltm",
            metadata={"description": "AgentOS long-term memory (MVP - no embeddings)"}
        )
        
        logger.info(f"ChromaDB collection initialized. Current document count: {self._collection.count()}")

    def add(self, text: str, tags: List[str] | None = None) -> None:
        """Add a memory item to persistent storage.
        
        Args:
            text: The text content to store
            tags: Optional list of tags/metadata
        """
        # Generate unique ID for this document
        doc_id = str(uuid4())
        
        # Store document with metadata
        # NOTE: ChromaDB requires embeddings OR documents. Since we're not using embeddings,
        # we store the text as a document
        metadata = {"tags": ",".join(tags) if tags else ""}
        
        self._collection.add(
            ids=[doc_id],
            documents=[text],
            metadatas=[metadata]
        )
        
        logger.debug(f"Added document {doc_id} to ChromaDB collection")

    def retrieve(self, query: str, top_k: int = 5) -> List[MemoryItem]:
        """Retrieve relevant memory items using token-overlap scoring.
        
        NOTE: This implementation does NOT use semantic search or embeddings.
        It uses the same token-overlap logic as NaiveMemoryBackend to avoid
        model downloads. Real semantic search will be added in Phase 4.2.3+.
        
        Args:
            query: Search query
            top_k: Maximum number of results to return
            
        Returns:
            List of matching MemoryItem instances, ordered by relevance
        """
        # Get all documents from collection
        # Guard-rail: limit to MAX_DOCS_FOR_RETRIEVAL to prevent OOM
        total_count = self._collection.count()
        
        if total_count == 0:
            return []
        
        if total_count > MAX_DOCS_FOR_RETRIEVAL:
            logger.warning(
                f"Collection has {total_count} documents. "
                f"Limiting retrieval to first {MAX_DOCS_FOR_RETRIEVAL} documents "
                "to prevent memory issues."
            )
            limit = MAX_DOCS_FOR_RETRIEVAL
        else:
            limit = total_count
        
        # Fetch documents
        results = self._collection.get(
            limit=limit,
            include=["documents", "metadatas"]
        )
        
        # Use token-overlap scoring (same as NaiveMemoryBackend)
        qtok = set(re.findall(r"[a-zA-ZáéíóúÁÉÍÓÚñÑ0-9_]+", query.lower()))
        scored: List[Tuple[int, MemoryItem]] = []
        
        for i, doc_text in enumerate(results["documents"]):
            # Calculate token overlap score
            itok = set(re.findall(r"[a-zA-ZáéíóúÁÉÍÓÚñÑ0-9_]+", doc_text.lower()))
            score = len(qtok.intersection(itok))
            
            # Convert to MemoryItem
            metadata = results["metadatas"][i]
            tags_str = metadata.get("tags", "")
            tags = [t.strip() for t in tags_str.split(",") if t.strip()]
            
            memory_item = MemoryItem(text=doc_text, tags=tags)
            scored.append((score, memory_item))
        
        # Sort by score descending and return top_k with score > 0
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for score, item in scored[:top_k] if score > 0]
