from __future__ import annotations

import re
from typing import Dict, List

from agentos.agents.base.agent_base import AgentContext, BaseAgent, ExecutionResult
from agentos.tools.base import ToolInput, ToolOutput


class ResearcherAgent(BaseAgent):
    def can_handle(self, task: str) -> bool:
        keywords = ["buscar", "investiga", "http", "url", "lee"]
        t = task.lower()
        return any(k in t for k in keywords)

    def execute(self, task: str, ctx: AgentContext) -> ExecutionResult:
        ctx.logger.info(
            "ResearcherAgent executing",
            extra={"request_id": ctx.request_id, "session_id": ctx.session_id, "user_id": ctx.user_id, "agent": self.name},
        )

        tool_calls: List[Dict[str, str]] = []

        # Heurística: si parece un archivo, leerlo
        m = re.search(r"archivo\s+([^\s]+)", task, re.IGNORECASE)
        if m and "read_file" in ctx.tools:
            path = m.group(1).strip()
            out = ctx.tools["read_file"].execute(ToolInput(request_id=ctx.request_id, payload={"path": path}))
            tool_calls.append({"tool": "read_file", "ok": str(out.success)})
            if out.success and out.data:
                content = out.data.get("content", "")
                snippet = "\n".join(content.splitlines()[:20])
                return ExecutionResult(agent_name=self.name, success=True, output=f"Contenido (snippet):\n{snippet}", meta={"tool_calls": tool_calls})
            return ExecutionResult(agent_name=self.name, success=False, output="", error=out.error, meta={"tool_calls": tool_calls})

        # Heurística: si hay URL, fetchear
        m2 = re.search(r"(https?://\S+)", task)
        if m2 and "http_fetch" in ctx.tools:
            url = m2.group(1)
            out = ctx.tools["http_fetch"].execute(ToolInput(request_id=ctx.request_id, payload={"url": url}))
            tool_calls.append({"tool": "http_fetch", "ok": str(out.success)})
            if out.success and out.data:
                text = out.data.get("text", "")
                snippet = "\n".join(text.splitlines()[:30])
                return ExecutionResult(agent_name=self.name, success=True, output=f"Respuesta HTTP (snippet):\n{snippet}", meta={"tool_calls": tool_calls})
            return ExecutionResult(agent_name=self.name, success=False, output="", error=out.error, meta={"tool_calls": tool_calls})

        # Fallback: no tools
        # Fallback: usar LLM si está disponible
        llm_client = ctx.memory.get("llm_client") if ctx.memory else None
        
        if llm_client:
            try:
                # Construir prompt con contexto de memoria a corto plazo
                short_term = ctx.memory.get("short_term", []) if ctx.memory else []
                context_str = "\n".join([f"- {msg}" for msg in short_term[-5:]]) if short_term else "Ninguno"
                
                prompt = (
                    f"Eres un investigador experto. Tarea: {task}\n\n"
                    f"Contexto previo:\n{context_str}\n\n"
                    "Responde detalladamente a la tarea basándote en tu conocimiento:"
                )
                
                response = llm_client.generate(prompt)
                return ExecutionResult(agent_name=self.name, success=True, output=response, meta={"tool_calls": tool_calls})
                
            except Exception as e:
                ctx.logger.error(f"ResearcherAgent LLM fallback failed: {e}")
                return ExecutionResult(agent_name=self.name, success=False, output="", error=f"Error generando respuesta: {e}", meta={"tool_calls": tool_calls})

        # Fallback original si no hay LLM
        return ExecutionResult(
            agent_name=self.name,
            success=True,
            output=(
                "No encontré una acción determinista y no hay LLM conectado.\n"
                "En un sistema real, aquí se usaría un LLM + tool router para planificar y ejecutar."
            ),
            meta={"tool_calls": tool_calls},
        )
