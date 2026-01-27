from __future__ import annotations

import json
import re
from typing import Dict, Optional, Any
from pathlib import Path

from agentos.agents.base.agent_base import AgentContext, BaseAgent, ExecutionResult
from .scaffold import ScaffoldManager
from .patch_generator import PatchGenerator


class BuilderAgent(BaseAgent):
    def can_handle(self, task: str) -> bool:
        t = task.lower()
        return "crear agente" in t or "crear tool" in t or "scaffold" in t

    def execute(self, task: str, ctx: AgentContext) -> ExecutionResult:
        ctx.logger.info(
            "BuilderAgent executing",
            extra={"request_id": ctx.request_id, "session_id": ctx.session_id, "user_id": ctx.user_id, "agent": self.name},
        )
        
        # Intentar parsear el task para extraer kind, name, description
        parsed = self._parse_task(task)
        
        if parsed is None:
            return ExecutionResult(
                agent_name=self.name,
                success=True,
                output=(
                    "No pude interpretar la solicitud. Usa formato:\n"
                    '\"Crear agente <nombre>: <descripción>\"\n'
                    '\"Crear tool <nombre>: <descripción>\"\n\n'
                    "O usa el endpoint POST /builder/scaffold directamente con kind=agent|tool."
                ),
            )
        
        kind, name, description = parsed
        
        try:
            # Usamos la lógica centralizada
            res = build_scaffold(kind=kind, name=name, description=description)
            files = res.get("files", [])
            
            # Formatear respuesta con el plan
            file_list = "\n".join([f"  - {f['path']}" for f in files])
            output = (
                f"Plan de scaffold generado (kind={kind}, name={name}):\n"
                f"Archivos a crear:\n{file_list}\n\n"
                f"Para aplicar, usa POST /builder/apply con el unified_diff o los archivos."
            )
            
            return ExecutionResult(
                agent_name=self.name,
                success=True,
                output=output,
                meta={"scaffold_plan": res, "kind": kind, "name": name}
            )
            
        except Exception as e:
            return ExecutionResult(
                agent_name=self.name,
                success=False,
                output="",
                error=str(e)
            )
    
    def _parse_task(self, task: str) -> tuple[str, str, str] | None:
        t = task.strip().lower()
        kind = None
        if "agente" in t or "agent" in t:
            kind = "agent"
        elif "tool" in t or "herramienta" in t:
            kind = "tool"
        
        if kind is None:
            return None
        
        patterns = [
            r"(?:crear|scaffold)\s+(?:agente|agent|tool|herramienta)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*[:\-]\s*(.+)",
            r"(?:crear|scaffold)\s+(?:agente|agent|tool|herramienta)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+(.+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, task, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                description = match.group(2).strip()
                return (kind, name, description)
        
        return None


def build_scaffold(kind: str, name: str, description: str, risk: str = "read", root_dir: Optional[str | Path] = None) -> Dict[str, Any]:
    # Si no se provee root_dir, intentamos derivarlo de forma segura
    if root_dir is None:
        # Fallback al directorio del archivo actual -> parents[3] para llegar al root del repo
        root_dir = Path(__file__).resolve().parents[3]
    else:
        root_dir = Path(root_dir).resolve()

    manager = ScaffoldManager(root_dir)
    generator = PatchGenerator(root_dir)
    
    kind = (kind or "").strip().lower()
    try:
        if kind == "agent":
            plan = manager.create_agent_scaffold(name=name, description=description)
        elif kind == "tool":
            plan = manager.create_tool_scaffold(name=name, description=description, risk=risk)
        else:
            raise ValueError("kind debe ser: agent | tool")
        
        diff = generator.generate_unified_diff(plan)
        
        # Estructuramos el plan_summary para la API (v2.3)
        plan_summary = {
            "name": plan.name,
            "description": plan.description,
            "changes": [{"path": c.path, "operation": c.operation} for c in plan.changes],
            "metadata": plan.metadata
        }
        
        return {
            "plan": plan_summary,
            "files": [{"path": c.path, "content": c.content} for c in plan.changes],
            "unified_diff": diff,
            "warnings": []
        }
    except Exception as e:
        # Contrato de error consistente con PlanSummary (v2.3)
        return {
            "error": str(e),
            "plan": {
                "name": "Error de Generación",
                "description": str(e),
                "changes": [],
                "metadata": {}
            },
            "files": [],
            "unified_diff": "",
            "warnings": [f"Error en generación: {str(e)}"]
        }
