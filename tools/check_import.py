"""Script to verify imports work correctly."""
from agentos.security.run_command_allowlist import CommandAllowlist
from agentos.tools.exec.run_command import RunCommandTool

print("✓ CommandAllowlist imported successfully")
print("✓ RunCommandTool imported successfully")

# Quick validation
allowlist = CommandAllowlist(allowed_commands=["python"])
decision = allowlist.validate("python", ["--version"])
print(f"✓ Allowlist validation works: {decision.allowed}")

print("\nAll imports successful!")
