"""Integration tests for ChromaMemoryBackend with persistence."""

import os
import shutil
from pathlib import Path

import pytest

# Check if chromadb is available
try:
    import chromadb
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

from agentos.memory import LongTermMemory

# Skip all tests in this module if chromadb is not installed
pytestmark = pytest.mark.skipif(
    not CHROMADB_AVAILABLE,
    reason="chromadb not installed - install with: pip install chromadb"
)


class TestChromaMemoryBackend:
    """Integration tests for ChromaDB backend with persistence."""

    @pytest.fixture
    def temp_persist_dir(self, tmp_path):
        """Create a temporary persistence directory for testing."""
        persist_dir = tmp_path / "ltm_chroma_test"
        persist_dir.mkdir(exist_ok=True)
        yield str(persist_dir)
        # Cleanup
        if persist_dir.exists():
            shutil.rmtree(persist_dir)

    def test_chroma_backend_basic_add_retrieve(self, temp_persist_dir, monkeypatch):
        """Test basic add and retrieve operations with ChromaDB backend."""
        monkeypatch.setenv("AGENTOS_LTM_BACKEND", "chroma")
        monkeypatch.setenv("AGENTOS_LTM_PERSIST_DIR", temp_persist_dir)
        
        memory = LongTermMemory()
        
        # Verify we're using ChromaDB backend
        assert type(memory._backend).__name__ == "ChromaMemoryBackend"
        
        # Add some documents
        memory.add("Python is a programming language", tags=["python", "tech"])
        memory.add("JavaScript is used for web development", tags=["javascript", "web"])
        memory.add("Machine learning uses Python frequently", tags=["ml", "python"])
        
        # Retrieve with query
        results = memory.retrieve("Python programming", top_k=5)
        
        # Should retrieve at least one result
        assert len(results) >= 1
        
        # Should contain Python-related content
        assert any("Python" in item.text for item in results)

    def test_chroma_backend_persistence(self, temp_persist_dir, monkeypatch):
        """Test that data persists across ChromaDB backend instances."""
        monkeypatch.setenv("AGENTOS_LTM_BACKEND", "chroma")
        monkeypatch.setenv("AGENTOS_LTM_PERSIST_DIR", temp_persist_dir)
        
        # First instance: add data
        memory1 = LongTermMemory()
        memory1.add("Persistent data test", tags=["test"])
        memory1.add("This should survive restart", tags=["persistence"])
        
        # Get initial results
        results1 = memory1.retrieve("persistent", top_k=5)
        assert len(results1) >= 1
        
        # Create new instance (simulating process restart)
        memory2 = LongTermMemory()
        
        # Should still be able to retrieve the data
        results2 = memory2.retrieve("persistent", top_k=5)
        assert len(results2) >= 1
        assert any("Persistent" in item.text or "persist" in item.text.lower() 
                   for item in results2)

    def test_chroma_backend_with_tags(self, temp_persist_dir, monkeypatch):
        """Test that tags are stored and retrieved correctly."""
        monkeypatch.setenv("AGENTOS_LTM_BACKEND", "chroma")
        monkeypatch.setenv("AGENTOS_LTM_PERSIST_DIR", temp_persist_dir)
        
        memory = LongTermMemory()
        
        # Add with tags
        memory.add("Document with multiple tags", tags=["tag1", "tag2", "tag3"])
        
        # Retrieve
        results = memory.retrieve("Document tags", top_k=5)
        
        assert len(results) >= 1
        # Find the document we added
        for item in results:
            if "multiple tags" in item.text:
                # Tags should be preserved
                assert isinstance(item.tags, list)
                break

    def test_chroma_backend_empty_query_handling(self, temp_persist_dir, monkeypatch):
        """Test handling of empty results."""
        monkeypatch.setenv("AGENTOS_LTM_BACKEND", "chroma")
        monkeypatch.setenv("AGENTOS_LTM_PERSIST_DIR", temp_persist_dir)
        
        memory = LongTermMemory()
        
        # Query on empty collection
        results = memory.retrieve("nonexistent query xyz", top_k=5)
        
        # Should return empty list, not crash
        assert isinstance(results, list)
        assert len(results) == 0

    def test_chroma_backend_top_k_limit(self, temp_persist_dir, monkeypatch):
        """Test that top_k parameter is respected."""
        monkeypatch.setenv("AGENTOS_LTM_BACKEND", "chroma")
        monkeypatch.setenv("AGENTOS_LTM_PERSIST_DIR", temp_persist_dir)
        
        memory = LongTermMemory()
        
        # Add multiple documents
        for i in range(10):
            memory.add(f"Document number {i} about testing", tags=[f"doc{i}"])
        
        # Retrieve with top_k=3
        results = memory.retrieve("Document testing", top_k=3)
        
        # Should return at most 3 results
        assert len(results) <= 3
