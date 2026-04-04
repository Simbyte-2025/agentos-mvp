# Minimax LLM Provider - Implementación Completa

## Resumen Ejecutivo

✅ **Minimax integrado exitosamente** como proveedor LLM para AgentOS MVP.
✅ **API inicia sin API key** - errores controlados en runtime
✅ **pytest -q: 71 passed, 8 skipped** - todos los tests pasando
✅ **No se expone MINIMAX_API_KEY** en logs

---

## Archivos Modificados/Creados

### Nuevos (3 archivos)
1. **`agentos/llm/minimax.py`** (174 líneas)
   - Clase `MinimaxClient(LLMClient)` con HTTP client usando `httpx`
   - Manejo robusto de errores (timeout, HTTP 401/429/500, JSON inválido)
   - Logging seguro (nunca expone API key)
   - Puede instanciarse sin API key (errores deferred a runtime)

2. **`tests/unit/test_minimax_client.py`** (13 tests)
   - Tests con mocks (sin llamadas de red)
   - Cobertura: success, timeout, HTTP errors, JSON parsing, seguridad

3. **`tests/integration/test_minimax_integration.py`** (3 tests opt-in)
   - Solo ejecutan si `MINIMAX_API_KEY` está configurada
   - Smoke tests con API real de Minimax

### Modificados (2 archivos)
1. **`agentos/llm/__init__.py`**
   - Exporta `MinimaxClient`

2. **`agentos/api/main.py`** (líneas 71-138)
   - Selección de proveedor LLM por env vars
   - Backward compatible con `AGENTOS_LLM`
   - API inicia incluso sin `MINIMAX_API_KEY` (warning en log)

---

## Dónde Estaba el Placeholder

### Hallazgo
**Archivo**: `agentos/agents/specialist/researcher_agent.py`
**Líneas**: 52-54
**Texto**: `"En un sistema real, aquí se usaría un LLM + tool router para planificar y ejecutar."`

### Contexto Importante
Este placeholder es el **fallback del ResearcherAgent** cuando no encuentra herramientas que coincidan con heurísticas. 

**NO es el punto principal de integración** porque:
- El flujo real de `/run` usa `PlannerExecutorOrchestrator` cuando `AGENTOS_ORCHESTRATOR=planner`
- El orquestador llama a `llm_client.generate()` en `planner_executor.py:257`
- **Minimax ya está integrado ahí** via la selección de provider en `main.py`

### Cómo se Reemplazó
El placeholder se reemplaza **indirectamente**:
1. Usuario configura `AGENTOS_ORCHESTRATOR=planner` + `AGENTOS_LLM_PROVIDER=minimax`
2. `main.py` instancia `MinimaxClient` y lo pasa a `PlannerExecutorOrchestrator`
3. El orquestador usa Minimax para generar planes (NO el fallback del agente)
4. El placeholder solo se ve si el orquestador falla completamente

---

## Configuración de Environment Variables

### Variables Requeridas
```powershell
# Activar orquestador planner (obligatorio para usar LLM)
$env:AGENTOS_ORCHESTRATOR = "planner"

# Seleccionar proveedor Minimax
$env:AGENTOS_LLM_PROVIDER = "minimax"
# O backward compatible:
$env:AGENTOS_LLM = "minimax"

# API Key de Minimax (obligatorio para llamadas reales)
$env:MINIMAX_API_KEY = "tu-api-key-aqui"
```

### Variables Opcionales
```powershell
# Base URL (default: https://api.minimax.io)
$env:MINIMAX_BASE_URL = "https://api.minimax.io"

# Modelo (default: MiniMax-M2.1)
$env:MINIMAX_MODEL = "MiniMax-M2.1"
```

---

## Instrucciones de Prueba Local

### Validación Rápida (Import Check)

Para verificar que MinimaxClient se importa correctamente (sin llamadas de red):

```powershell
python tests\manual\minimax_verify_import.py
```

⚠️ **Nota**: Este script solo verifica imports, NO hace llamadas reales a Minimax.

### Validación Real (Smoke Test con API)

Para validar con llamadas reales a Minimax API:

```powershell
# 1. Configurar variables de entorno
$env:AGENTOS_ORCHESTRATOR = "planner"
$env:AGENTOS_LLM_PROVIDER = "minimax"
$env:MINIMAX_API_KEY = "tu-api-key-aqui"

# 2. Ejecutar smoke test automatizado
.\tests\manual\minimax_api_smoke.ps1
```

