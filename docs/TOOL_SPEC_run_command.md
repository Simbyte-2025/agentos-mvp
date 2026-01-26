# Tool Spec: run_command

## Objetivo

Ejecutar comandos del sistema de forma segura con controles estrictos basados en allowlist, bloqueo de operadores shell, y modo sandbox opcional.

**Casos de uso**:
- Ejecutar tests automatizados (`pytest`)
- Ejecutar scripts Python para procesamiento de datos
- Inspeccionar archivos del sistema (`dir`, `type`)
- Validar instalación de dependencias

## Entradas

### ToolInput.payload

| Campo | Tipo | Requerido | Default | Descripción |
|-------|------|-----------|---------|-------------|
| `command` | `str` | ✅ Sí | - | Comando base a ejecutar (debe estar en allowlist) |
| `args` | `list[str]` | ❌ No | `[]` | Argumentos del comando |
| `cwd` | `str` | ❌ No | `AGENTOS_WORKSPACE_ROOT` | Directorio de trabajo (relativo al workspace) |
| `timeout_s` | `int` | ❌ No | `30` | Timeout en segundos (máx: 300) |
| `sandbox` | `bool` | ❌ No | `false` | Ejecutar en modo sandbox |

### Validaciones (Pydantic)

```python
class RunCommandPayload(BaseModel):
    command: str = Field(..., min_length=1, max_length=100)
    args: list[str] = Field(default_factory=list, max_items=50)
    cwd: Optional[str] = Field(None, max_length=500)
    timeout_s: int = Field(30, ge=1, le=300)
    sandbox: bool = Field(False)
```

### Ejemplo de payload

```json
{
  "command": "pytest",
  "args": ["-v", "tests/unit"],
  "cwd": ".",
  "timeout_s": 60,
  "sandbox": false
}
```

## Salidas

### ToolOutput

```python
{
  "success": bool,
  "data": {
    "exit_code": int,           # Código de salida del comando
    "stdout": str,              # Salida estándar (truncada a 10KB)
    "stderr": str,              # Salida de error (truncada a 10KB)
    "timed_out": bool,          # Si se aplicó timeout
    "command_executed": str     # Comando completo ejecutado (para auditoría)
  },
  "error": Optional[str],       # Mensaje de error si falla validación
  "meta": {
    "duration_ms": int,         # Duración de ejecución en ms
    "sandbox": bool             # Si se usó sandbox
  }
}
```

### Casos de éxito

**Comando ejecutado exitosamente**:
```json
{
  "success": true,
  "data": {
    "exit_code": 0,
    "stdout": "test_example.py::test_foo PASSED\n",
    "stderr": "",
    "timed_out": false,
    "command_executed": "pytest -v tests/unit"
  },
  "error": null,
  "meta": {
    "duration_ms": 1234,
    "sandbox": false
  }
}
```

**Comando ejecutado con error**:
```json
{
  "success": true,
  "data": {
    "exit_code": 1,
    "stdout": "",
    "stderr": "ERROR: file not found\n",
    "timed_out": false,
    "command_executed": "python script.py"
  },
  "error": null,
  "meta": {
    "duration_ms": 567,
    "sandbox": false
  }
}
```

### Casos de error

**Comando no permitido**:
```json
{
  "success": false,
  "data": null,
  "error": "Comando 'del' no está en allowlist. Permitidos: python, pytest, dir, type",
  "meta": {}
}
```

**Operador shell detectado**:
```json
{
  "success": false,
  "data": null,
  "error": "Operador shell peligroso detectado: '&&'",
  "meta": {}
}
```

**Path traversal detectado**:
```json
{
  "success": false,
  "data": null,
  "error": "cwd fuera del workspace no permitido",
  "meta": {}
}
```

**Timeout aplicado**:
```json
{
  "success": true,
  "data": {
    "exit_code": -1,
    "stdout": "...",
    "stderr": "",
    "timed_out": true,
    "command_executed": "python long_script.py"
  },
  "error": null,
  "meta": {
    "duration_ms": 30000,
    "sandbox": false
  }
}
```

## Riesgo

