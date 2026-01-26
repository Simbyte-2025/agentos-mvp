# ADR 003: Docker Backend for Secure Execution

## Contexto

El sistema AgentOS MVP actualmente utiliza un backend local para `run_command` con aislamiento limitado (tempdir). Si bien esto previene cambios accidentales en el directorio actual, no protege contra:
- Acceso a la red (exfiltración de datos, descargas).
- Consumo excesivo de recursos (CPU, memoria).
- Acceso a otros archivos del sistema si el proceso tiene permisos.

Existe un riesgo real de ejecutar código inestable o malicioso generado por LLMs en el host.

## Decisión

Implementar un **Backend Docker Opcional** activado mediante feature flag, manteniendo el backend local como default.

- **Feature Flag**: `AGENTOS_EXEC_BACKEND` (valores: `local`, `docker`). Default: `local`.
- **Backend Docker**: Ejecuta comandos dentro de contenedores efímeros (`python:3.11-slim`).

### Alternativas Consideradas

1. **Solo Local**: Rechazada por riesgo de seguridad en entornos de producción.
2. **Docker Siempre**: Rechazada por aumentar la barrera de entrada (requiere Docker instalado) y complejidad en dev.
3. **Docker-Py**: Se utiliza `subprocess` invocando el CLI de Docker para reducir dependencias Python y manejar mejor el ciclo de vida del proceso desde fuera.

## Detalles de Seguridad

El contenedor se ejecuta con flags estrictos:
- `--network none`: Aislamiento total de red.
- `--read-only`: Filesystem de solo lectura (excepto volúmenes montados explícitamente).
- `--tmpfs /tmp:rw,noexec,nosuid,size=100m`: Espacio temporal volátil.
- **Resource Limits**: Configurable (aunque no siempre enforceado en Windows/WSL2 sin configuración extra).
- **User**: Se intenta `--user <uid>:<gid>` (best-effort en Windows).

## Manejo de Timeouts y Limpieza

Para garantizar la limpieza de contenedores (evitar "zombies"):
1. Se asigna un nombre determinista: `--name agentos-runcommand-<short_uuid>`.
2. El timeout es manejado por `subprocess.run(timeout=X)`.
3. Si expira el timeout, se ejecuta explícitamente `docker kill <name>` y `docker rm <name>`.

## Consecuencias

### Positivas
- Aislamiento real del sistema host.
- Entorno de ejecución reproducible.
- Control de recursos.

### Negativas
- **Latencia**: Mayor tiempo de inicio por contenedor (cientos de ms vs ms).
- **Dependencia**: Requiere Docker Desktop en Windows o Docker Engine en Linux.
- **Comandos**: Solo soporta comandos disponibles en la imagen (`python`, `pytest`). Comandos del host (`dir`, `type`) no funcionan y requieren fallback.

## Fallbacks

1. **Docker no disponible**: Si `docker` no está en PATH o el daemon no responde → Fallback a `LocalBackend` (con warning).
2. **Comando no soportado**: Si se pide `dir`, `type` u otros comandos Windows-only → Fallback a `LocalBackend`.
