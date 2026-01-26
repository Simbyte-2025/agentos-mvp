from __future__ import annotations

from agentos.agents.base.agent_base import AgentContext, BaseAgent, ExecutionResult


class ReviewerAgent(BaseAgent):
    def can_handle(self, task: str) -> bool:
        keywords = ["revisa", "evalua", "riesgo", "seguridad"]
        t = task.lower()
        return any(k in t for k in keywords)

    def execute(self, task: str, ctx: AgentContext) -> ExecutionResult:
        ctx.logger.info(
            "ReviewerAgent executing",
            extra={"request_id": ctx.request_id, "session_id": ctx.session_id, "user_id": ctx.user_id, "agent": self.name},
        )

        # MVP: checklist simple
        checklist = [
            "¿Hay logs estructurados con request_id?",
            "¿Se valida acceso a tools por perfil?",
            "¿Hay prevención de path traversal en filesystem?",
            "¿Se evita exponer secretos?",
        ]
        out = "Checklist de revisión (MVP):\n- " + "\n- ".join(checklist)
        return ExecutionResult(agent_name=self.name, success=True, output=out)
