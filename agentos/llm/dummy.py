"""Dummy LLM client for testing."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from agentos.llm.base import LLMClient


class DummyLLM(LLMClient):
    """Dummy LLM implementation for testing.
    
    Returns deterministic responses based on keywords in the prompt.
    This should ONLY be used in tests or when explicitly configured
    via AGENTOS_LLM=dummy environment variable.
    """

    def __init__(self, responses: Optional[Dict[str, str]] = None):
        """Initialize DummyLLM.
        
        Args:
            responses: Optional custom responses dict. Keys are keywords to match
                      in prompts, values are the responses to return.
        """
        self.responses = responses or {}

    def generate(self, prompt: str) -> str:
        """Generate deterministic response based on prompt keywords.
        
        Args:
            prompt: Input prompt
            
        Returns:
            JSON string with subtasks or custom response
        """
        prompt_lower = prompt.lower()
        
        # Check for custom responses first
        for keyword, response in self.responses.items():
            if keyword.lower() in prompt_lower:
                return response
        
        # Default behavior: generate plan with subtasks
        if "plan" in prompt_lower or "subtask" in prompt_lower:
            # Check for file reading task
            if "archivo" in prompt_lower or "file" in prompt_lower or "lee" in prompt_lower or "read" in prompt_lower:
                return json.dumps({
                    "subtasks": [
                        {
                            "id": "1",
                            "objetivo": "Leer el archivo solicitado",
                            "criterios_exito": ["Archivo leído correctamente", "Contenido disponible"]
                        }
                    ]
                }, ensure_ascii=False)
            
            # Generic plan
            return json.dumps({
                "subtasks": [
                    {
                        "id": "1",
                        "objetivo": "Analizar la tarea",
                        "criterios_exito": ["Tarea analizada"]
                    },
                    {
                        "id": "2",
                        "objetivo": "Ejecutar la acción principal",
                        "criterios_exito": ["Acción completada"]
                    }
                ]
            }, ensure_ascii=False)
        
        # Replan scenario
        if "replan" in prompt_lower or "replantear" in prompt_lower:
            return json.dumps({
                "subtasks": [
                    {
                        "id": "1",
                        "objetivo": "Intentar enfoque alternativo",
                        "criterios_exito": ["Enfoque alternativo ejecutado"]
                    }
                ]
            }, ensure_ascii=False)
        
        # Fallback: empty plan
        return json.dumps({"subtasks": []}, ensure_ascii=False)
