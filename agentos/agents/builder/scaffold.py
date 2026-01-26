from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List


@dataclass
class ScaffoldFile:
    path: str
    content: str


def scaffold_agent(name: str, description: str) -> Dict[str, List[Dict[str, str]]]:
    safe_name = name.strip().lower().replace(" ", "_")
    class_name = "".join([p.capitalize() for p in safe_name.split("_")]) + "Agent"

    files = [
        ScaffoldFile(
            path=f"agentos/agents/specialist/{safe_name}_agent.py",
            content=f"""from __future__ import annotations\n\nfrom agentos.agents.base.agent_base import AgentContext, BaseAgent, ExecutionResult\n\n\nclass {class_name}(BaseAgent):\n    \"\"\"{description}\"\"\"\n\n    def can_handle(self, task: str) -> bool:\n        # TODO: definir keywords o un clasificador\n        return False\n\n    def execute(self, task: str, ctx: AgentContext) -> ExecutionResult:\n        # TODO: implementar lógica real\n        return ExecutionResult(agent_name=self.name, success=True, output=\"TODO\")\n""",
        ),
        ScaffoldFile(
            path=f"tests/unit/test_{safe_name}_agent.py",
            content=f"""from agentos.agents.specialist.{safe_name}_agent import {class_name}\n\n\ndef test_{safe_name}_agent_smoke():\n    a = {class_name}(name=\"{safe_name}_agent\", description=\"{description}\", profile=\"{safe_name}_agent\")\n    assert a.name\n""",
        ),
    ]

    return {"files": [asdict(f) for f in files]}


def scaffold_tool(name: str, description: str, risk: str = "read") -> Dict[str, List[Dict[str, str]]]:
    safe_name = name.strip().lower().replace(" ", "_")
    class_name = "".join([p.capitalize() for p in safe_name.split("_")]) + "Tool"

    files = [
        ScaffoldFile(
            path=f"agentos/tools/{safe_name}.py",
            content=f"""from __future__ import annotations\n\nfrom agentos.tools.base import BaseTool, ToolInput, ToolOutput\n\n\nclass {class_name}(BaseTool):\n    \"\"\"{description}\"\"\"\n\n    def __init__(self):\n        super().__init__(name=\"{safe_name}\", description=\"{description}\", risk=\"{risk}\")\n\n    def execute(self, tool_input: ToolInput) -> ToolOutput:\n        # TODO: implementar\n        return ToolOutput(success=True, data={{}})\n""",
        ),
        ScaffoldFile(
            path=f"tests/unit/test_{safe_name}_tool.py",
            content=f"""from agentos.tools.{safe_name} import {class_name}\n\n\ndef test_{safe_name}_tool_smoke():\n    t = {class_name}()\n    assert t.name == \"{safe_name}\"\n""",
        ),
    ]

    return {"files": [asdict(f) for f in files]}
