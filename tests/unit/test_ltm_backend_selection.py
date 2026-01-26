"""Unit tests for LongTermMemory backend selection via AGENTOS_LTM_BACKEND."""

import os
import pytest

from agentos.memory import LongTermMemory
from agentos.memory.long_term import NaiveMemoryBackend


class TestBackendSelection:
    """Test backend selection based on AGENTOS_LTM_BACKEND environment variable."""

    def test_default_backend_is_naive(self, monkeypatch):
        """When no env var is set, should use NaiveMemoryBackend."""
        # Ensure env var is not set
        monkeypatch.delenv("AGENTOS_LTM_BACKEND", raising=False)
        
        memory = LongTermMemory()
        
        assert isinstance(memory._backend, NaiveMemoryBackend)

    def test_explicit_naive_backend(self, monkeypatch):
        """When AGENTOS_LTM_BACKEND=naive, should use NaiveMemoryBackend."""
        monkeypatch.setenv("AGENTOS_LTM_BACKEND", "naive")
        
        memory = LongTermMemory()
        
        assert isinstance(memory._backend, NaiveMemoryBackend)

    def test_invalid_backend_falls_back_to_naive(self, monkeypatch):
        """When invalid backend is specified, should fall back to NaiveMemoryBackend."""
        monkeypatch.setenv("AGENTOS_LTM_BACKEND", "invalid_backend_xyz")
        
        memory = LongTermMemory()
        
        # Should fall back to naive backend
        assert isinstance(memory._backend, NaiveMemoryBackend)

    def test_chroma_backend_fallback_when_not_installed(self, monkeypatch):
        """When chroma backend requested but chromadb not installed, should fall back to naive."""
        monkeypatch.setenv("AGENTOS_LTM_BACKEND", "chroma")
        
        # This should not raise an error, just fall back to naive
        memory = LongTermMemory()
        
        # If chromadb is installed, this will be ChromaMemoryBackend
        # If not installed, should fall back to NaiveMemoryBackend
        # We just verify it doesn't crash and returns a valid backend
        assert memory._backend is not None
        assert hasattr(memory._backend, "add")
        assert hasattr(memory._backend, "retrieve")

    def test_backend_case_insensitive(self, monkeypatch):
        """Backend type should be case-insensitive."""
        monkeypatch.setenv("AGENTOS_LTM_BACKEND", "NAIVE")
        
        memory = LongTermMemory()
        
        assert isinstance(memory._backend, NaiveMemoryBackend)

    def test_backend_functionality_preserved(self, monkeypatch):
        """Regardless of backend, add() and retrieve() should work."""
        monkeypatch.delenv("AGENTOS_LTM_BACKEND", raising=False)
        
        memory = LongTermMemory()
        
        # Test basic functionality
        memory.add("Python is a programming language", tags=["python", "tech"])
        memory.add("JavaScript for web development", tags=["javascript", "web"])
        
        results = memory.retrieve("Python programming", top_k=5)
        
        # Should retrieve at least the Python document
        assert len(results) >= 1
        assert any("Python" in item.text for item in results)
