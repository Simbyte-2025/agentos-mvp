# AGENTS.md

Guía de trabajo para humanos y agentes (Google Antigravity) en este repo.

## Reglas mínimas

- Usar **modo Planning** para tareas no triviales.
- Hacer cambios **pequeños**: un PR = un objetivo.
- Si cambia comportamiento, agregar **tests**.
- No añadir dependencias sin justificar (idealmente con ADR).
- No otorgar permisos amplios a agentes “por conveniencia”.

## Dónde tocar qué

- `agentos/`: código.
- `config/`: YAML de agentes, tools, prompts y perfiles.
- `docs/`: especificación, threat model, ADRs.
- `deployments/`: docker.
- `scripts/`: scripts.
- `tests/`: unit/integration/evals.

## Flujo recomendado en Antigravity

1. Abrir un **Workspace** apuntando a la carpeta del repo.
2. Activar modo **Planning**.
3. Antes de aprobar, revisar: **Implementation Plan**, **Task List** y **Walkthrough**.
4. Si el agente se descontrola, usar **Undo changes**.

## Convenciones

- Logging: usar `agentos.observability.logging.get_logger()` y pasar `request_id`.
- Tools: devolver `ToolOutput` con `success/data/error`.
- Permisos: se validan con `config/profiles.yaml`.

## Comandos útiles

- Levantar API: `uvicorn agentos.api.main:app --reload --port 8080`
- Tests: `pytest -q`
