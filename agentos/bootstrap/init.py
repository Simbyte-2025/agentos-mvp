"""Application bootstrap — creates and wires all runtime singletons.

Extracted from api/main.py to enable:
- Testability (inject mock components)
- CLI usage without FastAPI
- Clear initialization order
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any, Dict, List

import yaml

from agentos.agents.base.agent_base import BaseAgent
from agentos.bootstrap.cleanup import register_cleanup
from agentos.bootstrap.state import AppState
from agentos.memory.long_term import LongTermMemory
from agentos.memory.short_term import ShortTermMemory
from agentos.memory.working_state import WorkingStateStore
from agentos.observability.logging import get_logger
from agentos.observability.metrics import MetricsCollector
from agentos.security.denial_tracking import DenialTracker
from agentos.security.permissions import PermissionValidator, load_profiles
from agentos.tools.base import BaseTool
from agentos.tools.executor import ToolExecutor

logger = get_logger("agentos")


def _import_class(class_path: str):
    module_name, class_name = class_path.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


def _load_yaml(path: Path) -> Dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _bootstrap_agents(config_dir: Path) -> List[BaseAgent]:
    cfg = _load_yaml(config_dir / "agents.yaml")
    agents: List[BaseAgent] = []
    for a in cfg.get("agents", []):
        cls = _import_class(a["class_path"])
        agents.append(cls(name=a["name"], description=a.get("description", ""), profile=a.get("profile", a["name"])))
    return agents


def _bootstrap_tools(config_dir: Path) -> List[BaseTool]:
    cfg = _load_yaml(config_dir / "tools.yaml")
    tools: List[BaseTool] = []
    for t in cfg.get("tools", []):
        cls = _import_class(t["class_path"])
        tool_config = t.get("config")
        tools.append(cls(config=tool_config) if tool_config else cls())
    return tools


def _create_orchestrator(state: AppState) -> Any:
    """Create orchestrator based on env flags and wire it into state."""
    orchestrator_type = (os.getenv("AGENTOS_ORCHESTRATOR") or "sequential").lower().strip()
    llm_provider = (os.getenv("AGENTOS_LLM_PROVIDER") or os.getenv("AGENTOS_LLM") or "").lower().strip()

    state.orchestrator_type = orchestrator_type
    state.llm_provider = llm_provider

    if orchestrator_type == "planner":
        from agentos.llm.dummy import DummyLLM
        from agentos.llm.minimax import MinimaxClient
        from agentos.orchestrators.planner_executor import PlannerExecutorOrchestrator

        llm_client = None

        if llm_provider == "dummy":
            llm_client = DummyLLM()
            logger.info("Using DummyLLM for planner orchestrator")
        elif llm_provider == "minimax":
            api_key = os.getenv("MINIMAX_API_KEY")
            base_url = os.getenv("MINIMAX_BASE_URL", "https://api.minimax.io/anthropic")
            model = os.getenv("MINIMAX_MODEL", "MiniMax-M2.1")
            llm_client = MinimaxClient(api_key=api_key, base_url=base_url, model=model)
            if api_key:
                logger.info("Using MinimaxClient for planner orchestrator")
            else:
                logger.warning("MinimaxClient configured but MINIMAX_API_KEY not set.")

        if llm_client is None:
            raise ValueError(
                f"AGENTOS_ORCHESTRATOR=planner requiere un proveedor LLM válido. "
                f"Proveedor actual: '{llm_provider}' (soportados: minimax, dummy)"
            )

        return PlannerExecutorOrchestrator(
            agents=state.agents,
            tools=state.tools,
            permission_validator=state.permission_validator,
            short_term=state.short_term,
            working_state=state.working_state,
            long_term=state.long_term,
            llm_client=llm_client,
            metrics=state.metrics,
            denial_tracker=state.denial_tracker,
            tool_executor=state.tool_executor,
        )
    else:
        from agentos.orchestrators.sequential import SequentialOrchestrator
        return SequentialOrchestrator(
            agents=state.agents,
            tools=state.tools,
            permission_validator=state.permission_validator,
            short_term=state.short_term,
            working_state=state.working_state,
            long_term=state.long_term,
            metrics=state.metrics,
            denial_tracker=state.denial_tracker,
            tool_executor=state.tool_executor,
        )


def bootstrap(root: Path | None = None) -> AppState:
    """Create and wire all runtime singletons. Returns a fully initialized AppState."""
    if root is None:
        root = Path(__file__).resolve().parents[2]
    config_dir = root / "config"

    agents = _bootstrap_agents(config_dir)
    tools = _bootstrap_tools(config_dir)
    profiles = load_profiles(config_dir / "profiles.yaml")
    permission_validator = PermissionValidator(profiles)

    short_term = ShortTermMemory(max_items=50)
    working_state = WorkingStateStore(db_path=root / "agentos_state.db")
    long_term = LongTermMemory()

    # Register cleanups
    if hasattr(working_state, "close"):
        register_cleanup(working_state.close, "WorkingStateStore")
    if hasattr(long_term, "close"):
        register_cleanup(long_term.close, "LongTermMemory")

    metrics = MetricsCollector()
    denial_tracker = DenialTracker()
    tool_executor = ToolExecutor()
    register_cleanup(lambda: tool_executor.shutdown(wait=False), "ToolExecutor")

    state = AppState(
        agents=agents,
        tools=tools,
        permission_validator=permission_validator,
        short_term=short_term,
        working_state=working_state,
        long_term=long_term,
        denial_tracker=denial_tracker,
        metrics=metrics,
        tool_executor=tool_executor,
    )

    state.orchestrator = _create_orchestrator(state)
    logger.info(
        "Bootstrap complete",
        extra={"orchestrator": state.orchestrator_type, "llm_provider": state.llm_provider},
    )
    return state
