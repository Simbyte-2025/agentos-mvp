# RULE.md (Reglas persistentes para Antigravity)

Estas reglas se aplican a **cualquier** tarea ejecutada por agentes en este repo.

## 1) Modo de trabajo

- Para tareas medianas/grandes: **usar modo Planning**.
- Revisar y aprobar artefactos: Implementation Plan, Task List, Walkthrough.
- Si el resultado no sirve: usar **Undo changes**.

## 2) Estructura del proyecto

Respetar la estructura existente:
- `agentos/agents/`: agentes (base, specialist, builder)
- `agentos/tools/`: herramientas
- `agentos/orchestrators/`: orquestación
- `agentos/memory/`: memoria
- `agentos/security/`: permisos
- `config/`: YAML

No crear nuevas carpetas sin justificar.

## 3) Seguridad

- **Principio de mínimo privilegio**: no ampliar permisos sin necesidad.
- Los agentes NO pueden auto-asignarse permisos.
- Tools destructivas deben requerir aprobación humana.
- Nunca exponer secretos en prompts, logs o repositorio.

## 4) Convenciones de código

- Python 3.11+.
- Usar typing.
- Errores de tools: devolver `ToolOutput(success=False, error=...)`.
- Logging estructurado: incluir `request_id`, `session_id`, `agent`, `tool`.

## 5) Dependencias

- No añadir dependencias nuevas sin:
  1) ADR en `docs/`
  2) test asociado

## 6) Terminal (si se ejecuta desde Antigravity)

- Configurar **Terminal Command Auto Execution** con **Allow List** (solo comandos necesarios).
- Evitar comandos peligrosos (rm -rf, curl | sh, etc.).