El script smoke test:
1. Valida que estás en la raíz del repo
2. Verifica que .venv existe
3. Valida env vars requeridas
4. Te pide que levantes uvicorn en otra ventana
5. Ejecuta POST /run con Minimax
6. Valida que la respuesta NO contiene el placeholder

### Prueba Manual Paso a Paso


```powershell
# Configurar variables (SIN exponer la key en comandos)
$env:AGENTOS_ORCHESTRATOR = "planner"
$env:AGENTOS_LLM_PROVIDER = "minimax"
$env:MINIMAX_API_KEY = "sk-..."  # Tu API key real

# Iniciar servidor
.\.venv\Scripts\uvicorn agentos.api.main:app --reload
```

**Verificar en logs**:
```
INFO: Using MinimaxClient for planner orchestrator
INFO: Using PlannerExecutorOrchestrator
```

### 2. Probar POST /run

```powershell
# En otra terminal PowerShell
curl -X POST http://localhost:8000/run `
  -H "Content-Type: application/json" `
  -H "X-API-Key: test-key" `
  -d '{
    "task": "Explica qué es Python en una frase corta",
    "session_id": "test-session",
    "user_id": "test-user"
  }'
```

**Respuesta esperada**:
```json
{
  "agent": "planner_executor",
  "success": true,
  "output": "Python es un lenguaje de programación...",
  "error": null,
  "meta": {
    "subtasks": [...],
    "replan_count": 0
  }
}
```

**Verificar**: El `output` ya NO contiene el placeholder "En un sistema real...". Contiene texto generado por Minimax.

### 3. Probar sin API Key (error controlado)

```powershell
# Remover API key
Remove-Item Env:\MINIMAX_API_KEY

# Reiniciar servidor
.\.venv\Scripts\uvicorn agentos.api.main:app --reload
```

**Verificar en logs**:
```
WARNING: MinimaxClient configured but MINIMAX_API_KEY not set. 
API will start but /run requests will fail with clear error message.
```

**Hacer request a /run**:
```powershell
curl -X POST http://localhost:8000/run ...
```

**Respuesta esperada** (HTTP 200 pero success=false):
```json
{
  "agent": "planner_executor",
  "success": false,
  "output": "",
  "error": "MINIMAX_API_KEY no configurada. Configure la variable de entorno...",
  "meta": {...}
}
```

---

## Tests

### Ejecutar todos los tests
```powershell
pytest -q
```

**Output esperado**:
```
71 passed, 8 skipped, 1 warning in ~9s
```

### Ejecutar solo tests de Minimax
```powershell
# Unit tests (sin red)
pytest tests/unit/test_minimax_client.py -v

# Integration tests (requiere MINIMAX_API_KEY)
$env:MINIMAX_API_KEY = "sk-..."
pytest tests/integration/test_minimax_integration.py -v
```

---

## Comportamiento por Configuración

| ORCHESTRATOR | LLM_PROVIDER | MINIMAX_API_KEY | Comportamiento |
|--------------|--------------|-----------------|----------------|
| `sequential` | (cualquiera) | (cualquiera) | No usa LLM, puede mostrar placeholder en fallback |
| `planner` | (vacío) | (cualquiera) | Fallback a sequential, warning en log |
| `planner` | `dummy` | (cualquiera) | Usa DummyLLM (respuestas deterministas) |
| `planner` | `minimax` | ❌ No configurada | API inicia, /run falla con error claro |
| `planner` | `minimax` | ✅ Configurada | **Usa Minimax real** |

---

## Seguridad

✅ **API Key nunca se loggea**: Verificado con test `test_minimax_client_does_not_log_api_key`
✅ **API no crashea sin key**: Servidor inicia, errores en runtime
✅ **Timeout configurado**: 30s por defecto (previene hang)
✅ **Errores específicos**: HTTP 401 (key inválida), 429 (rate limit), 500 (server error)

---

## Limitaciones Conocidas (MVP)

❌ **Sin retry automático**: Rate limits (HTTP 429) no se reintentan
❌ **Sin streaming**: Solo respuestas completas
❌ **Timeout fijo**: 30s hardcoded (no configurable via env var)
⚠️ **Proxy corporativo**: Puede requerir configurar `HTTP_PROXY`/`HTTPS_PROXY`

---

## Próximos Pasos (Fuera de Scope MVP)

1. Agregar `MINIMAX_TIMEOUT_S` env var
2. Implementar retry con backoff usando `tenacity`
3. Agregar streaming support
4. Crear ADR_005_minimax_integration.md
5. Actualizar README.md con sección Minimax
