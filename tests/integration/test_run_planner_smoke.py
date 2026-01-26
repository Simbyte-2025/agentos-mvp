"""Integration test for PlannerExecutorOrchestrator."""

from pathlib import Path

from agentos.agents.specialist.researcher_agent import ResearcherAgent
from agentos.llm.dummy import DummyLLM
from agentos.memory.long_term import LongTermMemory
from agentos.memory.short_term import ShortTermMemory
from agentos.memory.working_state import WorkingStateStore
from agentos.orchestrators.planner_executor import PlannerExecutorOrchestrator
from agentos.security.permissions import PermissionValidator
from agentos.tools.filesystem.read_file import ReadFileTool


def test_planner_orchestrator_reads_file(tmp_path: Path):
    """Integration test: planner orchestrator completes a file reading task."""
    import json
    
    # Create test file
    (tmp_path / "hello.txt").write_text("hola desde planner\nlinea2\n", encoding="utf-8")

    agent = ResearcherAgent(name="researcher_agent", description="", profile="p")
    tool = ReadFileTool(workspace_root=tmp_path)

    validator = PermissionValidator({"p": {"permissions": [{"tool": "read_file", "actions": ["read"]}]}})

    # Configure DummyLLM to generate a subtask that ResearcherAgent can handle
    llm = DummyLLM(responses={
        "plan": json.dumps({
            "subtasks": [{
                "id": "1",
                "objetivo": "lee el archivo hello.txt",  # Matches ResearcherAgent's regex
                "criterios_exito": ["Archivo leído correctamente"]
            }]
        }, ensure_ascii=False)
    })

    orch = PlannerExecutorOrchestrator(
        agents=[agent],
        tools=[tool],
        permission_validator=validator,
        short_term=ShortTermMemory(max_items=5),
        working_state=WorkingStateStore(db_path=tmp_path / "state.db"),
        long_term=LongTermMemory(),
        llm_client=llm,
    )

    # Execute task
    res = orch.run(task="lee el archivo hello.txt", session_id="s", user_id="u")
    
    # Verify success
    assert res.success is True
    assert "hola" in res.output
    assert res.agent_name == "planner_executor"
    
    # Verify metadata
    assert "subtasks" in res.meta
    assert isinstance(res.meta["subtasks"], list)
    assert len(res.meta["subtasks"]) > 0
    
    # Verify at least one subtask succeeded
    assert any(st["status"] == "success" for st in res.meta["subtasks"])
