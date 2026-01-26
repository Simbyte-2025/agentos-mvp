# Tool Spec: <tool_name>

## Objetivo

(Qué hace la tool y para qué se usa.)

## Entradas

- Campos, tipos, validaciones (Pydantic).

## Salidas

- `ToolOutput`: success/data/error.

## Riesgo

- read | write | delete | execute
- ¿Requiere aprobación humana?

## Errores y reintentos

- Errores esperables
- Estrategia de retry/circuit breaker

## Observabilidad

- Campos mínimos en logs (request_id, tool, latencia).
