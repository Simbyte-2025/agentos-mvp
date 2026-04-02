# Guía ejecutable: usar AgentOS MVP en Claude Code

Esta guía traduce la arquitectura y flujo de AgentOS MVP a un uso práctico dentro de **Claude Code** (terminal + edición + ejecución de comandos).

> Objetivo: que puedas abrir el repo en Claude Code y operar AgentOS de forma repetible: setup, ejecución API, pruebas, modo planner, y troubleshooting.

---

## 1) Qué hace este proyecto (modelo mental rápido)

AgentOS MVP es un runtime de agentes con:

- API FastAPI (`/healthz`, `/run`, `/builder/scaffold`, `/builder/apply`).
- Carga dinámica de agentes y herramientas vía YAML.
- Control de permisos por perfil (mínimo privilegio).
- Dos orquestadores:
  - `sequential` (default, sin LLM externo).
  - `planner` (planner-executor con LLM, soporta `dummy` y `minimax`).

### Flujo de ejecución de una tarea (`/run`)

1. Entra request `task/session_id/user_id`.
2. El orquestador seleccionado decide qué agente(s) y tool(s) usar.
3. Se validan permisos contra `profiles.yaml`.
4. Se ejecutan tools (ej. `read_file`, `http_fetch`, `run_command`).
5. Se guarda estado/checkpoints y se retorna `TaskResponse`.

---

## 2) Prerrequisitos para correrlo desde Claude Code

En Claude Code, abre una terminal en la raíz del repo y ejecuta:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Opcional (script ya preparado):

```bash
bash scripts/setup_dev.sh
```

---

## 3) Arranque mínimo (modo secuencial)

### 3.1 Levantar API

```bash
source .venv/bin/activate
uvicorn agentos.api.main:app --reload --host 0.0.0.0 --port 8080
```

### 3.2 Validar health

En otra terminal de Claude Code:

```bash
curl -s http://localhost:8080/healthz
```

Debe devolver `ok: true` y listar agentes/tools cargados.

### 3.3 Ejecutar tarea simple

```bash
curl -s http://localhost:8080/run \
  -H 'Content-Type: application/json' \
  -d '{"task":"lee el archivo README.md","session_id":"demo","user_id":"local"}'
```

---

## 4) Modo planner (con LLM)

Si quieres que el sistema planifique subtareas (planner-executor), setea variables **antes** de arrancar uvicorn.

### 4.1 Planner con Dummy LLM (ideal para desarrollo local)

```bash
export AGENTOS_ORCHESTRATOR=planner
export AGENTOS_LLM_PROVIDER=dummy
uvicorn agentos.api.main:app --reload --host 127.0.0.1 --port 8080
```

### 4.2 Planner con Minimax

```bash
export AGENTOS_ORCHESTRATOR=planner
export AGENTOS_LLM_PROVIDER=minimax
export MINIMAX_API_KEY='TU_API_KEY'
# opcional
export MINIMAX_BASE_URL='https://api.minimax.io/anthropic'
export MINIMAX_MODEL='MiniMax-M2.1'

uvicorn agentos.api.main:app --reload --host 127.0.0.1 --port 8080
```

Luego prueba `/run` igual que en secuencial.

---

## 5) Cómo operar AgentOS “bien” desde Claude Code (workflow recomendado)

### Paso A — Entender configuración activa

Ejecuta y revisa:

```bash
cat config/agents.yaml
cat config/tools.yaml
cat config/profiles.yaml
```

Esto te dice:

- qué agentes existen,
- qué tools están disponibles,
- qué permisos tiene cada perfil.

### Paso B — Validar seguridad de `run_command`

`run_command` está diseñado con allowlist + validaciones de args/cwd/backend. Usa este patrón cuando pruebes herramientas de ejecución:

```bash
pytest -q tests/unit/test_run_command.py tests/unit/test_run_command_allowlist.py
```

### Paso C — Correr smoke de orquestación

```bash
pytest -q tests/integration/test_run_smoke.py tests/integration/test_run_planner_smoke.py
```

### Paso D — Iterar cambios pequeños

En Claude Code:

1. modifica 1 objetivo por PR,
2. ejecuta tests relevantes,
3. revisa diffs,
4. documenta en `docs/` si cambió comportamiento.

---

## 6) Usar endpoints Builder desde Claude Code

### Generar scaffold

```bash
curl -s http://localhost:8080/builder/scaffold \
  -H 'Content-Type: application/json' \
  -d '{
    "kind":"tool",
    "name":"my_tool",
    "description":"Tool de ejemplo",
    "risk":"read"
  }'
```

### Aplicar scaffold (con validaciones de path)

```bash
curl -s http://localhost:8080/builder/apply \
  -H 'Content-Type: application/json' \
  -d '{
    "overwrite": false,
    "files": [
      {"path":"agentos/tools/example.txt","content":"hola"}
    ]
  }'
```

`/builder/apply` bloquea rutas absolutas y path traversal (`..`).

---

## 7) Seguridad y permisos (importante para Claude Code)

- Si defines `AGENTOS_API_KEY`, `/run` y endpoints builder exigirán header `X-API-Key`.
- Si no defines `AGENTOS_API_KEY`, API queda en modo dev (sin auth).
- Permisos de tools se validan por perfil en `config/profiles.yaml`.
- `run_command` solo debe habilitarse para perfiles concretos (mínimo privilegio).

Ejemplo con API key:

```bash
export AGENTOS_API_KEY='dev-secret'
curl -s http://localhost:8080/run \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: dev-secret' \
  -d '{"task":"saluda","session_id":"s1","user_id":"u1"}'
```

---

## 8) Troubleshooting rápido

### Error: planner no inicia

Verifica:

```bash
echo "$AGENTOS_ORCHESTRATOR"
echo "$AGENTOS_LLM_PROVIDER"
```

Si `AGENTOS_ORCHESTRATOR=planner`, entonces `AGENTOS_LLM_PROVIDER` debe ser `dummy` o `minimax`.

### Error 401 en `/run`

- revisa que `AGENTOS_API_KEY` del servidor coincida con `X-API-Key` del request.

### `run_command` bloquea comando

- revisa allowlist y args prohibidos en tests/config;
- prueba comandos permitidos (`python`, `pytest`, etc.).

---

## 9) Playbook “copiar/pegar” para Claude Code

```bash
# 1) Setup
bash scripts/setup_dev.sh

# 2) Tests base
bash scripts/run_tests.sh

# 3) Levantar API (secuencial)
source .venv/bin/activate
uvicorn agentos.api.main:app --reload --port 8080

# 4) Health
curl -s http://localhost:8080/healthz

# 5) Run
curl -s http://localhost:8080/run \
  -H 'Content-Type: application/json' \
  -d '{"task":"lee README.md","session_id":"demo","user_id":"local"}'
```

Con esto ya tienes una base operativa para trabajar AgentOS dentro de Claude Code.
