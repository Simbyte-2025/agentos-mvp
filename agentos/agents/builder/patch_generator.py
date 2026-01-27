from __future__ import annotations

import difflib
from typing import List

from agentos.agents.builder.schemas import PlanSummary


class PatchGenerator:
    """Generador de diffs unificados git-compatible y deterministas."""

    @staticmethod
    def generate(plan: PlanSummary) -> str:
        """Genera un unified diff string a partir del plan.
        
        Reglas:
        - Orden alfabético por path
        - Formato git: diff --git a/... b/...
        - New files: --- /dev/null, +++ b/path
        """
        # Ordenar cambios por path para determinismo
        changes = sorted(plan.changes, key=lambda c: c.path)
        
        diff_lines = []
        
        for change in changes:
            if change.operation == "create":
                # Header git-style
                diff_lines.append(f"diff --git a/{change.path} b/{change.path}")
                diff_lines.append(f"new file mode 100644")
                diff_lines.append(f"--- /dev/null")
                diff_lines.append(f"+++ b/{change.path}")
                
                # Content diff
                # Para archivo nuevo, todo es adicion
                lines = change.content.splitlines(keepends=True)
                if not lines:
                    continue
                    
                # Hunk header
                diff_lines.append(f"@@ -0,0 +1,{len(lines)} @@")
                for line in lines:
                    # Asegurar salto de línea al final si no tiene
                    if not line.endswith("\n"):
                        line += "\n"  # Git espera newline al final
                        # Nota: en realidad git muestra 'No newline at end of file'
                        # pero para simplicidad del patch generator, asumimos contenido normalizado
                    diff_lines.append(f"+{line.rstrip()}") # rstrip para evitar doble newline en print, pero diff necesita cuidado
                
        # TODO: Mejorar manejo de newlines exactos para compatibilidad total binaria
        # Por ahora v1.1 simple string append
        
        return "\n".join(diff_lines)

    @staticmethod
    def _create_hunk(content: str) -> List[str]:
        # Helper interno si hiciera falta lógica compleja de hunks
        pass
