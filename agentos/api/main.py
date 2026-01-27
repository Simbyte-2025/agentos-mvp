from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any, Dict, List

import yaml
from fastapi import Depends, FastAPI

from agentos.agents.base.agent_base import BaseAgent
from agentos.api.auth import require_api_key
from agentos.api.models import ApplyRequest, ApplyResponse, ScaffoldRequest, ScaffoldResponse, TaskRequest, TaskResponse
from agentos.agents.builder.builder_agent import build_scaffold
from agentos.memory.long_term import LongTermMemory
from agentos.memory.short_term import ShortTermMemory
from agentos.memory.working_state import WorkingStateStore
from agentos.orchestrators.sequential import SequentialOrchestrator
from agentos.security.permissions import PermissionValidator, load_profiles
from agentos.tools.base import BaseTool
from agentos.observability.logging import get_logger


ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"

logger = get_logger("agentos")


def import_class(class_path: str):
    module_name, class_name = class_path.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


def load_yaml(path: Path) -> Dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def bootstrap_agents() -> List[BaseAgent]:
    cfg = load_yaml(CONFIG_DIR / "agents.yaml")
    agents_cfg = cfg.get("agents", [])
    agents: List[BaseAgent] = []
    for a in agents_cfg:
        cls = import_class(a["class_path"])
        kwargs = {}
        if cls.__name__ == "BuilderAgent":
            kwargs["root_dir"] = ROOT
        agents.append(cls(name=a["name"], description=a.get("description", ""), profile=a.get("profile", a["name"]), **kwargs))
    return agents


def bootstrap_tools() -> List[BaseTool]:
    cfg = load_yaml(CONFIG_DIR / "tools.yaml")
    tools_cfg = cfg.get("tools", [])
    tools: List[BaseTool] = []
    for t in tools_cfg:
        cls = import_class(t["class_path"])
        tools.append(cls())
    return tools


app = FastAPI(title="AgentOS MVP")

# Singletons (MVP)
_agents = bootstrap_agents()
_tools = bootstrap_tools()
_profiles = load_profiles(CONFIG_DIR / "profiles.yaml")
_permission_validator = PermissionValidator(_profiles)
_short_term = ShortTermMemory(max_items=10)
_working_state = WorkingStateStore(db_path=ROOT / "agentos_state.db")
_long_term = LongTermMemory()

# Feature flags for orchestrator selection
# Feature flags for orchestrator selection
orchestrator_type = (os.getenv("AGENTOS_ORCHESTRATOR") or "sequential").lower().strip()

# LLM provider selection (backward compatible)
# AGENTOS_LLM_PROVIDER takes precedence, fallback to AGENTOS_LLM for compatibility
llm_provider = (os.getenv("AGENTOS_LLM_PROVIDER") or os.getenv("AGENTOS_LLM") or "").lower().strip()

# Initialize orchestrator based on feature flags
if orchestrator_type == "planner":
    from agentos.llm.dummy import DummyLLM
    from agentos.llm.minimax import MinimaxClient
    from agentos.orchestrators.planner_executor import PlannerExecutorOrchestrator
    
    llm_client = None
    
    # Select LLM client based on provider
    if llm_provider == "dummy":
        llm_client = DummyLLM()
        logger.info("Using DummyLLM for planner orchestrator", extra={"llm_provider": llm_provider})
    
    elif llm_provider == "minimax":
        # Get Minimax configuration from env vars
        api_key = os.getenv("MINIMAX_API_KEY")
        base_url = os.getenv("MINIMAX_BASE_URL", "https://api.minimax.io/anthropic")
        model = os.getenv("MINIMAX_MODEL", "MiniMax-M2.1")
        
        # Instantiate client even without API key (errors deferred to runtime)
        llm_client = MinimaxClient(
            api_key=api_key,
            base_url=base_url,
            model=model
        )
        
        if api_key:
            logger.info(
                "Using MinimaxClient for planner orchestrator",
                extra={"llm_provider": llm_provider, "base_url": base_url, "model": model}
            )
        else:
            logger.warning(
                "MinimaxClient configured but MINIMAX_API_KEY not set. "
                "API will start but /run requests will fail with clear error message.",
                extra={"llm_provider": llm_provider, "base_url": base_url, "model": model}
            )
    
    if llm_client is None:
        # Error fatal: Se pidió planner pero no hay LLM válido
        error_msg = f"AGENTOS_ORCHESTRATOR=planner requiere un proveedor LLM válido. Proveedor actual: '{llm_provider}' (soportados: minimax, dummy)"
        logger.error(error_msg)
        raise ValueError(error_msg)

    _orchestrator = PlannerExecutorOrchestrator(
        agents=_agents,
        tools=_tools,
        permission_validator=_permission_validator,
        short_term=_short_term,
        working_state=_working_state,
        long_term=_long_term,
        llm_client=llm_client,
    )
    logger.info("Using PlannerExecutorOrchestrator", extra={"orchestrator_type": orchestrator_type, "llm_provider": llm_provider})

