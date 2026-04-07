"""Planner-Executor orchestrator with replanning capabilities."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional

import time

from agentos.agents.base.agent_base import AgentContext, BaseAgent, ExecutionResult
from agentos.llm.base import LLMClient
from agentos.memory.compaction import ContextCompactor
from agentos.memory.long_term import LongTermMemory
from agentos.memory.session_transcript import SessionTranscript
from agentos.memory.short_term import ShortTermMemory
from agentos.memory.working_state import WorkingStateStore
from agentos.observability.logging import get_logger
from agentos.observability.metrics import MetricsCollector
from agentos.prompts.base import COORDINATOR_PROMPT
from agentos.prompts.sections import PromptSection, build_system_prompt
from agentos.security.denial_tracking import DenialTracker
from agentos.security.permissions import PermissionValidator
from agentos.tools.base import BaseTool
from agentos.tools.executor import ToolExecutor

from .router import AgentRouter, ToolRouter

# Configuration constants
MAX_REPLANS = 2
MAX_RETRIES_PER_TASK = 2


@dataclass
class Subtask:
    """Represents a subtask in the plan."""
    id: str
    objetivo: str
    criterios_exito: List[str]
    dependencies: List[str] = field(default_factory=list)
    status: str = "pending"  # pending, running, success, failed
    error: Optional[str] = None
    output: Optional[str] = None
    retry_count: int = 0
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)


class PlannerExecutorOrchestrator:
    """Orchestrator that plans tasks into subtasks, executes them, and replans on failure.
    
    This orchestrator uses an LLM to:
    1. Plan: Break down complex tasks into subtasks
    2. Execute: Run each subtask using agents and tools
    3. Replan: Generate new plans when subtasks fail
    
    It includes safeguards like retry limits and robust JSON parsing.
    """

    def __init__(
        self,
        agents: List[BaseAgent],
        tools: List[BaseTool],
        permission_validator: PermissionValidator,
        short_term: ShortTermMemory,
        working_state: WorkingStateStore,
        long_term: LongTermMemory,
        llm_client: LLMClient,
        metrics: Optional[MetricsCollector] = None,
        denial_tracker: Optional[DenialTracker] = None,
        tool_executor: Optional[ToolExecutor] = None,
    ):
        self.agents = agents
        self.tools = tools
        self.permission_validator = permission_validator
        self.short_term = short_term
        self.working_state = working_state
        self.long_term = long_term
        self.llm_client = llm_client
        self.metrics = metrics or MetricsCollector()
        self.denial_tracker = denial_tracker or DenialTracker()
        self.tool_executor = tool_executor or ToolExecutor()
        self.agent_router = AgentRouter()
        self.tool_router = ToolRouter(top_k=3)
        self.compactor = ContextCompactor()
        self.logger = get_logger("agentos")

    def run(self, task: str, session_id: str, user_id: str, request_id: str | None = None) -> ExecutionResult:
        """Execute a task using planner-executor pattern with replanning.
        
        Args:
            task: The task to execute
            session_id: Session identifier
            user_id: User identifier
            request_id: Optional request identifier
            
        Returns:
            ExecutionResult with aggregated results from all subtasks
        """
        rid = request_id or str(uuid.uuid4())
        start = time.monotonic()
        self.metrics.record_request()

        # Session transcript persistence
        transcript = SessionTranscript(session_id)
        transcript.append("user", task)

        # Restaurar historial previo
        try:
            history = self.working_state.load_checkpoint(session_id, "conversation_history")
            if history and isinstance(history, dict):
                for msg in history.get("messages", []):
                    self.short_term.add(session_id, msg)
        except Exception:
            pass

        self.logger.info(
            "PlannerExecutorOrchestrator starting",
            extra={"request_id": rid, "session_id": session_id, "user_id": user_id, "task": task}
        )
        
        # Add task to short-term memory
        self.short_term.add(session_id, f"USER: {task}")

        # Initial planning
        subtasks = self._plan(task, rid, session_id)
        
        if not subtasks:
            # Fallback: execute as single task
            self.logger.warning(
                "No subtasks generated, executing as single task",
                extra={"request_id": rid}
            )
            return self._execute_as_single_task(task, session_id, user_id, rid)
        
        # Execute plan with replanning
        replan_count = 0
        all_outputs: List[str] = []
        
        while replan_count <= MAX_REPLANS:
            self.logger.info(
                "Executing plan",
                extra={"request_id": rid, "replan_count": replan_count, "subtask_count": len(subtasks)}
            )
            
            # Execute all subtasks
            failed_subtasks: List[Subtask] = []
            
            for subtask in subtasks:
                if subtask.status == "success":
                    # Already completed in previous iteration
                    if subtask.output:
                        all_outputs.append(subtask.output)
                    continue
                
                result = self._execute_subtask(subtask, task, session_id, user_id, rid)
                
                if result.success:
                    subtask.status = "success"
                    subtask.output = result.output
                    all_outputs.append(result.output)
                    
                    # Save to long-term memory
                    if result.output:
                        self.long_term.add(result.output, tags=["planner_executor", subtask.id])
                else:
                    subtask.retry_count += 1
                    
                    if subtask.retry_count >= MAX_RETRIES_PER_TASK:
                        subtask.status = "failed"
                        subtask.error = result.error
                        failed_subtasks.append(subtask)
                        self.logger.error(
                            "Subtask failed after max retries",
                            extra={"request_id": rid, "subtask_id": subtask.id, "error": result.error}
                        )
                    else:
                        subtask.status = "pending"
                        self.logger.warning(
                            "Subtask failed, will retry",
                            extra={"request_id": rid, "subtask_id": subtask.id, "retry_count": subtask.retry_count}
                        )
            
            # Check if all subtasks succeeded
            if all(st.status == "success" for st in subtasks):
                self.logger.info(
                    "All subtasks completed successfully",
                    extra={"request_id": rid, "subtask_count": len(subtasks)}
                )
                break
            
            # Check if we should replan
            if failed_subtasks and replan_count < MAX_REPLANS:
                replan_count += 1
                self.logger.info(
                    "Replanning due to failed subtasks",
                    extra={"request_id": rid, "replan_count": replan_count, "failed_count": len(failed_subtasks)}
                )
                
                # Generate new plan
                subtasks = self._replan(task, subtasks, failed_subtasks, rid, session_id)
                
                if not subtasks:
                    # Replan failed, break
                    break
            else:
                # Max replans reached or no failed subtasks
                break
        
        # Aggregate results
        success = all(st.status == "success" for st in subtasks)
        final_output = "\n\n".join(all_outputs) if all_outputs else ""
        
        # Collect errors from failed subtasks
        errors = [st.error for st in subtasks if st.status == "failed" and st.error]
        final_error = "; ".join(errors) if errors else None
        
        # Save checkpoint
        self.working_state.save_checkpoint(
            session_id=session_id,
            name="last_result",
            data={
                "agent": "planner_executor",
                "success": success,
                "output": final_output,
                "error": final_error,
                "meta": {
                    "subtasks": [
                        {
                            "id": st.id,
                            "objetivo": st.objetivo,
                            "status": st.status,
                            "tool_calls": st.tool_calls,
                            "error": st.error
                        }
                        for st in subtasks
                    ],
                    "replan_count": replan_count
                }
            },
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        
        # Add to short-term memory
        self.short_term.add(session_id, f"AGENT(planner_executor): {final_output}")

        # Session transcript
        transcript.append("agent", final_output or "", meta={
            "agent": "planner_executor",
            "success": success,
            "subtask_count": len(subtasks),
            "replan_count": replan_count,
        })

        # Metrics
        duration_ms = (time.monotonic() - start) * 1000
        if success:
            self.metrics.record_success(duration_ms=duration_ms)
        else:
            self.metrics.record_error(final_error or "ORCHESTRATION_FAILED")

        # Compaction check
        messages = self.short_term.get(session_id)
        if self.compactor.should_trim(messages):
            compacted = self.compactor.trim_tool_results(messages)
            self.short_term._data[session_id].clear()
            for msg in compacted:
                self.short_term._data[session_id].append(msg)

        # Persistir historial de conversación
        try:
            messages = self.short_term.get(session_id)
            if messages:
                self.working_state.save_checkpoint(
                    session_id, "conversation_history",
                    {"messages": list(messages)},
                    datetime.now(timezone.utc).isoformat(),
                )
        except Exception:
            pass

        self.logger.info(
            "PlannerExecutorOrchestrator completed",
            extra={
                "request_id": rid,
                "success": success,
                "subtask_count": len(subtasks),
                "replan_count": replan_count
            }
        )
        
        return ExecutionResult(
            agent_name="planner_executor",
            success=success,
            output=final_output,
            error=final_error,
            meta={
                "subtasks": [{"id": st.id, "status": st.status} for st in subtasks],
                "replan_count": replan_count
            }
        )

    def _plan(self, task: str, request_id: str, session_id: str) -> List[Subtask]:
        """Generate a plan (list of subtasks) using the LLM.
        
        Args:
            task: The task to plan
            request_id: Request identifier for logging
            session_id: Session identifier for memory retrieval
            
        Returns:
            List of Subtask objects, or empty list if planning fails
        """
        # Retrieve context from memory
        retrieved = self.long_term.retrieve(task)
        context_items = [it.text for it in retrieved]
        
        # Build planning prompt
        context_str = "\n".join(f"- {c}" for c in context_items[:3]) if context_items else ""
        prompt = self._build_planning_prompt(task, context_str)
        
        try:
            # Generate plan using LLM
            response = self.llm_client.generate(prompt)
            
            # Log raw response for debugging JSON errors
            self.logger.info(
                f"Raw plan response received len={len(response)} snippet={response[:800]!r}",
                extra={"request_id": request_id}
            )
            
            # Parse and validate JSON response
            subtasks = self._parse_plan_response(response, request_id)
            
            self.logger.info(
                "Plan generated successfully",
                extra={"request_id": request_id, "subtask_count": len(subtasks)}
            )
            
            return subtasks
            
        except Exception as e:
            self.logger.error(
                "Planning failed",
                extra={"request_id": request_id, "error": str(e)}
            )
            self.logger.error(
                f"Planning error details -> type: {type(e).__name__}, msg: {str(e)}",
                extra={"request_id": request_id, "error_type": type(e).__name__, "error_msg": str(e)}
            )
            # Return empty list to trigger fallback
            return []

    def _replan(
        self,
        task: str,
        current_subtasks: List[Subtask],
        failed_subtasks: List[Subtask],
        request_id: str,
        session_id: str
    ) -> List[Subtask]:
        """Generate a new plan based on failed subtasks.
        
        Args:
            task: Original task
            current_subtasks: Current list of subtasks
            failed_subtasks: Subtasks that failed
            request_id: Request identifier
            session_id: Session identifier
            
        Returns:
            New list of subtasks, or empty list if replanning fails
        """
        # Build replanning prompt with context about failures
        prompt = self._build_replanning_prompt(task, current_subtasks, failed_subtasks)
        
        try:
            response = self.llm_client.generate(prompt)
            
            # Log raw response for debugging JSON errors
            self.logger.info(
                f"Raw replan response received len={len(response)} snippet={response[:800]!r}",
                extra={"request_id": request_id}
            )

            new_subtasks = self._parse_plan_response(response, request_id)
            
            self.logger.info(
                "Replan generated successfully",
                extra={"request_id": request_id, "new_subtask_count": len(new_subtasks)}
            )
            
            return new_subtasks
            
        except Exception as e:
            self.logger.error(
                "Replanning failed",
                extra={"request_id": request_id, "error": str(e)}
            )
            self.logger.error(
                f"Replanning error details -> type: {type(e).__name__}, msg: {str(e)}",
                extra={"request_id": request_id, "error_type": type(e).__name__, "error_msg": str(e)}
            )
            return []

    def _execute_subtask(
        self,
        subtask: Subtask,
        original_task: str,
        session_id: str,
        user_id: str,
        request_id: str
    ) -> ExecutionResult:
        """Execute a single subtask using agent router and tools.
        
        Args:
            subtask: The subtask to execute
            original_task: Original task for context
            session_id: Session identifier
            user_id: User identifier
            request_id: Request identifier
            
        Returns:
            ExecutionResult from the agent execution
        """
        subtask.status = "running"

        self.logger.info(
            "Executing subtask",
            extra={
                "request_id": request_id,
                "subtask_id": subtask.id,
                "objetivo": subtask.objetivo
            }
        )

        try:
            # Select agent for this subtask
            agent = self.agent_router.select_agent(subtask.objetivo, self.agents)

            if agent is None:
                return ExecutionResult(
                    agent_name="none",
                    success=False,
                    output="",
                    error="No hay agentes cargados"
                )

            # Select tools for this subtask with denial tracking
            selected_tools: List[BaseTool] = []
            for t in self.tools:
                decision = self.permission_validator.validate_tool_access(agent.profile, t.name, t.risk)
                if decision.allowed:
                    selected_tools.append(t)
                    self.denial_tracker.record_success(session_id)
                else:
                    self.denial_tracker.record_denial(session_id, t.name, t.risk)

            selected_tools = self.tool_router.select_tools(
                subtask.objetivo,
                agent.profile,
                selected_tools,
                self.permission_validator
            )
            tool_map: Mapping[str, BaseTool] = {t.name: t for t in selected_tools}

            # Build context
            ctx = AgentContext(
                request_id=request_id,
                session_id=session_id,
                user_id=user_id,
                tools=tool_map,
                memory={
                    "short_term": self.short_term.get(session_id),
                    "retrieved": [],
                    "original_task": original_task,
                    "subtask_objetivo": subtask.objetivo,
                    "criterios_exito": subtask.criterios_exito,
                    "llm_client": self.llm_client,
                },
                logger=self.logger,
            )

            # Execute
            result = agent.execute(subtask.objetivo, ctx)

            # Track tool calls if available
            if result.meta and "tool_calls" in result.meta:
                subtask.tool_calls = result.meta["tool_calls"]

            self.logger.info(
                "Subtask execution completed",
                extra={
                    "request_id": request_id,
                    "subtask_id": subtask.id,
                    "success": result.success,
                    "agent": result.agent_name
                }
            )

            return result

        except Exception as e:
            self.logger.error(
                f"Subtask {subtask.id} raised: {e}",
                extra={"request_id": request_id, "subtask_id": subtask.id}
            )
            return ExecutionResult(
                agent_name="error",
                success=False,
                output="",
                error=str(e)
            )

        finally:
            self._cleanup_subtask_resources(subtask)

    def _cleanup_subtask_resources(self, subtask: Subtask) -> None:
        """Hook de cleanup por subtask. Override para recursos específicos."""
        pass  # extensible sin romper subclases

    def _execute_as_single_task(
        self,
        task: str,
        session_id: str,
        user_id: str,
        request_id: str
    ) -> ExecutionResult:
        """Fallback: execute task as a single subtask without planning.
        
        This is used when planning fails or returns no subtasks.
        """
        self.logger.info(
            "Executing as single task (fallback)",
            extra={"request_id": request_id}
        )
        
        # Create a single subtask
        subtask = Subtask(
            id="1",
            objetivo=task,
            criterios_exito=["Tarea completada"]
        )
        
        return self._execute_subtask(subtask, task, session_id, user_id, request_id)

    def _parse_plan_response(self, response: str, request_id: str) -> List[Subtask]:
        """Parse and validate LLM response into subtasks.
        
        Implements robust parsing with validation and fallback.
        
        Args:
            response: JSON string from LLM
            request_id: Request identifier for logging
            
        Returns:
            List of validated Subtask objects
            
        Raises:
            ValueError: If JSON is invalid or structure is incorrect
        """
        try:
            # Parse JSON
            # Clean markdown code fences if present
            clean = response.strip()
            if clean.startswith("```"):
                # Remove first line (open fence)
                clean = clean.split("\n", 1)[1]
                # Remove last fence if present
                if clean.rstrip().endswith("```"):
                    clean = clean.rstrip()[:-3]
                clean = clean.strip()
            
            data = json.loads(clean)
            
            # Validate structure
            if not isinstance(data, dict):
                raise ValueError("Response is not a JSON object")
            
            if "subtasks" not in data:
                raise ValueError("Response missing 'subtasks' field")
            
            if not isinstance(data["subtasks"], list):
                raise ValueError("'subtasks' is not a list")
            
            # Parse and validate each subtask
            subtasks: List[Subtask] = []
            
            for i, st_data in enumerate(data["subtasks"]):
                if not isinstance(st_data, dict):
                    self.logger.warning(
                        "Skipping invalid subtask (not an object)",
                        extra={"request_id": request_id, "index": i}
                    )
                    continue
                
                # Validate required fields
                if "id" not in st_data or "objetivo" not in st_data:
                    self.logger.warning(
                        "Skipping subtask missing required fields",
                        extra={"request_id": request_id, "index": i, "data": st_data}
                    )
                    continue
                
                # Extract fields with defaults
                subtask_id = str(st_data["id"])
                objetivo = str(st_data["objetivo"])
                criterios_exito = st_data.get("criterios_exito", [])
                
                # Ensure criterios_exito is a list
                if not isinstance(criterios_exito, list):
                    criterios_exito = [str(criterios_exito)]
                
                # Parse dependencies if present
                deps = st_data.get("dependencias", st_data.get("dependencies", []))
                if not isinstance(deps, list):
                    deps = []
                deps = [str(d) for d in deps]

                subtasks.append(Subtask(
                    id=subtask_id,
                    objetivo=objetivo,
                    criterios_exito=criterios_exito,
                    dependencies=deps,
                ))
            
            if not subtasks:
                raise ValueError("No valid subtasks found in response")
            
            return subtasks
            
        except json.JSONDecodeError as e:
            self.logger.error(
                "Failed to parse JSON response",
                extra={"request_id": request_id, "error": str(e), "response": response[:200]}
            )
            raise ValueError(f"Invalid JSON: {e}")
        
        except ValueError as e:
            self.logger.error(
                "Invalid plan structure",
                extra={"request_id": request_id, "error": str(e)}
            )
            raise

    @staticmethod
    def _build_execution_order(subtasks: List[Subtask]) -> List[List[Subtask]]:
        """Topological sort of subtasks into execution layers.

        Returns a list of layers. Subtasks within the same layer have all
        dependencies satisfied and can run concurrently. If there are
        circular or unresolvable dependencies, remaining subtasks are
        appended as a final layer (best-effort).
        """
        by_id = {st.id: st for st in subtasks}
        remaining = set(by_id.keys())
        completed_ids: set = set()
        layers: List[List[Subtask]] = []

        while remaining:
            # Find subtasks whose deps are all completed
            ready = [
                sid for sid in remaining
                if all(d in completed_ids or d not in by_id for d in by_id[sid].dependencies)
            ]
            if not ready:
                # Circular / unresolvable — dump remaining into last layer
                layers.append([by_id[sid] for sid in sorted(remaining)])
                break
            layer = [by_id[sid] for sid in ready]
            layers.append(layer)
            for sid in ready:
                remaining.discard(sid)
                completed_ids.add(sid)

        return layers

    def _build_planning_prompt(self, task: str, context_str: str = "") -> str:
        """Build prompt for initial planning using PromptSection composition.

        Args:
            task: The task to plan
            context_str: Pre-formatted context string from long-term memory

        Returns:
            Formatted prompt string
        """
        sections = [
            PromptSection("coordinator_role", lambda: COORDINATOR_PROMPT, cached=True),
            PromptSection("available_agents", lambda: self._get_agents_context(), cached=True),
            PromptSection("task", lambda t=task: f"## Tarea a planificar\n{t}", cached=False),
            PromptSection("context", lambda c=context_str: f"## Contexto relevante\n{c}" if c else None, cached=False),
            PromptSection("output_format", lambda: (
                "## Formato de respuesta\n"
                "Responde SOLO con JSON válido:\n"
                '{"subtasks": [{"id": "st_1", "objetivo": "...", "agente": "nombre_agente", "dependencias": []}]}'
            ), cached=True),
        ]
        return build_system_prompt(sections)

    def _get_agents_context(self) -> str:
        """Describe los agentes disponibles para el coordinator."""
        try:
            agent_names = [a.profile.name for a in self.agents] if self.agents else []
            if agent_names:
                return "## Agentes disponibles\n" + "\n".join(f"- {name}" for name in agent_names)
        except Exception:
            pass
        return ""

    def _build_replanning_prompt(
        self,
        task: str,
        current_subtasks: List[Subtask],
        failed_subtasks: List[Subtask]
    ) -> str:
        """Build prompt for replanning after failures.
        
        Args:
            task: Original task
            current_subtasks: Current subtasks
            failed_subtasks: Subtasks that failed
            
        Returns:
            Formatted prompt string
        """
        failed_info = "\n".join(
            f"- Subtarea {st.id}: {st.objetivo} (Error: {st.error or 'desconocido'})"
            for st in failed_subtasks
        )
        
        return f"""Eres un planificador de tareas. La ejecución anterior falló. Genera un nuevo plan.

Tarea original: {task}

Subtareas que fallaron:
{failed_info}

Genera un plan alternativo que evite los errores anteriores.

Responde SOLO con un JSON válido en este formato exacto:
{{
  "subtasks": [
    {{
      "id": "1",
      "objetivo": "descripción clara de la subtarea",
      "criterios_exito": ["criterio 1", "criterio 2"]
    }}
  ]
}}

Reglas:
- Intenta un enfoque diferente para las subtareas fallidas
- Los IDs deben ser únicos
- Incluye 1-5 subtareas máximo
- NO incluyas texto adicional fuera del JSON"""
