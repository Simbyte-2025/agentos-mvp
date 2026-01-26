# ADR: Minimax LLM Integration

## Contexto

AgentOS MVP necesita un proveedor LLM real para ejecutar tareas que requieren generación de texto, planificación y razonamiento. El sistema fue diseñado con una abstracción `LLMClient` (ADR-001) que permite intercambiar proveedores sin cambiar el código del orquestador.

Se seleccionó Minimax como proveedor inicial por:
1. API compatible con formato Anthropic Messages
2. Modelo MiniMax-M2.1 con buen balance costo/rendimiento
3. Disponibilidad de API key para desarrollo

## Decisión

Implementar `MinimaxClient` como cliente LLM de producción para AgentOS MVP.

### 1. Arquitectura del Cliente

```python
class MinimaxClient(LLMClient):
    def __init__(
        self,
        api_key: Optional[str] = None,  # Puede ser None (graceful degradation)
        base_url: str = "https://api.minimax.io/anthropic",
        model: str = "MiniMax-M2.1",
        timeout: int = 30,
    )
```

- **Antropic-compatible**: Usa `/v1/messages` con headers `x-api-key` y `anthropic-version`
- **API key opcional en constructor**: Permite instanciar sin key (errores en runtime, no en startup)
- **Configurable por ENV**: `MINIMAX_API_KEY`, `MINIMAX_BASE_URL`, `MINIMAX_MODEL`

### 2. Manejo de Errores Robusto

El cliente implementa logging defensivo para diagnóstico sin exponer secretos:

- **Logging de respuestas**: Status code, content-type, body truncado (800 chars)
- **Parsing JSON defensivo**: Captura errores de parsing con contexto
- **Errores estructurados**: Distingue timeout, HTTP errors, JSON errors, errores lógicos
- **API key nunca se loggea**: Headers se construyen sin logging del valor

### 3. Graceful Degradation

```
AGENTOS_LLM_PROVIDER=minimax (sin MINIMAX_API_KEY)
  → API inicia OK
  → /run devuelve error claro: "MINIMAX_API_KEY no configurada"
```

Esto permite que:
- La API esté disponible para health checks
- Otros endpoints funcionen
- El error sea específico y actionable

### 4. Feature Flags

| Variable | Valores | Default | Descripción |
|----------|---------|---------|-------------|
| `AGENTOS_LLM_PROVIDER` | `minimax`, `dummy` | (vacío) | Selecciona cliente LLM |
| `AGENTOS_LLM` | (legacy) | (vacío) | Fallback si `AGENTOS_LLM_PROVIDER` no existe |
| `MINIMAX_API_KEY` | string | (ninguno) | API key de Minimax |
| `MINIMAX_BASE_URL` | URL | `https://api.minimax.io/anthropic` | Endpoint base |
| `MINIMAX_MODEL` | string | `MiniMax-M2.1` | Modelo a usar |

### 5. Integración con Agentes

Los agentes ahora reciben `llm_client` en su contexto:

```python
# En planner_executor.py
ctx = AgentContext(
    ...
    memory={
        ...
        "llm_client": self.llm_client,  # Inyectado
    }
)
```

Esto elimina los mensajes "placeholder" en `ResearcherAgent` y `WriterAgent`.

## Alternativas Consideradas

### A. OpenAI GPT vs. Minimax
**No seleccionada**: OpenAI tiene mayor latencia para algunos casos de uso y el formato de API es diferente. Minimax ofrece compatibilidad Anthropic que simplifica la implementación.

### B. Anthropic Claude vs. Minimax
**No seleccionada**: Claude requiere acuerdos comerciales adicionales. Minimax provee API compatible sin overhead administrativo.

### C. Fail-fast sin API key vs. Graceful degradation
**No seleccionada**: Fail-fast bloquearía el startup de la API. Graceful degradation permite debugging y desarrollo parcial.

### D. Logging completo de requests vs. Logging seguro
**Seleccionada**: Logging seguro que nunca incluye API keys, pero sí incluye suficiente contexto (status, body truncado) para diagnóstico.

## Consecuencias

### Positivas

- ✅ **LLM real funcional**: `/run` produce respuestas generadas por IA
- ✅ **Sin placeholders**: Agentes usan LLM cuando herramientas no aplican
- ✅ **Diagnosticable**: Logging estructurado para debugging
- ✅ **Seguro**: API key nunca expuesta en logs
- ✅ **Flexible**: Configurable por ENV sin changes de código
- ✅ **Resiliente**: API inicia sin key, errores claros en runtime

### Negativas

- ⚠️ **Dependencia externa**: Requiere conectividad a Minimax API
- ⚠️ **Costos**: Uso de API genera costos por tokens
- ⚠️ **Latencia**: Llamadas de red agregan latencia (~1-3s por request)

### Mitigaciones

- **Dependencia**: DummyLLM disponible para tests y desarrollo offline
- **Costos**: Límites en `MAX_REPLANS` y `MAX_RETRIES_PER_TASK`
- **Latencia**: Futuro: agregar caching para prompts repetitivos

## Estado

**Aprobada** - Implementado y validado en AgentOS MVP

## Referencias

- `agentos/llm/minimax.py`: Implementación del cliente
- `agentos/llm/base.py`: Interfaz `LLMClient`
- `tests/unit/test_minimax_client.py`: Tests unitarios (13 tests)
- `tests/integration/test_minimax_integration.py`: Tests de integración
- `tests/manual/minimax_api_smoke.ps1`: Smoke test con API real
- `ENTREGA_MINIMAX.md`: Documentación de entrega
- `MINIMAX_IMPLEMENTATION.md`: Guía de implementación detallada
