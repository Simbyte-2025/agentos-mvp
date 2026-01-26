# Runbook: Local

## Levantar API

1. Crear venv e instalar deps:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

2. Iniciar servicio:

```bash
uvicorn agentos.api.main:app --reload --host 0.0.0.0 --port 8080
```

## Health check

```bash
curl -s http://localhost:8080/healthz
```

## Ejecutar una tarea

```bash
curl -s http://localhost:8080/run \
  -H 'Content-Type: application/json' \
  -d '{"task":"lee el archivo README.md","session_id":"demo","user_id":"local"}'
```

## Tests

```bash
pytest -q
```
