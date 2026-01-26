# ADR: Secure run_command Tool

## Contexto

El sistema AgentOS MVP necesita capacidad de ejecutar comandos del sistema para casos de uso como:

1. **Testing automatizado**: Ejecutar `pytest` para validar código
2. **Inspección del sistema**: Ejecutar `dir`, `type` para explorar archivos
3. **Ejecución de scripts**: Ejecutar scripts Python para procesamiento de datos

Sin embargo, la ejecución de comandos del sistema es **la superficie de ataque más crítica** en un sistema de agentes:

- **Shell injection**: Inyección de comandos maliciosos vía operadores shell (`&&`, `||`, `;`, `|`)
- **Path traversal**: Acceso a archivos fuera del workspace permitido
- **Escalada de privilegios**: Ejecución de comandos con permisos elevados
- **Resource exhaustion**: Comandos que consumen CPU/memoria indefinidamente
- **Data exfiltration**: Comandos que envían datos a servidores externos

El threat model actual (docs/threat_model.md) identifica "No hay sandbox real por tool" como un riesgo abierto.

### Restricciones

- **Windows MVP**: Debe funcionar en Windows sin dependencias adicionales
- **Sin contenedores**: Docker/WSL están fuera del alcance del MVP
- **Principio de mínimo privilegio**: Solo comandos estrictamente necesarios
- **Sin nuevas dependencias**: No agregar bibliotecas externas sin ADR

## Decisión

Implementar `RunCommandTool` con **defensa en profundidad** usando múltiples capas de seguridad:

### 1. Allowlist Estricta (Primera Línea de Defensa)

**Decisión**: Usar allowlist de comandos permitidos en vez de blocklist.

**Comandos permitidos por defecto**:
- `python`: Ejecutar scripts Python
- `pytest`: Ejecutar tests
- `dir`: Listar archivos (Windows)
- `type`: Leer archivos (Windows)

**Configuración**:
```yaml
# config/tools.yaml
tools:
  - name: run_command
    config:
      allowed_commands: [python, pytest, dir, type]
```

**Override vía ENV**:
```bash
AGENTOS_ALLOWED_COMMANDS=python,pytest,dir,type,myapp
```

### 2. Bloqueo de Shell Operators (Segunda Línea de Defensa)

**Decisión**: Bloquear operadores shell peligrosos en `command` y `args`.

**Operadores bloqueados**:
- `&&`, `||`: Encadenamiento de comandos
- `;`: Separador de comandos
- `|`: Pipes
- `>`, `<`: Redirección
- `$`, `` ` ``: Expansión de variables/comandos
- `(`, `)`: Subshells

**Implementación**:
```python
DANGEROUS_TOKENS = ["&&", "||", ";", "|", ">", "<", "$", "`", "(", ")"]

def _contains_shell_operators(text: str) -> bool:
    return any(token in text for token in DANGEROUS_TOKENS)
```

### 3. shell=False Obligatorio (Tercera Línea de Defensa)

**Decisión**: Usar `subprocess.run()` con `shell=False` siempre.

**Rationale**:
- `shell=True` invoca el shell del sistema (cmd.exe en Windows)
- Permite interpretación de operadores shell
- Expone a inyección de comandos incluso con validación

**Implementación**:
```python
subprocess.run(
    [command] + args,  # Lista, no string
    shell=False,       # NUNCA True
    ...
)
```

### 4. Path Traversal Protection (Cuarta Línea de Defensa)

**Decisión**: Validar `cwd` contra `AGENTOS_WORKSPACE_ROOT`.

**Implementación**:
```python
workspace_root = Path(os.getenv("AGENTOS_WORKSPACE_ROOT", ".")).resolve()
cwd_path = (workspace_root / cwd).resolve()

if not str(cwd_path).startswith(str(workspace_root)):
    return ToolOutput(success=False, error="cwd fuera del workspace")
