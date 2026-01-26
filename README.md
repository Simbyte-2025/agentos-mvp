# AgentOS MVP

Sistema de orquestación de agentes con mínimo privilegio y aislamiento de herramientas.

## Características

- **Orquestación**: Planner-Executor con replanning automático
- **Seguridad**: Principio de mínimo privilegio, permisos explícitos por herramienta
- **Herramientas**: Sistema extensible con validación de permisos
- **API REST**: FastAPI con endpoints para ejecución de agentes

## Estructura del Proyecto

```
agentos_mvp/
├── agentos/
│   ├── orchestrator/      # Planner-Executor orchestrator
│   ├── tools/             # Herramientas disponibles
│   │   ├── filesystem/    # read_file
│   │   ├── http/          # http_fetch
│   │   └── exec/          # run_command (secure execution)
│   ├── security/          # Validación de permisos y allowlists
│   └── api/               # FastAPI endpoints
├── config/
│   ├── tools.yaml         # Configuración de herramientas
│   └── profiles.yaml      # Perfiles de permisos por agente
├── docs/                  # ADRs y especificaciones
└── tests/                 # Unit + integration tests
```

## Quickstart

### 1. Instalar dependencias

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

### 2. Ejecutar tests

```powershell
.\.venv\Scripts\pytest -v
```

### 3. Iniciar API

```powershell
.\.venv\Scripts\uvicorn agentos.api.main:app --reload
```

### 4. Health check

```powershell
curl http://localhost:8000/healthz
```

## Probar Minimax (MVP)

AgentOS MVP soporta **Minimax AI** como proveedor LLM para el orquestador Planner-Executor.

### Paso 1: Configurar Variables de Entorno

```powershell
# Activar orquestador planner (obligatorio para usar LLM)
$env:AGENTOS_ORCHESTRATOR = "planner"

# Seleccionar proveedor Minimax
$env:AGENTOS_LLM_PROVIDER = "minimax"

# API Key de Minimax (obligatorio para llamadas reales)
$env:MINIMAX_API_KEY = "tu-api-key-aqui"

# (Opcional) Base URL y modelo
$env:MINIMAX_BASE_URL = "https://api.minimax.io"  # default
$env:MINIMAX_MODEL = "MiniMax-M2.1"  # default
```

**⚠️ Seguridad**: NO commitear `MINIMAX_API_KEY` en código. Usar variables de entorno.

### Paso 2: Iniciar API

```powershell
# En la raíz del proyecto
.\.venv\Scripts\uvicorn agentos.api.main:app --host 127.0.0.1 --port 8080
```

**Verificar en logs**:
```
INFO: Using MinimaxClient for planner orchestrator
INFO: Using PlannerExecutorOrchestrator
```

### Paso 3: Probar POST /run

```powershell
# En otra terminal PowerShell
curl -X POST http://127.0.0.1:8080/run `
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
  "output": "Python es un lenguaje de programación de alto nivel...",
  "meta": {
    "subtasks": [...],
    "replan_count": 0
  }
}
```

✅ **Validación**: El campo `output` debe contener texto generado por Minimax (NO el placeholder "En un sistema real...").

### Smoke Test Automatizado

Para validación completa con script automatizado:

```powershell
# Configurar env vars primero (ver Paso 1)
.\tests\manual\minimax_api_smoke.ps1
```

El script:
- Valida configuración de env vars
- Verifica que el servidor responde
- Ejecuta POST /run
- Valida que la respuesta NO contiene el placeholder

Ver documentación completa en: [`MINIMAX_IMPLEMENTATION.md`](MINIMAX_IMPLEMENTATION.md)

## Herramientas Disponibles


### `run_command` - Ejecución Segura de Comandos

**⚠️ IMPORTANTE: Deshabilitado por defecto. Requiere permiso `execute` explícito.**

Ejecuta comandos del sistema con **8 capas de seguridad**:

1. **Allowlist estricta**: Solo `python`, `pytest`, `dir`, `type` por defecto
2. **Bloqueo de operadores shell**: `&&`, `||`, `;`, `|`, `>`, `<`, `$`, `` ` ``
3. **`shell=False` obligatorio**: Sin interpretación de shell
4. **Validación de Python args**: Bloquea `-c`, `-m`, `-` (code injection)
5. **Path traversal prevention**: `cwd` confinado al workspace
6. **Timeout estricto**: Default 30s, máximo 300s
7. **Tempdir isolation (sandbox)**: Directorio temporal aislado
8. **Permisos explícitos**: Solo agentes con `execute` permission

