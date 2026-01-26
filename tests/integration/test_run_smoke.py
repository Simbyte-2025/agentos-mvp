from pathlib import Path

from agentos.agents.specialist.researcher_agent import ResearcherAgent
from agentos.memory.long_term import LongTermMemory
from agentos.memory.short_term import ShortTermMemory
from agentos.memory.working_state import WorkingStateStore
from agentos.orchestrators.sequential import SequentialOrchestrator
from agentos.security.permissions import PermissionValidator
from agentos.tools.filesystem.read_file import ReadFileTool


def test_orchestrator_reads_file(tmp_path: Path):
    (tmp_path / "hello.txt").write_text("hola\nlinea2\n", encoding="utf-8")

    agent = ResearcherAgent(name="researcher_agent", description="", profile="p")
    tool = ReadFileTool(workspace_root=tmp_path)

    v = PermissionValidator({"p": {"permissions": [{"tool": "read_file", "actions": ["read"]}]}})

    orch = SequentialOrchestrator(
        agents=[agent],
        tools=[tool],
        permission_validator=v,
        short_term=ShortTermMemory(max_items=5),
        working_state=WorkingStateStore(db_path=tmp_path / "state.db"),
        long_term=LongTermMemory(),
    )

    res = orch.run(task="lee el archivo hello.txt", session_id="s", user_id="u")
    assert res.success is True
    assert "hola" in res.output