```

### 5. Timeout Estricto (Quinta Línea de Defensa)

**Decisión**: Timeout obligatorio con límite máximo.

**Configuración**:
- Default: 30 segundos
- Máximo: 300 segundos (5 minutos)
- Configurable por request

**Implementación**:
```python
timeout_s = min(payload.get("timeout_s", 30), 300)
subprocess.run(..., timeout=timeout_s)
```

### 6. Modo Sandbox (Sexta Línea de Defensa)

**Decisión**: Sandbox ligero basado en aislamiento de entorno (no contenedores).

**Limitaciones en Windows**:
- No hay namespaces como en Linux
- No hay cgroups para limitar recursos
- No hay seccomp para filtrar syscalls

**Implementación MVP**:
```python
if sandbox:
    # Crear directorio temporal aislado
    sandbox_dir = tempfile.mkdtemp(prefix="agentos_sandbox_")
    
    # Limitar variables de entorno
    env = {
        "PATH": os.environ.get("PATH", ""),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        "TEMP": sandbox_dir,
        "TMP": sandbox_dir,
    }
    
    # Ejecutar en directorio temporal
    subprocess.run(..., cwd=sandbox_dir, env=env)
    
    # Limpiar después
    shutil.rmtree(sandbox_dir)
```

**Advertencia**: Este sandbox NO previene:
- Acceso a red
- Acceso a archivos del sistema (si el comando tiene permisos)
- Consumo de CPU/memoria

Para sandbox completo se requiere Docker/contenedores (fuera del alcance).

### 7. Permisos Explícitos (Séptima Línea de Defensa)

**Decisión**: `risk: execute` requiere permiso explícito en `profiles.yaml`.

**Por defecto**: NINGÚN agente tiene permiso `execute`.

**Ejemplo**:
```yaml
# config/profiles.yaml
builder_agent:
  permissions:
    - tool: run_command
      actions: [execute]  # Explícito
  forbidden:
    - tool: "*"
      actions: [write, delete]
```

### 8. Validación de Args Específica por Comando (Octava Línea de Defensa)

**Decisión**: Bloquear args peligrosos específicos para comandos de alto riesgo.

**Python args bloqueados**:
- `-c`: Ejecutar código inline (`python -c "import os; os.system('del *')"`)
- `-m`: Ejecutar módulo (`python -m http.server` puede exponer archivos)
- `-`: Leer código desde stdin (difícil de auditar)

**Python args permitidos**:
- `--version`: Información de versión
- `--help`: Ayuda
- `<script.py>`: Ejecutar script dentro del workspace (validado por path traversal)

**Implementación**:
```python
PYTHON_DANGEROUS_ARGS = ["-c", "-m", "-"]

def _validate_python_args(args: list[str]) -> tuple[bool, str]:
    for arg in args:
        if arg in PYTHON_DANGEROUS_ARGS:
            return False, f"Python arg peligroso bloqueado: {arg}"
    return True, ""
