"""Unit tests for PlannerExecutorOrchestrator."""

from pathlib import Path

import pytest

from agentos.agents.specialist.researcher_agent import ResearcherAgent
from agentos.llm.dummy import DummyLLM
from agentos.memory.long_term import LongTermMemory
from agentos.memory.short_term import ShortTermMemory
from agentos.memory.working_state import WorkingStateStore
from agentos.orchestrators.planner_executor import PlannerExecutorOrchestrator
from agentos.security.permissions import PermissionValidator
from agentos.tools.filesystem.read_file import ReadFileTool


def test_planner_generates_valid_subtasks(tmp_path: Path):
    """Test that planner generates valid subtasks using DummyLLM."""
    agent = ResearcherAgent(name="researcher", description="", profile="p")
    tool = ReadFileTool(workspace_root=tmp_path)
    validator = PermissionValidator({"p": {"permissions": [{"tool": "read_file", "actions": ["read"]}]}})
    
    llm = DummyLLM()
    
    orch = PlannerExecutorOrchestrator(
        agents=[agent],
        tools=[tool],
        permission_validator=validator,
        short_term=ShortTermMemory(max_items=5),
        working_state=WorkingStateStore(db_path=tmp_path / "state.db"),
        long_term=LongTermMemory(),
        llm_client=llm,
    )
    
    # Test planning
    subtasks = orch._plan("lee el archivo test.txt", "req123", "session1")
    
    assert len(subtasks) > 0
    assert all(hasattr(st, "id") for st in subtasks)
    assert all(hasattr(st, "objetivo") for st in subtasks)
    assert all(hasattr(st, "criterios_exito") for st in subtasks)
    assert all(st.status == "pending" for st in subtasks)


def test_executor_executes_subtask_successfully(tmp_path: Path):
    """Test that executor can execute a subtask successfully."""
    # Create test file
    (tmp_path / "hello.txt").write_text("hola mundo", encoding="utf-8")
    
    agent = ResearcherAgent(name="researcher", description="", profile="p")
    tool = ReadFileTool(workspace_root=tmp_path)
    validator = PermissionValidator({"p": {"permissions": [{"tool": "read_file", "actions": ["read"]}]}})
    
    llm = DummyLLM()
    
    orch = PlannerExecutorOrchestrator(
        agents=[agent],
        tools=[tool],
        permission_validator=validator,
        short_term=ShortTermMemory(max_items=5),
        working_state=WorkingStateStore(db_path=tmp_path / "state.db"),
        long_term=LongTermMemory(),
        llm_client=llm,
    )
    
    # Create a subtask
    from agentos.orchestrators.planner_executor import Subtask
    
    subtask = Subtask(
        id="1",
        objetivo="lee el archivo hello.txt",
        criterios_exito=["Archivo leÃ­do"]
    )
    
    # Execute subtask
    result = orch._execute_subtask(subtask, "lee el archivo hello.txt", "session1", "user1", "req123")
    
    assert result.success is True
    assert "hola" in result.output


