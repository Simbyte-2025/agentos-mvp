#!/usr/bin/env python
"""
Demo script for Long-Term Memory persistence.

This demonstrates how LTM works with both naive and chroma backends.

Usage:
    # Default (naive backend)
    python tests/manual/ltm_persist_demo.py

    # With chroma backend (requires: pip install chromadb)
    $env:AGENTOS_LTM_BACKEND = "chroma"
    python tests/manual/ltm_persist_demo.py
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from agentos.memory import LongTermMemory


def main():
    print("=" * 60)
    print("Long-Term Memory Persistence Demo")
    print("=" * 60)
    
    # Create memory instance
    memory = LongTermMemory()
    
    # Show which backend is being used
    backend_name = type(memory._backend).__name__
    backend_type = os.getenv("AGENTOS_LTM_BACKEND", "naive")
    persist_dir = os.getenv("AGENTOS_LTM_PERSIST_DIR", ".agentos_memory")
    
    print(f"\n📦 Backend configurado: {backend_type}")
    print(f"✓ Backend activo: {backend_name}")
    
    if backend_name == "ChromaMemoryBackend":
        print(f"💾 Directorio de persistencia: {persist_dir}")
    else:
        print("⚠️  Memoria volátil (datos se pierden al reiniciar)")
    
    # Add some sample data
    print("\n➕ Agregando datos de ejemplo...")
    memory.add("Python es un lenguaje de programación versátil", tags=["python", "tech"])
    memory.add("JavaScript se usa principalmente para desarrollo web", tags=["javascript", "web"])
    memory.add("Machine learning utiliza Python frecuentemente", tags=["ml", "python"])
    print("   ✓ 3 documentos agregados")
    
    # Retrieve data
    print("\n🔍 Buscando documentos relevantes para: 'Python programación'")
    results = memory.retrieve("Python programación", top_k=5)
    
    print(f"   ✓ Recuperados: {len(results)} documentos")
    
    for i, item in enumerate(results, 1):
        print(f"\n   {i}. {item.text}")
        if item.tags:
            print(f"      Tags: {', '.join(item.tags)}")
    
    # Show persistence info
    print("\n" + "=" * 60)
    if backend_name == "ChromaMemoryBackend":
        print("💡 Datos persistidos. Para verificar persistencia:")
        print("   1. Cierra este proceso")
        print("   2. Vuelve a ejecutar este script")
        print("   3. Los datos seguirán disponibles")
    else:
        print("💡 Para usar persistencia, instala chromadb y configura:")
        print("   pip install chromadb")
        print("   $env:AGENTOS_LTM_BACKEND = 'chroma'")
        print("   python tests/manual/ltm_persist_demo.py")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