else:
    # Default: sequential orchestrator
    _orchestrator = SequentialOrchestrator(
        agents=_agents,
        tools=_tools,
        permission_validator=_permission_validator,
        short_term=_short_term,
        working_state=_working_state,
        long_term=_long_term,
    )
    logger.info("Using SequentialOrchestrator", extra={"orchestrator_type": orchestrator_type})


@app.get("/healthz")
def healthz():
    return {"ok": True, "agents": [a.name for a in _agents], "tools": [t.name for t in _tools]}


@app.post("/run", response_model=TaskResponse)
def run_task(req: TaskRequest, _: None = Depends(require_api_key)):
    res = _orchestrator.run(task=req.task, session_id=req.session_id, user_id=req.user_id)
    return TaskResponse(agent=res.agent_name, success=res.success, output=res.output, error=res.error, meta=res.meta)


from agentos.agents.builder.schemas import PlanSummary


@app.post("/builder/scaffold", response_model=ScaffoldResponse)
def scaffold(req: ScaffoldRequest, _: None = Depends(require_api_key)):
    try:
        result = build_scaffold(kind=req.kind, name=req.name, description=req.description, risk=req.risk, root_dir=ROOT)
        return ScaffoldResponse(
            files=result.get("files", []),
            plan=result.get("plan"),
            unified_diff=result.get("unified_diff", ""),
            warnings=result.get("warnings", [])
        )
    except Exception as e:
        # Contract: return valid structure even on error
        error_plan = PlanSummary(
            name=req.name,
            description=req.description,
            changes=[],
            metadata={"error": str(e), "status": "failed"}
        )
        return ScaffoldResponse(
            files=[],
            plan=error_plan,
            unified_diff="",
            warnings=[f"Error generating scaffold: {str(e)}"]
        )


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
        
        # Validaciones de seguridad
        if not path_str:
            errors.append({"path": "(empty)", "error": "Path vacío"})
            continue
        
        # Bloquear rutas absolutas
        if path_str.startswith("/") or path_str.startswith("\\") or (len(path_str) > 1 and path_str[1] == ":"):
            errors.append({"path": path_str, "error": "Ruta absoluta no permitida"})
            continue
        
        # Bloquear path traversal
        if ".." in path_str:
            errors.append({"path": path_str, "error": "Path traversal (..) no permitido"})
            continue
        
        # Construir path relativo al ROOT del proyecto
        target_path = ROOT / path_str
        
        # Verificar que el path resultante sigue dentro de ROOT
        try:
            resolved = target_path.resolve()
            if not str(resolved).startswith(str(ROOT.resolve())):
                errors.append({"path": path_str, "error": "Path escapa del proyecto"})
                continue
        except Exception as e:
            errors.append({"path": path_str, "error": f"Error resolviendo path: {e}"})
            continue
        
        # Verificar si existe y si podemos sobrescribir
        if target_path.exists() and not req.overwrite:
            skipped.append(path_str)
            continue
        
        # Crear directorios padre si no existen
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding="utf-8")
            written.append(path_str)
            logger.info(f"Applied scaffold file: {path_str}")
        except Exception as e:
            errors.append({"path": path_str, "error": str(e)})
    
    return ApplyResponse(written=written, skipped=skipped, errors=errors)