**Nivel**: `execute` (máximo riesgo)

**Justificación**:
- Ejecución de comandos del sistema es la superficie de ataque más crítica
- Potencial para shell injection, path traversal, escalada de privilegios
- Puede causar modificación/eliminación de archivos si el comando tiene permisos

**Requiere aprobación humana**: ❌ No (pero requiere permiso explícito en `profiles.yaml`)

**Controles de seguridad**:
1. ✅ Allowlist estricta de comandos
2. ✅ Bloqueo de operadores shell
3. ✅ `shell=False` obligatorio
4. ✅ Validación de path traversal
5. ✅ Timeout estricto
6. ✅ Modo sandbox opcional
7. ✅ Permisos explícitos requeridos

## Errores y reintentos

### Errores esperables

| Error | Causa | Retry | Acción |
|-------|-------|-------|--------|
| `Comando no está en allowlist` | Comando no permitido | ❌ No | Agregar comando a allowlist o usar comando permitido |
| `Operador shell detectado` | Intento de inyección | ❌ No | Remover operadores shell del comando/args |
| `cwd fuera del workspace` | Path traversal | ❌ No | Usar cwd dentro del workspace |
| `Timeout aplicado` | Comando muy lento | ✅ Sí | Aumentar `timeout_s` o optimizar comando |
| `Exit code != 0` | Comando falló | ✅ Sí | Revisar stderr, corregir comando/args |
| `Comando no encontrado` | Comando no instalado | ❌ No | Instalar comando o usar alternativa |

### Estrategia de retry

**Retry automático**: ❌ No

**Rationale**:
- Comandos pueden tener side effects (escribir archivos, enviar requests)
- Retry automático podría duplicar side effects
- El agente debe decidir si reintentar basado en el error

**Recomendación**: El orquestador (Planner-Executor) puede reintentar si:
- `exit_code != 0` y el error es recuperable
- `timed_out == true` y se puede aumentar timeout

## Observabilidad

### Campos mínimos en logs

Todos los comandos ejecutados deben loggearse con:

```json
{
  "timestamp": "2026-01-16T14:15:30Z",
  "level": "info",
  "request_id": "req_abc123",
  "tool": "run_command",
  "command": "pytest",
  "args": ["-v"],
  "cwd": ".",
  "exit_code": 0,
  "duration_ms": 1234,
  "sandbox": false,
  "timed_out": false,
  "stdout_length": 567,
  "stderr_length": 0
}
```

**Nota**: `stdout` y `stderr` NO se loggean completos (pueden ser muy largos). Solo se loggea la longitud.

### Métricas

- **Latencia**: `duration_ms` (p50, p95, p99)
- **Exit codes**: Distribución de códigos de salida
- **Timeouts**: Frecuencia de timeouts
- **Comandos más usados**: Top 10 comandos
- **Errores de validación**: Frecuencia de errores de allowlist/shell operators

### Alertas

- ⚠️ **Timeout frecuente**: >10% de comandos con timeout
- 🚨 **Intento de shell injection**: Operador shell detectado
- 🚨 **Intento de path traversal**: cwd fuera del workspace
- 🚨 **Comando no permitido**: Intento de ejecutar comando no en allowlist

## Configuración

### config/tools.yaml

```yaml
tools:
  - name: run_command
    class_path: agentos.tools.exec.run_command.RunCommandTool
    risk: execute
    description: "Ejecuta comandos del sistema con allowlist estricta y modo sandbox."
    config:
      allowed_commands:
        - python
        - pytest
        - dir
        - type
      max_timeout_s: 300
      default_timeout_s: 30
```

### Variables de entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `AGENTOS_ALLOWED_COMMANDS` | `python,pytest,dir,type` | Comandos permitidos (separados por coma) |
| `AGENTOS_WORKSPACE_ROOT` | `.` | Directorio raíz del workspace |

**Ejemplo**:
```bash
export AGENTOS_ALLOWED_COMMANDS=python,pytest,dir,type,myapp
export AGENTOS_WORKSPACE_ROOT=/home/user/workspace
```

## Backends