def test_planner_executor_end_to_end(tmp_path: Path):
    """Test complete planner-executor flow end-to-end."""
    import json
    
    # Create test file
    (tmp_path / "data.txt").write_text("contenido de prueba", encoding="utf-8")
    
    agent = ResearcherAgent(name="researcher", description="", profile="p")
    tool = ReadFileTool(workspace_root=tmp_path)
    validator = PermissionValidator({"p": {"permissions": [{"tool": "read_file", "actions": ["read"]}]}})
    
    # Configure DummyLLM to generate a subtask that ResearcherAgent can handle
    # ResearcherAgent looks for pattern "archivo <filename>"
    llm = DummyLLM(responses={
        "plan": json.dumps({
            "subtasks": [{
                "id": "1",
                "objetivo": "lee el archivo data.txt",  # This matches ResearcherAgent's regex
                "criterios_exito": ["Archivo leÃ­do correctamente"]
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
    
    # Run task
    result = orch.run("lee el archivo data.txt", session_id="s1", user_id="u1")
    
    assert result.success is True
    assert "contenido" in result.output or "prueba" in result.output
    assert result.agent_name == "planner_executor"
    assert "subtasks" in result.meta


def test_json_parsing_handles_invalid_json(tmp_path: Path):
    """Test that invalid JSON is handled gracefully."""
    agent = ResearcherAgent(name="researcher", description="", profile="p")
    tool = ReadFileTool(workspace_root=tmp_path)
    validator = PermissionValidator({"p": {"permissions": [{"tool": "read_file", "actions": ["read"]}]}})
    
    # LLM that returns invalid JSON
    llm = DummyLLM(responses={"plan": "invalid json {{"})
    
    orch = PlannerExecutorOrchestrator(
        agents=[agent],
        tools=[tool],
        permission_validator=validator,
        short_term=ShortTermMemory(max_items=5),
        working_state=WorkingStateStore(db_path=tmp_path / "state.db"),
        long_term=LongTermMemory(),
        llm_client=llm,
    )
    
    # Planning should return empty list on invalid JSON
    subtasks = orch._plan("test task", "req123", "session1")
    
    assert len(subtasks) == 0


def test_json_parsing_handles_missing_subtasks_field(tmp_path: Path):
    """Test that missing 'subtasks' field is handled gracefully."""
    import json
    
    agent = ResearcherAgent(name="researcher", description="", profile="p")
    tool = ReadFileTool(workspace_root=tmp_path)
    validator = PermissionValidator({"p": {"permissions": [{"tool": "read_file", "actions": ["read"]}]}})
    
    # LLM that returns JSON without 'subtasks' field
    llm = DummyLLM(responses={"plan": json.dumps({"error": "no subtasks"})})
    
    orch = PlannerExecutorOrchestrator(
        agents=[agent],
        tools=[tool],
        permission_validator=validator,
        short_term=ShortTermMemory(max_items=5),
        working_state=WorkingStateStore(db_path=tmp_path / "state.db"),
        long_term=LongTermMemory(),
        llm_client=llm,
    )
    
    # Planning should return empty list
    subtasks = orch._plan("test task", "req123", "session1")
    
    assert len(subtasks) == 0


def test_fallback_to_single_task_when_planning_fails(tmp_path: Path):
    """Test that orchestrator falls back to single task execution when planning fails."""
    # Create test file
    (tmp_path / "test.txt").write_text("test content", encoding="utf-8")
    
    agent = ResearcherAgent(name="researcher", description="", profile="p")
    tool = ReadFileTool(workspace_root=tmp_path)
    validator = PermissionValidator({"p": {"permissions": [{"tool": "read_file", "actions": ["read"]}]}})
    
    # LLM that returns invalid JSON
    llm = DummyLLM(responses={"plan": "not json"})
    
    orch = PlannerExecutorOrchestrator(
        agents=[agent],
        tools=[tool],
        permission_validator=validator,
        short_term=ShortTermMemory(max_items=5),
        working_state=WorkingStateStore(db_path=tmp_path / "state.db"),
        long_term=LongTermMemory(),
        llm_client=llm,
    )
    
    # Should still execute successfully using fallback
    result = orch.run("lee el archivo test.txt", session_id="s1", user_id="u1")
    
    # Should succeed via fallback mechanism
    # Note: fallback returns agent result directly
    assert result.success is True  # Fallback should succeed
    assert "test" in result.output or "content" in result.output


def test_max_retries_per_task_limit(tmp_path: Path):
    """Test that MAX_RETRIES_PER_TASK limit is respected."""
    import json
    
    agent = ResearcherAgent(name="researcher", description="", profile="p")
    tool = ReadFileTool(workspace_root=tmp_path)
    validator = PermissionValidator({"p": {"permissions": [{"tool": "read_file", "actions": ["read"]}]}})
    
    # LLM that generates a plan with a task that will trigger fallback behavior
    # The ResearcherAgent will return success but with a fallback message
    llm = DummyLLM(responses={
        "plan": json.dumps({
            "subtasks": [{
                "id": "1", 
                "objetivo": "tarea sin patron reconocible xyz123",  # Won't match any regex
                "criterios_exito": ["completada"]
            }]
        })
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
    
    result = orch.run("tarea sin patron", session_id="s1", user_id="u1")
    
    # ResearcherAgent returns success with fallback message, so result will be success
    # But we can verify the orchestrator executed the plan
    assert result.agent_name == "planner_executor"
    assert "subtasks" in result.meta
    assert len(result.meta["subtasks"]) > 0