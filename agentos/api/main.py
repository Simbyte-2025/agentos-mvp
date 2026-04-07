"""FastAPI application — uses centralized bootstrap for initialization."""

from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import StreamingResponse

from agentos.api.auth import require_api_key
from agentos.api.models import ApplyRequest, ApplyResponse, ScaffoldRequest, ScaffoldResponse, TaskRequest, TaskResponse
from agentos.agents.builder.builder_agent import build_scaffold
from agentos.bootstrap.init import bootstrap
from agentos.tasks.lifecycle import TaskState
from agentos.observability.logging import get_logger


ROOT = Path(__file__).resolve().parents[2]

logger = get_logger("agentos")

app = FastAPI(title="AgentOS MVP")

# Centralized bootstrap — replaces scattered singleton creation
_state = bootstrap(root=ROOT)


@app.get("/healthz")
def healthz():
    return _state.healthz()


@app.post("/run", response_model=TaskResponse)
def run_task(req: TaskRequest, _: None = Depends(require_api_key)):
    task_state = TaskState(task=req.task, session_id=req.session_id, user_id=req.user_id)
    _state.task_states[task_state.task_id] = task_state
    task_state.start()

    res = _state.orchestrator.run(task=req.task, session_id=req.session_id, user_id=req.user_id)

    if res.success:
        task_state.complete(output=res.output, meta=res.meta)
    else:
        task_state.fail(error=res.error or "Unknown error", meta=res.meta)

    return TaskResponse(agent=res.agent_name, success=res.success, output=res.output, error=res.error, meta=res.meta)


@app.get("/status/{task_id}")
def get_task_status(task_id: str, _: None = Depends(require_api_key)):
    task_state = _state.task_states.get(task_id)
    if task_state is None:
        return {"task_id": task_id, "status": "not_found"}
    return task_state.to_dict()


@app.get("/tasks")
def list_tasks(_: None = Depends(require_api_key)):
    return {"tasks": [ts.to_dict() for ts in _state.task_states.values()]}


@app.post("/run/stream")
def run_task_stream(req: TaskRequest, _: None = Depends(require_api_key)):
    """Execute task with SSE streaming of orchestration events."""
    def event_generator():
        if not hasattr(_state.orchestrator, "run_stream"):
            # Fallback: run synchronously and yield a single completed event
            from agentos.orchestrators.events import OrchestrationEvent, OrchestrationEventType
            res = _state.orchestrator.run(task=req.task, session_id=req.session_id, user_id=req.user_id)
            evt = OrchestrationEvent(
                event_type=OrchestrationEventType.COMPLETED,
                data={"agent": res.agent_name, "success": res.success, "output": res.output, "error": res.error},
            )
            yield evt.to_sse()
            return

        for event in _state.orchestrator.run_stream(
            task=req.task, session_id=req.session_id, user_id=req.user_id
        ):
            yield event.to_sse()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/metrics")
def metrics(_: None = Depends(require_api_key)):
    """Return runtime metrics (requests, tokens, errors, tool usage)."""
    return _state.metrics.to_dict()


@app.get("/readyz")
def readyz():
    """Readiness check — verifies critical dependencies are operational."""
    checks = {}

    # SQLite working state
    try:
        _state.working_state.save_checkpoint("_readyz", "_probe", {"ok": True}, "")
        checks["working_state"] = "ok"
    except Exception as e:
        checks["working_state"] = f"error: {e}"

    # Memory backend
    try:
        _state.long_term.retrieve("readyz probe", top_k=1)
        checks["long_term_memory"] = "ok"
    except Exception as e:
        checks["long_term_memory"] = f"error: {e}"

    all_ok = all(v == "ok" for v in checks.values())
    return {"ready": all_ok, "checks": checks}


# --- Session management endpoints ---

@app.get("/sessions")
def list_sessions(_: None = Depends(require_api_key)):
    """List all sessions with existing transcripts."""
    from agentos.memory.session_transcript import SessionTranscript
    session_ids = SessionTranscript.list_sessions()
    sessions = []
    for sid in session_ids:
        t = SessionTranscript(sid)
        sessions.append({"session_id": sid, "message_count": t.message_count()})
    return {"sessions": sessions}


@app.get("/sessions/{session_id}")
def get_session(session_id: str, _: None = Depends(require_api_key)):
    """Get session details including message count and transcript."""
    from agentos.memory.session_transcript import SessionTranscript
    t = SessionTranscript(session_id)
    return {
        "session_id": session_id,
        "message_count": t.message_count(),
        "messages": t.load(),
    }


@app.delete("/sessions/{session_id}")
def delete_session(session_id: str, _: None = Depends(require_api_key)):
    """Delete a session transcript."""
    from agentos.memory.session_transcript import SessionTranscript
    t = SessionTranscript(session_id)
    deleted = t.delete()
    return {"session_id": session_id, "deleted": deleted}


@app.post("/builder/scaffold", response_model=ScaffoldResponse)
def scaffold(req: ScaffoldRequest, _: None = Depends(require_api_key)):
    plan = build_scaffold(kind=req.kind, name=req.name, description=req.description, risk=req.risk)
    return ScaffoldResponse(files=plan.get("files", []))


@app.post("/builder/apply", response_model=ApplyResponse)
def apply_scaffold(req: ApplyRequest, _: None = Depends(require_api_key)):
    """Aplicar archivos generados por scaffold al filesystem.

    Seguridad:
    - Bloquea rutas absolutas (ej: /etc/passwd, C:\\Windows)
    - Bloquea path traversal (..)
    - No sobrescribe por defecto (overwrite=False)
    """
    written: list[str] = []
    skipped: list[str] = []
    errors: list[dict[str, str]] = []

    for file_spec in req.files:
        path_str = file_spec.get("path", "")
        content = file_spec.get("content", "")

        if not path_str:
            errors.append({"path": "(empty)", "error": "Path vacío"})
            continue

        if path_str.startswith("/") or path_str.startswith("\\") or (len(path_str) > 1 and path_str[1] == ":"):
            errors.append({"path": path_str, "error": "Ruta absoluta no permitida"})
            continue

        if ".." in path_str:
            errors.append({"path": path_str, "error": "Path traversal (..) no permitido"})
            continue

        target_path = ROOT / path_str

        try:
            resolved = target_path.resolve()
            if not str(resolved).startswith(str(ROOT.resolve())):
                errors.append({"path": path_str, "error": "Path escapa del proyecto"})
                continue
        except Exception as e:
            errors.append({"path": path_str, "error": f"Error resolviendo path: {e}"})
            continue

        if target_path.exists() and not req.overwrite:
            skipped.append(path_str)
            continue

        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding="utf-8")
            written.append(path_str)
            logger.info(f"Applied scaffold file: {path_str}")
        except Exception as e:
            errors.append({"path": path_str, "error": str(e)})

    return ApplyResponse(written=written, skipped=skipped, errors=errors)
