from __future__ import annotations

import re

from agentos.agents.base.agent_base import AgentContext, BaseAgent, ExecutionResult
from agentos.tools.base import ToolInput


class WriterAgent(BaseAgent):
    def can_handle(self, task: str) -> bool:
        keywords = ["redacta", "escribe", "resume", "sintetiza"]
        t = task.lower()
        return any(k in t for k in keywords)

    def execute(self, task: str, ctx: AgentContext) -> ExecutionResult:
        ctx.logger.info(
            "WriterAgent executing",
            extra={"request_id": ctx.request_id, "session_id": ctx.session_id, "user_id": ctx.user_id, "agent": self.name},
        )

        # Si pide resumen de un archivo, leerlo y resumir (muy simple)
        m = re.search(r"archivo\s+([^\s]+)", task, re.IGNORECASE)
        if m and "read_file" in ctx.tools:
            path = m.group(1).strip()
            out = ctx.tools["read_file"].execute(ToolInput(request_id=ctx.request_id, payload={"path": path}))
            if out.success and out.data:
                content = out.data.get("content", "")
                lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
                summary = "\n".join(lines[:12])
                return ExecutionResult(agent_name=self.name, success=True, output=f"Resumen (heurístico):\n{summary}", meta={"source": path})
            return ExecutionResult(agent_name=self.name, success=False, output="", error=out.error)

        # Usar LLM si está disponible
        llm_client = ctx.memory.get("llm_client") if ctx.memory else None
        
        if llm_client:
            try:
                # Recuperar contexto para redacción
                short_term = ctx.memory.get("short_term", []) if ctx.memory else []
                context_str = "\n".join([f"- {msg}" for msg in short_term[-5:]]) if short_term else "Ninguno"
                
                prompt = (
                    f"Eres un redactor experto. Tarea: {task}\n\n"
                    f"Contexto previo:\n{context_str}\n\n"
                    "Escribe el contenido solicitado:"
                )
                
                response = llm_client.generate(prompt)
                return ExecutionResult(agent_name=self.name, success=True, output=response)
                
            except Exception as e:
                ctx.logger.error(f"WriterAgent LLM generation failed: {e}")
                return ExecutionResult(agent_name=self.name, success=False, output="", error=f"Error generando texto: {e}")

        return ExecutionResult(
            agent_name=self.name,
            success=True,
            output="WriterAgent MVP: sin LLM no puedo redactar en serio. Conecta un LLM para generación real.",
        )
