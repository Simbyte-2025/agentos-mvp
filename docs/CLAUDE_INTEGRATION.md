# Claude LLM Integration - AgentOS

## ✅ Completado

Se ha integrado exitosamente **Claude como LLM provider** en AgentOS, reemplazando Minimax/Dummy.

## Cambios Realizados

### 1. Nuevo archivo: `agentos/llm/claude.py`
- Clase `ClaudeClient` que implementa la interfaz `LLMClient`
- Usa el SDK de Anthropic con soporte para custom endpoints
- Soporta `ANTHROPIC_API_KEY` y `ANTHROPIC_BASE_URL` desde env vars

### 2. Actualización: `agentos/llm/__init__.py`
- Exporta `ClaudeClient` junto a `MinimaxClient` y `LLMClient`

### 3. Actualización: `agentos/api/main.py`
- Agregado `elif llm_provider == "claude"` en el selector de LLM
- Lee variables de entorno:
  - `ANTHROPIC_API_KEY` (obligatorio para uso real)
  - `ANTHROPIC_BASE_URL` (opcional, usa default si omitido)
  - `CLAUDE_MODEL` (default: `claude-opus-4-6`)

### 4. Actualización: `requirements.txt`
- Agregado `anthropic>=0.7.0`

## Como Usar

### Opción 1: Servidor HTTP

```bash
cd agentos-mvp-main
pip install -r requirements.txt

# Arrancar servidor con Claude como LLM
AGENTOS_ORCHESTRATOR=planner \
AGENTOS_LLM_PROVIDER=claude \
ANTHROPIC_API_KEY=sk-your-key-here \
ANTHROPIC_BASE_URL=https://aiprime.store \
uvicorn agentos.api.main:app --host 127.0.0.1 --port 8080
```

**Endpoints disponibles:**
- `GET /healthz` - Estado del sistema
- `POST /run` - Ejecutar tarea (usa PlannerExecutorOrchestrator con Claude)
- `POST /builder/scaffold` - Generar scaffold de agente/tool
- `POST /builder/apply` - Aplicar archivos generados

**Ejemplo de request:**
```bash
curl -X POST http://localhost:8080/run \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Crear agente WebScraper: scraping de noticias tecnológicas",
    "session_id": "s1",
    "user_id": "u1"
  }'
```

### Opción 2: Python directo

```python
import os
os.environ["AGENTOS_ORCHESTRATOR"] = "planner"
os.environ["AGENTOS_LLM_PROVIDER"] = "claude"
os.environ["ANTHROPIC_API_KEY"] = "sk-..."
os.environ["ANTHROPIC_BASE_URL"] = "https://aiprime.store"

from agentos.llm.claude import ClaudeClient

client = ClaudeClient(
    api_key="sk-...",
    base_url="https://aiprime.store",
    model="claude-opus-4-6"
)

response = client.generate("Tu prompt aquí")
print(response)
```

## Variables de Entorno

| Variable | Requerido | Default | Descripción |
|----------|-----------|---------|-------------|
| `AGENTOS_ORCHESTRATOR` | Sí | `sequential` | Usar `planner` para activar Claude |
| `AGENTOS_LLM_PROVIDER` | Sí (si orchestrator=planner) | - | Usar `claude` |
| `ANTHROPIC_API_KEY` | Sí (para uso real) | - | Tu API key de Anthropic |
| `ANTHROPIC_BASE_URL` | No | API Anthropic default | URL custom (ej: https://aiprime.store) |
| `CLAUDE_MODEL` | No | `claude-opus-4-6` | Modelo a usar |

## Flujo de Ejecución

```
POST /run
    ↓
PlannerExecutorOrchestrator
    ↓
ClaudeClient.generate(prompt)  ← Claude genera plan
    ↓
Ejecuta agentes especializados (ResearcherAgent, WriterAgent, etc.)
    ↓
Resultado final
```

## Testing

Se incluye `test_claude_integration.py`:

```bash
source venv/bin/activate
python test_claude_integration.py
```

Prueba:
1. ✅ Endpoint `/healthz`
2. ✅ BuilderAgent vía `/run` (crea nuevo agente)
3. ✅ Inicialización de ClaudeClient
4. ✅ Generación de respuestas con Claude

## Notas Técnicas

### ClaudeClient implementa:
- Interfaz `LLMClient.generate(prompt: str) -> str`
- Soporte para custom base_url (Anthropic-compatible)
- Manejo robusto de errores
- Logging estructurado

### Compatible con:
- Anthropic API estándar
- Endpoints Anthropic-compatible (como https://aiprime.store)
- Cualquier modelo de Claude (via variable `CLAUDE_MODEL`)

### Diferencias con MinimaxClient:
- Usa SDK oficial `anthropic` en vez de HTTP directo
- Soporte nativo para custom endpoints via parámetro `base_url`
- Mejor manejo de errores y autenticación

## Próximos Pasos (Opcional)

1. **Agregar más opciones de configuración:**
   - `CLAUDE_MAX_TOKENS` - Controlar max_tokens en generate()
   - `CLAUDE_TEMPERATURE` - Soporte para temperatura

2. **Caching de planes:**
   - Cache Redis o en-memory de planes generados

3. **Streaming responses:**
   - Soporte para streaming de respuestas largas

4. **Métricas:**
   - Track de tokens usados, latencias, etc.
