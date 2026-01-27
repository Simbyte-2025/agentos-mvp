from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Any

from agentos.agents.builder.schemas import PlanSummary, PlanChange
from agentos.agents.builder.patch_generator import PatchGenerator
from agentos.security.path_policy import PathPolicy


def scaffold_agent(name: str, description: str, root_dir: Path) -> Dict[str, Any]:
    safe_name = name.strip().lower().replace(" ", "_")
    class_name = "".join([p.capitalize() for p in safe_name.split("_")]) + "Agent"
    
    # Definir archivos propuestos (paths relativos)
    proposed_files = [
        {
            "path": f"agentos/agents/specialist/{safe_name}_agent.py",
            "content": f"""from __future__ import annotations\n\nfrom agentos.agents.base.agent_base import AgentContext, BaseAgent, ExecutionResult\n\n\nclass {class_name}(BaseAgent):\n    \"\"\"{description}\"\"\"\n\n    def can_handle(self, task: str) -> bool:\n        # TODO: definir keywords o un clasificador\n        return False\n\n    def execute(self, task: str, ctx: AgentContext) -> ExecutionResult:\n        # TODO: implementar lógica real\n        return ExecutionResult(agent_name=self.name, success=True, output=\"TODO\")\n"""
        },
        {
            "path": f"tests/unit/test_{safe_name}_agent.py",
            "content": f"""from agentos.agents.specialist.{safe_name}_agent import {class_name}\n\n\ndef test_{safe_name}_agent_smoke():\n    a = {class_name}(name=\"{safe_name}_agent\", description=\"{description}\", profile=\"{safe_name}_agent\")\n    assert a.name\n"""
        }
    ]

    return _build_response_payload(name, description, proposed_files, root_dir)


def scaffold_tool(name: str, description: str, root_dir: Path, risk: str = "read") -> Dict[str, Any]:
    safe_name = name.strip().lower().replace(" ", "_")
    class_name = "".join([p.capitalize() for p in safe_name.split("_")]) + "Tool"

    proposed_files = [
        {
            "path": f"agentos/tools/{safe_name}.py",
            "content": f"""from __future__ import annotations\n\nfrom agentos.tools.base import BaseTool, ToolInput, ToolOutput\n\n\nclass {class_name}(BaseTool):\n    \"\"\"{description}\"\"\"\n\n    def __init__(self):\n        super().__init__(name=\"{safe_name}\", description=\"{description}\", risk=\"{risk}\")\n\n    def execute(self, tool_input: ToolInput) -> ToolOutput:\n        # TODO: implementar\n        return ToolOutput(success=True, data={{}})\n"""
        },
        {
            "path": f"tests/unit/test_{safe_name}_tool.py",
            "content": f"""from agentos.tools.{safe_name} import {class_name}\n\n\ndef test_{safe_name}_tool_smoke():\n    t = {class_name}()\n    assert t.name == \"{safe_name}\"\n"""
        }
    ]

    return _build_response_payload(name, description, proposed_files, root_dir)


def _build_response_payload(name: str, description: str, proposed_files: List[Dict[str, str]], root_dir: Path) -> Dict[str, Any]:
    """Construye la respuesta completa validando security y generando diffs."""
    
    policy = PathPolicy(root_dir)
    changes: List[PlanChange] = []
    files_out: List[Dict[str, str]] = []
    warnings: List[str] = []

    for f in proposed_files:
        path_str = f["path"]
        content = f["content"]
        
        # Validar path contra política
        try:
            policy.validate_path(path_str)
            
            # Si pasa validación, agregamos al plan
            changes.append(PlanChange(path=path_str, operation="create", content=content))
            files_out.append({"path": path_str, "content": content})
            
        except ValueError as e:
            warnings.append(f"Skipped {path_str}: {str(e)}")

    # Construir Plan
    plan = PlanSummary(
        name=name,
        description=description,
        changes=changes,
        metadata={"warnings_count": len(warnings)}
    )

    # Generar Diff
    unified_diff = PatchGenerator.generate(plan)

    # Retornar payload completo (dict para facilitar integración con legacy/API models por ahora)
    return {
        "files": files_out,
        "plan": plan,
        "unified_diff": unified_diff,
        "warnings": warnings
    }
