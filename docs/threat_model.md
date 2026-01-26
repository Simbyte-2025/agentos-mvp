# Threat Model (MVP)

## Superficie de ataque

1) Herramientas (Tools): acceso a FS, HTTP, DB, etc.
2) Prompt injection / tool injection.
3) Fugas de secretos (logs, contexto, respuestas).
4) Escalada de privilegios (agente obtiene permisos indebidos).
5) Dependencias externas (APIs inestables / errores).

## Controles propuestos

### Mínimo privilegio
- Perfiles por agente en `config/profiles.yaml`.
- Validación centralizada en runtime (`PermissionValidator`).
- Prohibición explícita: el agente no puede modificar perfiles.

### Categoría por riesgo
- Tools etiquetadas como: read / write / delete / execute.
- Acciones destructivas requieren HITL.

### Sanitización y validación
- Inputs de tools validados con Pydantic.
- Paths: prevenir path traversal.

### Observabilidad / auditoría
- Log estructurado por request_id: tool, input (sanitizado), output (resumido), timestamps.

## Riesgos abiertos (MVP)
- No hay sandbox real por tool (pendiente: contenedores por ejecución).
- No hay allowlist de dominios en HTTP (pendiente).
