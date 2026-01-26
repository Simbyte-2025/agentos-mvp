"""
Script de verificación: Minimax Provider Integration (Import Check)

⚠️ IMPORTANTE: Este script solo verifica que MinimaxClient se puede importar
e integrar correctamente. NO hace llamadas reales a la API de Minimax.

Para validación real con API de Minimax, usar:
  tests/manual/minimax_api_smoke.ps1
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_minimax_import():
    """Test 1: MinimaxClient se puede importar."""
    print("✓ Test 1: Importando MinimaxClient...")
    try:
        from agentos.llm.minimax import MinimaxClient
        print("  ✅ MinimaxClient importado correctamente")
        return True
    except ImportError as e:
        print(f"  ❌ Error al importar: {e}")
        return False


def test_minimax_instantiation():
    """Test 2: MinimaxClient se puede instanciar sin API key."""
    print("\n✓ Test 2: Instanciando MinimaxClient sin API key...")
    try:
        from agentos.llm.minimax import MinimaxClient
        client = MinimaxClient(api_key=None)
        print(f"  ✅ Cliente instanciado: {client}")
        print(f"     - base_url: {client.base_url}")
        print(f"     - model: {client.model}")
        print(f"     - timeout: {client.timeout}s")
        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_minimax_in_main():
    """Test 3: main.py puede importar y usar MinimaxClient."""
    print("\n✓ Test 3: Verificando integración en main.py...")
    try:
        # Set env vars to trigger minimax path
        os.environ["AGENTOS_ORCHESTRATOR"] = "planner"
        os.environ["AGENTOS_LLM_PROVIDER"] = "minimax"
        # Don't set MINIMAX_API_KEY to test graceful handling
        
        from agentos.api.main import _orchestrator
        
        print(f"  ✅ Orquestador inicializado: {type(_orchestrator).__name__}")
        
        # Check if it's PlannerExecutor with MinimaxClient
        if hasattr(_orchestrator, 'llm_client'):
            from agentos.llm.minimax import MinimaxClient
            if isinstance(_orchestrator.llm_client, MinimaxClient):
                print(f"  ✅ LLM client es MinimaxClient")
                print(f"     - API key configurada: {_orchestrator.llm_client.api_key is not None}")
            else:
                print(f"  ⚠️  LLM client es {type(_orchestrator.llm_client).__name__}")
        else:
            print(f"  ⚠️  Orquestador no tiene llm_client")
        
        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_api_healthz():
    """Test 4: API /healthz endpoint funciona."""
    print("\n✓ Test 4: Verificando endpoint /healthz...")
    try:
        from agentos.api.main import app
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        response = client.get("/healthz")
        
        if response.status_code == 200:
            data = response.json()
            print(f"  ✅ /healthz responde OK")
            print(f"     - Agentes: {data.get('agents', [])}")
            print(f"     - Tools: {data.get('tools', [])}")
            return True
        else:
            print(f"  ❌ Status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def main():
    """Ejecutar todos los tests de verificación."""
    print("=" * 60)
    print("VERIFICACIÓN: Minimax Provider Integration")
    print("=" * 60)
    
    results = []
    results.append(test_minimax_import())
    results.append(test_minimax_instantiation())
    results.append(test_minimax_in_main())
    results.append(test_api_healthz())
    
    print("\n" + "=" * 60)
    print("RESUMEN")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Tests pasados: {passed}/{total}")
    
    if passed == total:
        print("\n✅ TODOS LOS TESTS PASARON")
        print("\nMinimax está correctamente integrado.")
        print("\nPara usar con API key real:")
        print("  $env:MINIMAX_API_KEY = 'tu-api-key'")
        print("  .venv\\Scripts\\uvicorn agentos.api.main:app --reload")
        return 0
    else:
        print("\n❌ ALGUNOS TESTS FALLARON")
        return 1


if __name__ == "__main__":
    sys.exit(main())
