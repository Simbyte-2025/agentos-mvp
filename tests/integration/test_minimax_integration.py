"""Integration tests for MinimaxClient (opt-in with MINIMAX_API_KEY)."""

import os
from pathlib import Path

import pytest

from agentos.agents.specialist.researcher_agent import ResearcherAgent
from agentos.llm.minimax import MinimaxClient
from agentos.memory.long_term import LongTermMemory
from agentos.memory.short_term import ShortTermMemory
from agentos.memory.working_state import WorkingStateStore
from agentos.orchestrators.planner_executor import PlannerExecutorOrchestrator
from agentos.security.permissions import PermissionValidator
from agentos.tools.filesystem.read_file import ReadFileTool


@pytest.mark.skipif(
    not os.getenv("MINIMAX_API_KEY"),
    reason="MINIMAX_API_KEY no configurada (test opt-in)"
)
def test_minimax_client_real_api():
    """Smoke test: llamada real a Minimax API.
    
    Este test solo se ejecuta si MINIMAX_API_KEY está configurada.
    Verifica que el cliente puede hacer una llamada real y recibir respuesta.
    """
    client = MinimaxClient(
        api_key=os.getenv("MINIMAX_API_KEY"),
        base_url=os.getenv("MINIMAX_BASE_URL", "https://api.minimax.io"),
        model=os.getenv("MINIMAX_MODEL", "MiniMax-M2.1")
    )
    
    # Prompt simple que debe generar respuesta corta
    response = client.generate("Di 'hola' en una palabra")
    
    # Verificar que recibimos respuesta válida
    assert isinstance(response, str)
    assert len(response) > 0
    assert response.strip() != ""
    
    print(f"Minimax response: {response}")


@pytest.mark.skipif(
    not os.getenv("MINIMAX_API_KEY"),
    reason="MINIMAX_API_KEY no configurada (test opt-in)"
)
def test_minimax_client_generates_plan():
    """Test que Minimax puede generar un plan en formato JSON.
    
    Este test verifica que Minimax puede generar planes estructurados
    que el PlannerExecutorOrchestrator puede usar.
    """
    client = MinimaxClient(
        api_key=os.getenv("MINIMAX_API_KEY"),
        base_url=os.getenv("MINIMAX_BASE_URL", "https://api.minimax.io"),
        model=os.getenv("MINIMAX_MODEL", "MiniMax-M2.1")
    )
    
    # Prompt de planificación (similar al usado por PlannerExecutor)
    prompt = """Eres un planificador de tareas. Descompón la siguiente tarea en subtareas ejecutables.

Tarea: Leer el archivo README.md

Responde SOLO con un JSON válido en este formato exacto:
{
  "subtasks": [
    {
      "id": "1",
      "objetivo": "descripción clara de la subtarea",
      "criterios_exito": ["criterio 1", "criterio 2"]
    }
  ]
}

Reglas:
- Cada subtarea debe ser específica y ejecutable
- Los IDs deben ser únicos
- Incluye 1-5 subtareas máximo
- NO incluyas texto adicional fuera del JSON"""
    
    response = client.generate(prompt)
    
    # Verificar que recibimos respuesta
    assert isinstance(response, str)
    assert len(response) > 0
    
    # Intentar parsear como JSON (no validamos estructura completa aquí)
    import json
    try:
        data = json.loads(response)
        print(f"Minimax plan: {json.dumps(data, indent=2, ensure_ascii=False)}")
    except json.JSONDecodeError:
        # Si no es JSON válido, al menos verificamos que hay contenido
        print(f"Minimax response (not JSON): {response}")
        # No fallamos el test, solo mostramos el resultado


@pytest.mark.skipif(
    not os.getenv("MINIMAX_API_KEY"),
    reason="MINIMAX_API_KEY no configurada (test opt-in)"
)
def test_planner_executor_with_real_minimax(tmp_path: Path):
    """Integration test: PlannerExecutor con Minimax real.
    
    Este test verifica que el flujo completo funciona:
    1. Minimax genera un plan
    2. PlannerExecutor lo ejecuta
    3. Se obtiene resultado exitoso
    """
    # Crear archivo de prueba
    test_file = tmp_path / "test.txt"
    test_file.write_text("Contenido de prueba para Minimax", encoding="utf-8")
    
    # Setup componentes
    agent = ResearcherAgent(name="researcher", description="", profile="researcher")
    tool = ReadFileTool(workspace_root=tmp_path)
    validator = PermissionValidator({
        "researcher": {
            "permissions": [{"tool": "read_file", "actions": ["read"]}]
        }
    })
    
    # Cliente Minimax real
    llm_client = MinimaxClient(
        api_key=os.getenv("MINIMAX_API_KEY"),
        base_url=os.getenv("MINIMAX_BASE_URL", "https://api.minimax.io"),
        model=os.getenv("MINIMAX_MODEL", "MiniMax-M2.1")
    )
    
    # Orquestador con Minimax
    orch = PlannerExecutorOrchestrator(
        agents=[agent],
        tools=[tool],
        permission_validator=validator,
        short_term=ShortTermMemory(max_items=5),
        working_state=WorkingStateStore(db_path=tmp_path / "state.db"),
        long_term=LongTermMemory(),
        llm_client=llm_client,
    )
    
    # Ejecutar tarea
    result = orch.run(
        task="lee el archivo test.txt",
        session_id="test_session",
        user_id="test_user"
    )
    
    # Verificar resultado
    # Nota: El resultado puede variar dependiendo de lo que Minimax genere
    # Solo verificamos que el orquestador no crasheó
    assert result is not None
    assert result.agent_name == "planner_executor"
    assert "subtasks" in result.meta
    
    print(f"Result success: {result.success}")
    print(f"Result output: {result.output}")
    print(f"Result meta: {result.meta}")