El sistema soporta múltiples backends de ejecución, controlados por feature flags.

### Selección de Backend

Variable de entorno: `AGENTOS_EXEC_BACKEND`

| Valor | Descripción | Comportamiento |
|-------|-------------|----------------|
| `local` (default) | Ejecución en host | Usa `subprocess` localmente. Aislamiento limitado a cwd/tempdir. |
| `docker` | Ejecución en contenedor | Usa `docker run`. Aislamiento fuerte (red, FS). Requiere Docker instalado. |

### Docker Backend

**Activación**:
```bash
export AGENTOS_EXEC_BACKEND=docker
```

**Comandos Soportados**:
- `python`, `pytest`: Se ejecutan dentro del contenedor (`python:3.11-slim`).
- `dir`, `type`: **Fallback automático a Local**. Estos comandos son específicos de Windows shell y no existen en Linux container.

**Troubleshooting (Windows/WSL2)**:
- Si falla con "access denied" en volúmenes: Verificar que la unidad C: esté compartida en Docker Desktop settings.
- Si falla "network not found": El backend usa `--network none` intencionalmente.

## Modo Sandbox

### Comportamiento

Cuando `sandbox: true`:
1. Crea directorio temporal aislado
2. Limita variables de entorno a mínimo:
   - `PATH`: Para encontrar comandos
   - `SYSTEMROOT`: Requerido por Windows
   - `TEMP`, `TMP`: Apuntan al directorio temporal
3. Ejecuta comando en directorio temporal
4. Limpia directorio temporal después de ejecución

### Limitaciones (Windows)

⚠️ **Advertencia**: El sandbox NO previene:
- Acceso a red (comandos pueden hacer HTTP requests)
- Acceso a archivos del sistema (si el comando tiene permisos)
- Consumo de CPU/memoria (no hay cgroups en Windows)

Para sandbox completo se requiere Docker/contenedores.

### Ejemplo de uso

```json
{
  "command": "python",
  "args": ["-c", "import os; print(os.listdir('.'))"],
  "sandbox": true
}
```

**Resultado**: Lista archivos del directorio temporal, no del workspace.

## Permisos

### Configuración en profiles.yaml

Por defecto, **NINGÚN agente** tiene permiso `execute`.

**Ejemplo**: Otorgar permiso a `builder_agent`:

```yaml
builder_agent:
  permissions:
    - tool: run_command
      actions: [execute]
  forbidden:
    - tool: "*"
      actions: [write, delete]
```

### Validación

El `PermissionValidator` valida que:
1. El agente tiene permiso para `run_command`
2. La acción `execute` está permitida
3. La acción `execute` NO está en `forbidden`

Si falla la validación, el comando NO se ejecuta.

## Ejemplos de uso

### Ejecutar tests

```python
tool_input = ToolInput(
    request_id="req_123",
    payload={
        "command": "pytest",
        "args": ["-v", "tests/unit"],
        "timeout_s": 60
    }
)
result = run_command_tool.execute(tool_input)
```

### Listar archivos

```python
tool_input = ToolInput(
    request_id="req_456",
    payload={
        "command": "dir",
        "args": ["/B"],  # Brief format
        "cwd": "src"
    }
)
result = run_command_tool.execute(tool_input)
```

### Ejecutar script en sandbox

```python
tool_input = ToolInput(
    request_id="req_789",
    payload={
        "command": "python",
        "args": ["script.py"],
        "sandbox": true,
        "timeout_s": 120
    }
)
result = run_command_tool.execute(tool_input)
```

## Referencias

- ADR: [ADR_002_run_command_security.md](file:///c:/Users/nicol/Desktop/agentos_mvp/docs/ADR_002_run_command_security.md)
- Threat Model: [threat_model.md](file:///c:/Users/nicol/Desktop/agentos_mvp/docs/threat_model.md)
- Base Tool: [agentos/tools/base.py](file:///c:/Users/nicol/Desktop/agentos_mvp/agentos/tools/base.py)
- Permissions: [agentos/security/permissions.py](file:///c:/Users/nicol/Desktop/agentos_mvp/agentos/security/permissions.py)
