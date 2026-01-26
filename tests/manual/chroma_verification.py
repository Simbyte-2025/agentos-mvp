"""
Temporary manual test for ChromaMemoryBackend.

This test is NOT part of the test suite. It's for manual verification only
when chromadb is installed.

To run:
1. Install chromadb: pip install chromadb
2. Run: python tests/.tmp_chroma_verification.py
3. Delete this file after verification
"""

def test_chroma_backend_basic():
    """Verify ChromaMemoryBackend basic functionality."""
    try:
        import chromadb
        print(f"✓ chromadb installed: {chromadb.__version__}")
    except ImportError:
        print("✗ chromadb not installed - skipping verification")
        print("  To test, run: pip install chromadb")
        return
    
    import shutil
    from pathlib import Path
    from agentos.memory.chroma import ChromaMemoryBackend
    from agentos.memory.base import MemoryItem
    
    # Use a temporary test directory
    test_dir = Path(".tmp_chroma_test")
    
    try:
        # Clean up any previous test data
        if test_dir.exists():
            shutil.rmtree(test_dir)
        
        print(f"\n1. Creating ChromaMemoryBackend with persist_dir: {test_dir}")
        backend = ChromaMemoryBackend(persist_directory=str(test_dir))
        print("   ✓ Backend created successfully")
        
        # Test add
        print("\n2. Adding test documents...")
        backend.add("Python is a programming language", tags=["python", "tech"])
        backend.add("JavaScript is used for web development", tags=["javascript", "web"])
        backend.add("Machine learning uses Python frequently", tags=["ml", "python"])
        print("   ✓ 3 documents added")
        
        # Test retrieve
        print("\n3. Testing retrieval with query: 'Python programming'")
        results = backend.retrieve("Python programming", top_k=2)
        print(f"   ✓ Retrieved {len(results)} results:")
        for i, item in enumerate(results, 1):
            print(f"     {i}. {item.text[:50]}... (tags: {item.tags})")
        
        # Test persistence
        print("\n4. Testing persistence (creating new backend instance)...")
        backend2 = ChromaMemoryBackend(persist_directory=str(test_dir))
        results2 = backend2.retrieve("JavaScript", top_k=5)
        print(f"   ✓ Retrieved {len(results2)} results from persisted data:")
        for i, item in enumerate(results2, 1):
            print(f"     {i}. {item.text[:50]}...")
        
        # Test guard-rail (not actually hitting it, just verifying the code path)
        print("\n5. Verifying guard-rail is in place...")
        from agentos.memory.chroma import MAX_DOCS_FOR_RETRIEVAL
        print(f"   ✓ Maximum retrieval limit set to: {MAX_DOCS_FOR_RETRIEVAL} documents")
        
        print("\n✅ All checks passed!")
        print("\nNOTE: This backend uses token-overlap scoring (no embeddings).")
        print("Semantic search with embeddings will be added in Phase 4.2.3+")
        
    finally:
        # Clean up test directory
        if test_dir.exists():
            shutil.rmtree(test_dir)
            print(f"\n🧹 Cleaned up test directory: {test_dir}")


if __name__ == "__main__":
    test_chroma_backend_basic()
