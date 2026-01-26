"""Quick test script to debug the issue."""
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from agentos.agents.specialist.researcher_agent import ResearcherAgent
from agentos.llm.dummy import DummyLLM
from agentos.memory.long_term import LongTermMemory
from agentos.memory.short_term import ShortTermMemory
from agentos.memory.working_state import WorkingStateStore
from agentos.orchestrators.planner_executor import PlannerExecutorOrchestrator
from agentos.security.permissions import PermissionValidator
from agentos.tools.filesystem.read_file import ReadFileTool

# Create temp directory
tmp_path = Path("C:/Users/nicol/AppData/Local/Temp/test_debug")
tmp_path.mkdir(exist_ok=True)

# Create test file
(tmp_path / "data.txt").write_text("contenido de prueba", encoding="utf-8")

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
print("=== Testing Planning ===")
subtasks = orch._plan("lee el archivo data.txt", "req123", "session1")
print(f"Generated {len(subtasks)} subtasks:")
for st in subtasks:
    print(f"  - ID: {st.id}, Objetivo: {st.objetivo}")

# Run full task
print("\n=== Running Full Task ===")
result = orch.run("lee el archivo data.txt", session_id="s1", user_id="u1")

print(f"\nSuccess: {result.success}")
print(f"Output: {result.output[:200] if result.output else 'None'}")
print(f"Error: {result.error}")
print(f"Meta: {result.meta}")
