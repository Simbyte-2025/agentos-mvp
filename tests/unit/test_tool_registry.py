from agentos.tools.registry import ToolRegistry
from agentos.tools.base import BaseTool, ToolInput, ToolOutput


class DummyTool(BaseTool):
    def __init__(self):
        super().__init__(name="dummy", description="dummy", risk="read")

    def execute(self, tool_input: ToolInput) -> ToolOutput:
        return ToolOutput(success=True, data={"ok": True})


def test_tool_registry_register_and_get():
    r = ToolRegistry()
    t = DummyTool()
    r.register(t)
    assert r.get("dummy") is t
