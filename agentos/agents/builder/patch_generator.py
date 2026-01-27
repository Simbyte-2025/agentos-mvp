from __future__ import annotations

import difflib
from pathlib import Path
from .schemas import BuilderPlan

class PatchGenerator:
    def __init__(self, root_dir: str | Path):
        self.root_dir = Path(root_dir).resolve()

    def generate_unified_diff(self, plan: BuilderPlan) -> str:
        """
        Genera un unified diff compatible con git apply a partir de un BuilderPlan.
        El orden de los archivos es determinista (alfabético).
        """
        diff_parts = []
        
        # Ordenar cambios por path para determinismo
        sorted_changes = sorted(plan.changes, key=lambda x: x.path)
        
        for change in sorted_changes:
            path = change.path
            content = change.content
            
            # Formato Git Unified Diff
            # En el MVP, asumimos que la mayoría son archivos nuevos (scaffold)
            current_content = ""
            
            diff = difflib.unified_diff(
                current_content.splitlines(keepends=True),
                content.splitlines(keepends=True),
                fromfile="/dev/null",
                tofile=f"b/{path}",
                n=3
            )
            
            # Construir el header estilo git
            header = [
                f"diff --git a/{path} b/{path}\n",
                "new file mode 100644\n",
                "--- /dev/null\n",
                f"+++ b/{path}\n"
            ]
            
            diff_list = list(diff)
            if len(diff_list) > 2:
                diff_parts.extend(header)
                diff_parts.extend(diff_list[2:])
        
        return "".join(diff_parts)
