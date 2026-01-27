from __future__ import annotations

import json
import re
from typing import Dict

from agentos.agents.base.agent_base import AgentContext, BaseAgent, ExecutionResult
from .scaffold import scaffold_agent, scaffold_tool


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
            # No se pudo parsear, devolver guía de uso
            return ExecutionResult(
                agent_name=self.name,
                success=True,
                output=(
                    "No pude interpretar la solicitud. Usa formato:\\n"
                    '"Crear agente <nombre>: <descripción>"\\n'
                    '"Crear tool <nombre>: <descripción>"\\n\\n'
                    "O usa el endpoint POST /builder/scaffold directamente con kind=agent|tool."
                ),
            )
        
        kind, name, description = parsed
        
        try:
            plan = build_scaffold(kind=kind, name=name, description=description)
            files = plan.get("files", [])
            
            # Formatear respuesta con el plan
            file_list = "\\n".join([f"  - {f['path']}" for f in files])
            output = (
                f"Plan de scaffold generado (kind={kind}, name={name}):\\n"
                f"Archivos a crear:\\n{file_list}\\n\\n"
                f"Para aplicar, usa POST /builder/apply con:\\n"
                f'{json.dumps({"files": files}, indent=2, ensure_ascii=False)}'
            )
            
            return ExecutionResult(
                agent_name=self.name,
                success=True,
                output=output,
                meta={"scaffold_plan": plan, "kind": kind, "name": name}
            )
            
        except ValueError as e:
            return ExecutionResult(
                agent_name=self.name,
                success=False,
                output="",
                error=str(e)
            )
    
    def _parse_task(self, task: str) -> tuple[str, str, str] | None:
        """Parsear task para extraer kind, name, description.
        
        Formatos soportados:
        - "Crear agente <nombre>: <descripción>"
        - "Crear tool <nombre>: <descripción>"
        - "scaffold agent <nombre>: <descripción>"
        - "scaffold tool <nombre>: <descripción>"
        
        Returns:
            Tuple (kind, name, description) o None si no se puede parsear
        """
        t = task.strip().lower()
        
        # Detectar kind
        kind = None
        if "agente" in t or "agent" in t:
            kind = "agent"
        elif "tool" in t or "herramienta" in t:
            kind = "tool"
        
        if kind is None:
            return None
        
        # Extraer nombre y descripción con regex
        # Patrones: "crear agente <nombre>: <desc>" o "crear agente <nombre> - <desc>"
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


def build_scaffold(kind: str, name: str, description: str, risk: str = "read") -> Dict:
    kind = (kind or "").strip().lower()
    if kind == "agent":
        return scaffold_agent(name=name, description=description)
    if kind == "tool":
        return scaffold_tool(name=name, description=description, risk=risk)
    raise ValueError("kind debe ser: agent | tool")