#### Configuración de Permisos

Por defecto, **NINGÚN agente** tiene permiso `execute`. Solo `builder_agent`:

```yaml
# config/profiles.yaml
builder_agent:
  permissions:
    - tool: run_command
      actions: [execute]
```

#### Ejemplos de Uso

**Ejecutar script Python:**

```python
from agentos.tools.exec.run_command import RunCommandTool
from agentos.tools.base import ToolInput

tool = RunCommandTool()
result = tool.execute(ToolInput(
    request_id="req_001",
    payload={
        "command": "python",
        "args": ["script.py"],
        "timeout_s": 60
    }
))

print(result.data["stdout"])  # Output truncado a 10KB
print(result.data["exit_code"])
```

**Modo Sandbox (tempdir isolation):**

```python
result = tool.execute(ToolInput(
    request_id="req_002",
    payload={
        "command": "python",
        "args": ["--version"],
        "sandbox": True  # Ejecuta en directorio temporal aislado
    }
))
```

**⚠️ Limitaciones del Sandbox en Windows:**

El modo `sandbox: true` proporciona **tempdir isolation**, NO aislamiento real:
- ✅ Ejecuta en directorio temporal
- ✅ Variables de entorno limitadas
- ❌ **NO bloquea acceso a red**
- ❌ **NO limita CPU/memoria**
- ❌ **NO previene acceso a archivos del sistema**

Para aislamiento real, configure `AGENTOS_EXEC_BACKEND=docker` (requiere Docker). Ver [docs/TOOL_SPEC_run_command.md](docs/TOOL_SPEC_run_command.md).

#### Comandos Bloqueados

**Shell injection bloqueado:**

```python
# ❌ BLOQUEADO - Operador shell
tool.execute(ToolInput(payload={
    "command": "python",
    "args": ["script.py", "&&", "del", "*"]
}))
# Error: "Operador shell peligroso detectado en arg: '&&'"
```

**Python code injection bloqueado:**

```python
# ❌ BLOQUEADO - Python -c
tool.execute(ToolInput(payload={
    "command": "python",
    "args": ["-c", "import os; os.system('rm -rf /')"]
}))
# Error: "Python arg peligroso bloqueado: '-c'"

# ❌ BLOQUEADO - Python -m
tool.execute(ToolInput(payload={
    "command": "python",
    "args": ["-m", "http.server"]
}))
# Error: "Python arg peligroso bloqueado: '-m'"
```

**Comando no en allowlist:**

```python
# ❌ BLOQUEADO - No en allowlist
tool.execute(ToolInput(payload={
    "command": "rm",
    "args": ["-rf", "/"]
}))
# Error: "Comando 'rm' no está en allowlist. Permitidos: python, pytest, dir, type"
```

#### Configuración Avanzada

**Modificar allowlist (config/tools.yaml):**

```yaml
- name: run_command
  config:
    allowed_commands:
      - python
      - pytest
      - git  # Agregar comando adicional
    max_timeout_s: 300
    default_timeout_s: 30
```

**O via variable de entorno:**

```powershell
$env:AGENTOS_ALLOWED_COMMANDS = "python,pytest,git"
```

#### Documentación Técnica

- **ADR**: [docs/ADR_002_run_command_security.md](docs/ADR_002_run_command_security.md)
- **Tool Spec**: [docs/TOOL_SPEC_run_command.md](docs/TOOL_SPEC_run_command.md)
- **Threat Model**: [docs/threat_model.md](docs/threat_model.md)

## Memory

### Long-Term Memory (LTM)

AgentOS soporta backends de memoria configurables para persistencia y búsqueda de información histórica.

#### Backends Disponibles

| Backend | Storage | Persistencia | Dependencias |
|---------|---------|--------------|--------------|
| `naive` (default) | In-memory | ❌ Volátil | Ninguna |
| `chroma` | ChromaDB (SQLite) | ✅ Disco | `chromadb` (manual) |

