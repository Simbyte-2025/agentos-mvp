from __future__ import annotations

from pathlib import Path
from .schemas import BuilderPlan, FileChange
from agentos.security.path_policy import PathPolicy

class ScaffoldManager:
    def __init__(self, root_dir: str | Path):
        self.root_dir = Path(root_dir).resolve()
        self.policy = PathPolicy(self.root_dir)

    def create_agent_scaffold(self, name: str, description: str) -> BuilderPlan:
        safe_name = name.strip().lower().replace(" ", "_")
        class_name = "".join([p.capitalize() for p in safe_name.split("_")]) + "Agent"
        agent_path = f"agentos/agents/specialist/{safe_name}_agent.py"
        
        self.policy.validate_path(agent_path)
        
        content = f"""from __future__ import annotations

from agentos.agents.base.agent_base import AgentContext, BaseAgent, ExecutionResult


class {class_name}(BaseAgent):
    \"\"\"{description}\"\"\"

    def can_handle(self, task: str) -> bool:
        # TODO: definir keywords o un clasificador
        return False

    def execute(self, task: str, ctx: AgentContext) -> ExecutionResult:
        # TODO: implementar lógica real
        return ExecutionResult(agent_name=self.name, success=True, output=\"TODO\")
"""
        test_path = f"tests/unit/test_{safe_name}_agent.py"
        test_content = f"""from agentos.agents.specialist.{safe_name}_agent import {class_name}


def test_{safe_name}_agent_smoke():
    a = {class_name}(name=\"{safe_name}_agent\", description=\"{description}\", profile=\"{safe_name}_agent\")
    assert a.name
"""
        return BuilderPlan(
            name=f"Scaffold Agent: {name}",
            description=description,
            changes=[
                FileChange(path=agent_path, content=content),
                FileChange(path=test_path, content=test_content)
            ],
            metadata={"kind": "agent", "target_name": name}
        )

    def create_tool_scaffold(self, name: str, description: str, risk: str = "read") -> BuilderPlan:
        safe_name = name.strip().lower().replace(" ", "_")
        class_name = "".join([p.capitalize() for p in safe_name.split("_")]) + "Tool"
        tool_path = f"agentos/tools/{safe_name}.py"
        
        self.policy.validate_path(tool_path)
        
        content = f"""from __future__ import annotations

from agentos.tools.base import BaseTool, ToolInput, ToolOutput


class {class_name}(BaseTool):
    \"\"\"{description}\"\"\"

    def __init__(self):
        super().__init__(name=\"{safe_name}\", description=\"{description}\", risk=\"{risk}\")

    def execute(self, tool_input: ToolInput) -> ToolOutput:
        # TODO: implementar
        return ToolOutput(success=True, data={{}})
"""
        test_path = f"tests/unit/test_{safe_name}_tool.py"
        test_content = f"""from agentos.tools.{safe_name} import {class_name}


def test_{safe_name}_tool_smoke():
    t = {class_name}()
    assert t.name == \"{safe_name}\"
"""
        return BuilderPlan(
            name=f"Scaffold Tool: {name}",
            description=description,
            changes=[
                FileChange(path=tool_path, content=content),
                FileChange(path=test_path, content=test_content)
            ],
            metadata={"kind": "tool", "target_name": name, "risk": risk}
        )