```

**Rationale**:
- Allowlist por sí sola no previene `python -c` injection
- Bloquear args peligrosos reduce superficie de ataque
- Permite casos de uso legítimos (`python script.py`, `python --version`)

## Alternativas consideradas

### A. Blocklist vs. Allowlist

**Rechazada**: Usar blocklist de comandos prohibidos.

- ❌ Imposible enumerar todos los comandos peligrosos
- ❌ Nuevos comandos son permitidos por defecto (inseguro)
- ❌ Bypass vía aliases, rutas absolutas, etc.
- ✅ **Seleccionada**: Allowlist es más segura (deny by default)

### B. shell=True con sanitización vs. shell=False

**Rechazada**: Usar `shell=True` con sanitización de inputs.

- ❌ Sanitización es frágil (siempre hay bypasses)
- ❌ Depende de conocer todos los operadores shell
- ❌ Varía entre shells (cmd.exe, PowerShell, bash)
- ✅ **Seleccionada**: `shell=False` elimina el problema de raíz

### C. Docker/WSL sandbox vs. Sandbox ligero

**Rechazada**: Usar Docker o WSL para sandbox completo.

- ❌ Requiere Docker instalado (dependencia externa)
- ❌ Latencia de inicio de contenedor (~1-2s)
- ❌ Complejidad de configuración
- ❌ No funciona en todos los entornos Windows
- ✅ **Seleccionada**: Sandbox ligero es suficiente para MVP

**Nota**: Docker sandbox puede agregarse en el futuro como opción avanzada.

### D. Timeout ilimitado vs. Timeout estricto

**Rechazada**: Permitir comandos sin timeout.

- ❌ Riesgo de comandos que nunca terminan
- ❌ Resource exhaustion
- ❌ Bloqueo de workers
- ✅ **Seleccionada**: Timeout obligatorio previene DoS

### E. Validación de args vs. Solo validación de command

**Rechazada**: Validar solo el comando base, permitir args arbitrarios.

- ❌ Bypass vía args: `python -c "import os; os.system('del *')"`
- ❌ Bypass vía archivos: `python malicious.py`
- ✅ **Seleccionada**: Validar command + bloquear operadores shell + bloquear args peligrosos por comando

**Nota**: Validación específica para Python bloquea `-c`, `-m`, `-`. Otros comandos pueden requerir validación similar en el futuro.

### F. Validación genérica de args vs. Validación específica por comando

**Rechazada**: Validación genérica de args para todos los comandos.

- ❌ Cada comando tiene args peligrosos diferentes
- ❌ Validación genérica es demasiado restrictiva o demasiado permisiva
- ✅ **Seleccionada**: Validación específica por comando (empezando con Python)

## Consecuencias

### Positivas

- ✅ **Defensa en profundidad**: 8 capas de seguridad independientes
- ✅ **Deny by default**: Solo comandos explícitamente permitidos
- ✅ **Python injection bloqueado**: Args peligrosos (`-c`, `-m`, `-`) bloqueados
- ✅ **Sin dependencias**: Usa solo stdlib de Python
- ✅ **Auditable**: Logging completo de comandos ejecutados
- ✅ **Configurable**: Allowlist vía config o ENV
- ✅ **Timeout garantizado**: Previene comandos infinitos
- ✅ **Compatible con permisos**: Integra con `PermissionValidator` existente

### Negativas

- ⚠️ **Sandbox limitado**: No es aislamiento completo (Windows)
- ⚠️ **Allowlist restrictiva**: Requiere agregar comandos manualmente
- ⚠️ **Validación de args limitada**: Confía en el agente para args seguros
- ⚠️ **Sin límite de recursos**: No previene uso excesivo de CPU/memoria
- ⚠️ **Sin filtrado de red**: Comandos pueden hacer requests HTTP

### Mitigaciones

- **Sandbox limitado**: Documentar como "tempdir isolation", no prometer aislamiento completo. Agregar Docker sandbox en futuro.
- **Allowlist restrictiva**: Proveer ENV override para casos de uso específicos.
- **Validación de args**: Validación específica por comando (Python implementado, otros en futuro).
- **Límite de recursos**: Agregar en futuro (requiere bibliotecas externas o cgroups).
- **Filtrado de red**: Agregar firewall rules en deployment (fuera del alcance del MVP).

## Estado

**Aprobada** - Implementación aprobada con condiciones:
- Allowlist exacta: `python`, `pytest`, `dir`, `type`
- Python args bloqueados: `-c`, `-m`, `-`
- Sandbox documentado como "tempdir isolation"
- Solo `builder_agent` tiene permiso `execute`

## Notas de Implementación

### Estructura de archivos

```
agentos/
  security/
    run_command_allowlist.py  # Validación de allowlist
  tools/
    exec/
      __init__.py
      run_command.py            # Implementación de RunCommandTool

tests/
  unit/
    test_run_command_allowlist.py
    test_run_command.py
  integration/
    test_run_command_integration.py
```

### Logging

Todos los comandos ejecutados deben loggearse con:
- `request_id`: Identificador de request
- `command`: Comando base
- `args`: Argumentos (sanitizados)
- `exit_code`: Código de salida
- `duration_ms`: Duración en milisegundos
- `sandbox`: Si se usó modo sandbox
- `timed_out`: Si se aplicó timeout

**Ejemplo**:
```json
{
  "level": "info",
  "request_id": "req_123",
  "tool": "run_command",
  "command": "pytest",
  "args": ["-v"],
  "exit_code": 0,
  "duration_ms": 1234,
  "sandbox": false,
  "timed_out": false
}
```

### Testing

**Casos críticos**:
1. Comando permitido ejecuta correctamente
2. Comando no permitido falla en validación
3. Operadores shell son bloqueados
4. Python args peligrosos (`-c`, `-m`, `-`) son bloqueados
5. Path traversal es bloqueado
6. Timeout se aplica correctamente
7. Sandbox aísla ejecución (tempdir)
8. Permisos son validados (sin permiso execute, comando NO corre)
9. stdout/stderr truncados a 10KB en respuesta

## Referencias

- `agentos/tools/base.py`: Interfaz BaseTool
- `agentos/security/permissions.py`: PermissionValidator
- `config/tools.yaml`: Configuración de tools
- `config/profiles.yaml`: Perfiles de permisos
- `docs/threat_model.md`: Modelo de amenazas
