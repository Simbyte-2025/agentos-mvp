# ADR: Planner-Executor Orchestrator

## Contexto

El sistema AgentOS MVP necesita capacidades de orquestación más sofisticadas para manejar tareas complejas que requieren:

1. **Descomposición de tareas**: Dividir tareas complejas en subtareas ejecutables
2. **Replanificación**: Adaptar el plan cuando las subtareas fallan
3. **Observabilidad**: Tracking detallado de la ejecución de cada subtarea
4. **Flexibilidad**: Soporte para diferentes proveedores LLM sin acoplamiento

El orquestador secuencial existente es adecuado para tareas simples, pero no puede manejar escenarios que requieren planificación dinámica.

## Decisión

Implementar un **Planner-Executor Orchestrator** con las siguientes características:

### 1. Abstracción LLM
- Interfaz `LLMClient` abstracta con método `generate(prompt: str) -> str`
- Desacopla el orquestador de proveedores LLM específicos (OpenAI, Anthropic, etc.)
- `DummyLLM` para testing con respuestas deterministas

### 2. Arquitectura Planner-Executor
- **Planner**: Genera plan inicial con subtareas en formato JSON
- **Executor**: Ejecuta cada subtarea usando `AgentRouter` y `ToolRouter`
- **Replanner**: Genera nuevo plan cuando subtareas fallan

### 3. Límites de Seguridad
- `MAX_REPLANS = 2`: Máximo 2 replanificaciones por tarea
- `MAX_RETRIES_PER_TASK = 2`: Máximo 2 reintentos por subtarea
- Previene loops infinitos y uso excesivo de LLM

### 4. Parsing Robusto
- Validación JSON con `try/except` y verificación de estructura
- Validación de campos requeridos: `id`, `objetivo`, `criterios_exito`
- **Fallback graceful**: Si el parsing falla, ejecuta la tarea como una sola subtarea
- Logging detallado de errores de parsing

### 5. Feature Flags
- `AGENTOS_ORCHESTRATOR`: `sequential` (default) | `planner`
- `AGENTOS_LLM`: `dummy` | otros (futuro: `openai`, `anthropic`, etc.)
- **Fallback automático**: Si `AGENTOS_ORCHESTRATOR=planner` pero no hay LLM configurado, usa sequential
- Mantiene compatibilidad con sistema existente

### 6. Observabilidad
- Logging estructurado por `request_id`
- Tracking de status por subtarea: `pending`, `running`, `success`, `failed`
- Registro de tool calls, errores, y retry counts
- Checkpoint en `WorkingStateStore` con metadata completa

## Alternativas consideradas

### A. Hardcodear prompts vs. Abstracción LLM
**Rechazada**: Hardcodear prompts directamente en el orquestador
- ❌ Acopla el código a un proveedor específico
- ❌ Dificulta testing (requiere mocks complejos)
- ✅ **Seleccionada**: Abstracción LLM permite testabilidad y flexibilidad

### B. Biblioteca externa vs. Implementación propia
**Rechazada**: Usar biblioteca como LangChain o LlamaIndex
- ❌ Agrega dependencias pesadas
- ❌ Introduce complejidad innecesaria para MVP
- ❌ Dificulta control sobre seguridad y permisos
- ✅ **Seleccionada**: Implementación propia mantiene control y simplicidad

### C. Replanificación ilimitada vs. Límites
**Rechazada**: Permitir replanificación ilimitada
- ❌ Riesgo de loops infinitos
- ❌ Costos de LLM incontrolados
- ❌ Timeout de requests
- ✅ **Seleccionada**: Límites configurables (`MAX_REPLANS`, `MAX_RETRIES_PER_TASK`)

### D. Error estricto vs. Fallback graceful
**Rechazada**: Fallar inmediatamente si el LLM retorna JSON inválido
- ❌ Fragilidad ante errores de LLM
- ❌ Mala experiencia de usuario
- ✅ **Seleccionada**: Fallback a ejecución como tarea única mantiene disponibilidad

### E. DummyLLM por defecto vs. Configuración explícita
**Rechazada**: Usar DummyLLM por defecto en runtime
- ❌ No es útil en producción (respuestas genéricas)
- ❌ Confusión sobre estado del sistema
- ✅ **Seleccionada**: DummyLLM solo con `AGENTOS_LLM=dummy` o en tests

## Consecuencias

### Positivas
- ✅ **Flexibilidad**: Soporte para múltiples proveedores LLM sin cambios en el orquestador
- ✅ **Testabilidad**: DummyLLM permite tests deterministas sin LLM real
- ✅ **Robustez**: Parsing con validación y fallback previene fallos catastróficos
- ✅ **Observabilidad**: Logging estructurado facilita debugging y monitoring
- ✅ **Compatibilidad**: Feature flags mantienen sistema existente funcionando
- ✅ **Seguridad**: Límites previenen loops infinitos y uso excesivo de recursos
- ✅ **Sin dependencias**: No requiere bibliotecas adicionales

### Negativas
- ⚠️ **Complejidad**: Más código que mantener vs. orquestador secuencial
- ⚠️ **Configuración**: Requiere configurar LLM en producción (no incluido en MVP)
- ⚠️ **Costos**: Uso de LLM genera costos por API calls
- ⚠️ **Latencia**: Planificación agrega latencia vs. ejecución directa
- ⚠️ **Calidad del plan**: Depende de la calidad del LLM (garbage in, garbage out)

### Mitigaciones
- **Complejidad**: Tests exhaustivos y documentación clara
- **Configuración**: Fallback automático a sequential si no hay LLM
- **Costos**: Límites de replanificación y caching futuro
- **Latencia**: Usar planner solo para tareas complejas (feature flag)
- **Calidad**: Validación robusta de JSON y fallback graceful

## Estado

**Aprobada** - Implementado en AgentOS MVP

## Notas de Implementación

- Formato JSON del plan:
  ```json
  {
    "subtasks": [
      {
        "id": "1",
        "objetivo": "descripción de la subtarea",
        "criterios_exito": ["criterio 1", "criterio 2"]
      }
    ]
  }
  ```

- Estructura de `Subtask`:
  - `id`: Identificador único
  - `objetivo`: Descripción de la subtarea
  - `criterios_exito`: Lista de criterios de éxito
  - `status`: `pending` | `running` | `success` | `failed`
  - `retry_count`: Contador de reintentos
  - `tool_calls`: Lista de llamadas a herramientas
  - `error`: Mensaje de error si falla

- El orquestador reutiliza `AgentRouter` y `ToolRouter` existentes para mantener consistencia con el sistema actual

## Referencias

- `agentos/llm/base.py`: Interfaz LLMClient
- `agentos/llm/dummy.py`: Implementación DummyLLM
- `agentos/orchestrators/planner_executor.py`: Implementación del orquestador
- `tests/unit/test_planner_executor.py`: Tests unitarios
- `tests/integration/test_run_planner_smoke.py`: Test de integración