**⚠️ Nota Fase 4.2.2**: Ambos backends usan **token-overlap** para búsqueda (no embeddings). Búsqueda semántica con embeddings se agregará en Fase 4.2.3+.

#### Configuración

**Activar backend ChromaDB:**

```powershell
# Instalar chromadb (opcional)
pip install chromadb

# Configurar backend
$env:AGENTOS_LTM_BACKEND = "chroma"

# (Opcional) Configurar directorio de persistencia
$env:AGENTOS_LTM_PERSIST_DIR = ".agentos_memory"
```

**Si chromadb no está instalado**: El sistema hace fallback automático a `naive` con warning.

#### Uso Básico

```python
from agentos.memory import LongTermMemory

# Crear instancia (lee AGENTOS_LTM_BACKEND)
memory = LongTermMemory()

# Agregar información
memory.add("Python es un lenguaje de programación", tags=["python", "tech"])
memory.add("JavaScript se usa para desarrollo web", tags=["javascript", "web"])

# Buscar información relevante
results = memory.retrieve("Python programación", top_k=5)

for item in results:
    print(f"- {item.text} (tags: {item.tags})")
```

#### Persistencia (ChromaDB)


Con `AGENTOS_LTM_BACKEND=chroma`, los datos persisten entre sesiones:

```powershell
# Ejecutar demo de persistencia con ChromaDB
$env:AGENTOS_LTM_BACKEND = "chroma"
.\.venv\Scripts\python tests\manual\ltm_persist_demo.py

# Primera ejecución: agrega datos
# Segunda ejecución: recupera datos persistidos
# Los datos sobreviven entre sesiones
```

Ver [`tests/manual/ltm_persist_demo.py`](tests/manual/ltm_persist_demo.py) para el código completo.


#### Tests de Memoria

```powershell
# Todos los tests (unit siempre corre, integration skip si no hay chromadb)
pytest -q

# Solo tests de backend selection (siempre pasan)
pytest tests/unit/test_ltm_backend_selection.py -v

# Solo tests de ChromaDB (requiere: pip install chromadb)
pytest tests/integration/test_ltm_chroma_backend.py -v
```

**Si ChromaDB no está instalado**: Integration tests se skipean automáticamente (no fallan).

#### Limitaciones Actuales (Fase 4.2.2)

- ❌ **Sin embeddings**: Búsqueda por token-overlap solamente
- ❌ **Sin búsqueda semántica**: No entiende sinónimos ni contexto
- ⚠️ **Límite de 1000 documentos** para retrieval (previene OOM)

Estas limitaciones se resolverán en Fase 4.2.3+ con embeddings reales.

#### Documentación Técnica

- **ADR**: [docs/ADR_004_long_term_memory.md](docs/ADR_004_long_term_memory.md)

## Seguridad

### Principio de Mínimo Privilegio

Cada herramienta tiene un nivel de riesgo (`read`, `write`, `delete`, `execute`):

- `read_file`: `risk: read`
- `http_fetch`: `risk: read`
- `run_command`: `risk: execute` ⚠️

Los agentes deben tener permisos explícitos en `config/profiles.yaml`.

### Validación de Permisos

```python
from agentos.security.permissions import PermissionValidator

validator = PermissionValidator("config/profiles.yaml")
decision = validator.validate_tool_access(
    profile_name="researcher_agent",
    tool_name="run_command",
    action="execute"
)
# decision.allowed = False (researcher no tiene execute)
```

## Desarrollo

### Ejecutar tests específicos

```powershell
# Unit tests
.\.venv\Scripts\pytest tests/unit/ -v

# Integration tests
.\.venv\Scripts\pytest tests/integration/ -v

# Tests de run_command
.\.venv\Scripts\pytest tests/unit/test_run_command.py -v
```

### Agregar nueva herramienta

1. Crear clase que herede de `BaseTool`
2. Implementar método `execute(tool_input: ToolInput) -> ToolOutput`
3. Registrar en `config/tools.yaml`
4. Definir permisos en `config/profiles.yaml`
5. Escribir tests unitarios

Ver [docs/templates/TOOL_SPEC_TEMPLATE.md](docs/templates/TOOL_SPEC_TEMPLATE.md)

## Licencia

MIT
