"""Research Package Pipeline — modified by the AutoResearch loop between experiments.

This is the "train.py" equivalent. The loop agent may modify RESEARCH_CONFIG
and RESEARCH_SYSTEM_PROMPT to improve judge scores. The run_research() function
signature must remain stable.
"""

from __future__ import annotations

import json
import os
import re

# ---------------------------------------------------------------------------
# RESEARCH_CONFIG — the loop agent may tune these values
# ---------------------------------------------------------------------------
RESEARCH_CONFIG = {
    "query_expansion": {
        "enabled": True,
        "max_sub_queries": 3,
        "strategy": "decompose",
    },
    "source_depth": {
        "web_search_rounds": 2,
        "cross_reference": True,
    },
    "verification": {
        "require_source_for_claims": True,
        "uncertainty_markers": [
            "[INCIERTO]",
            "[SIN VERIFICAR]",
            "[POSIBLEMENTE DESACTUALIZADO]",
        ],
        "flag_unverified": True,
    },
    "output_structure": {
        "sections": [
            "resumen_ejecutivo",
            "hallazgos_verificados",
            "hallazgos_descartados",
            "stack_tecnico_relevante",
            "gaps_conocidos",
            "proximos_pasos",
        ],
        "include_bitacora": True,
        "notion_ready": True,
    },
}

# ---------------------------------------------------------------------------
# RESEARCH_SYSTEM_PROMPT — the loop agent may tune this string
# ---------------------------------------------------------------------------
RESEARCH_SYSTEM_PROMPT = """Eres un agente de investigación técnica experto. Tu tarea es producir un Research Package (RP) en formato JSON estructurado.

## REGLAS ESTRICTAS DE VERIFICACIÓN
1. Marca toda afirmación incierta o sin fuente con [INCIERTO].
2. Coloca información contradicha o refutada en `hallazgos_descartados`, explicando por qué fue descartada.
3. Para `stack_tecnico_relevante`, incluye versiones específicas cuando estén disponibles.
4. `proximos_pasos` debe tener al menos 3 acciones concretas y ejecutables.
5. Incluye al menos 1 entrada en `hallazgos_descartados` (opciones consideradas y rechazadas).
6. En `hallazgos_verificados`, cada hallazgo debe indicar su fuente o base de conocimiento.

## FORMATO DE OUTPUT
Devuelve ÚNICAMENTE un JSON válido con esta estructura exacta:

{
  "resumen_ejecutivo": "string — síntesis de 2-4 oraciones con el hallazgo principal",
  "hallazgos_verificados": [
    {
      "hallazgo": "descripción del hallazgo",
      "fuente": "URL, nombre de docs oficiales, o 'conocimiento del modelo (verificar)'",
      "confianza": "alta | media | baja"
    }
  ],
  "hallazgos_descartados": [
    {
      "opcion": "nombre de la opción descartada",
      "razon_descarte": "por qué no aplica o fue refutada"
    }
  ],
  "stack_tecnico_relevante": [
    {
      "nombre": "nombre del tool/lib/API",
      "version": "versión específica o 'verificar última'",
      "rol": "qué hace en el stack",
      "url_docs": "URL de documentación oficial"
    }
  ],
  "gaps_conocidos": [
    "descripción de brecha de conocimiento o información no disponible"
  ],
  "proximos_pasos": [
    {
      "accion": "acción concreta y ejecutable",
      "prioridad": "alta | media | baja",
      "herramienta": "tool o recurso necesario"
    }
  ],
  "bitacora": {
    "sub_queries_generadas": ["lista de sub-queries si se expandió la consulta"],
    "estrategia_usada": "descripción de la estrategia de investigación",
    "rondas_busqueda": 2
  }
}

No incluyas texto fuera del JSON. No uses markdown. Solo el JSON puro."""


def _build_research_prompt(query: str, config: dict, system_prompt: str) -> str:
    """Construye el prompt completo para la investigación."""
    cfg = config or RESEARCH_CONFIG

    expansion_cfg = cfg.get("query_expansion", {})
    verification_cfg = cfg.get("verification", {})

    parts = [system_prompt or RESEARCH_SYSTEM_PROMPT, "\n\n---\n\n"]

    # Instrucciones de expansión de query
    if expansion_cfg.get("enabled"):
        max_sub = expansion_cfg.get("max_sub_queries", 3)
        strategy = expansion_cfg.get("strategy", "decompose")
        parts.append(
            f"## INSTRUCCIÓN DE EXPANSIÓN\n"
            f"Antes de responder, descompone la consulta en hasta {max_sub} sub-preguntas "
            f"usando la estrategia '{strategy}'. Registra las sub-queries en `bitacora.sub_queries_generadas`.\n\n"
        )

    # Instrucciones de verificación
    if verification_cfg.get("require_source_for_claims"):
        markers = verification_cfg.get("uncertainty_markers", ["[INCIERTO]"])
        parts.append(
            f"## INSTRUCCIÓN DE VERIFICACIÓN\n"
            f"Cada afirmación sin fuente verificable debe marcarse con uno de: "
            f"{', '.join(markers)}.\n\n"
        )

    parts.append(f"## CONSULTA DE INVESTIGACIÓN\n{query}\n")

    return "".join(parts)


def run_research(
    query: str,
    config: dict = None,
    system_prompt: str = None,
) -> dict:
    """Ejecuta una investigación para la query dada y retorna un Research Package.

    Args:
        query: La pregunta de investigación
        config: Overrides para RESEARCH_CONFIG (None = usar global)
        system_prompt: Override para RESEARCH_SYSTEM_PROMPT (None = usar global)

    Returns:
        dict con la estructura del Research Package
    """
    from agentos.llm.anthropic_client import AnthropicClient

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    client = AnthropicClient(
        api_key=api_key,
        model="claude-sonnet-4-6",
        max_tokens=4096,
        timeout=120,
    )

    effective_config = config or RESEARCH_CONFIG
    effective_prompt = system_prompt or RESEARCH_SYSTEM_PROMPT

    full_prompt = _build_research_prompt(query, effective_config, effective_prompt)

    raw_response = client.generate(full_prompt)

    # Intentar parsear JSON directamente
    try:
        return json.loads(raw_response.strip())
    except json.JSONDecodeError:
        pass

    # Fallback: extraer bloque JSON si hay texto extra
    match = re.search(r"\{.*\}", raw_response, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Si no se puede parsear, retornar estructura de error
    return {
        "resumen_ejecutivo": "[ERROR] No se pudo parsear la respuesta como JSON.",
        "hallazgos_verificados": [],
        "hallazgos_descartados": [],
        "stack_tecnico_relevante": [],
        "gaps_conocidos": [f"Error de parsing: {raw_response[:500]}"],
        "proximos_pasos": [],
        "bitacora": {
            "sub_queries_generadas": [],
            "estrategia_usada": "error",
            "rondas_busqueda": 0,
        },
    }


if __name__ == "__main__":
    import sys

    test_query = (
        "¿Cuál es el stack mínimo para un agente FastAPI con memoria persistente en 2026?"
    )
    print(f"Probando rp_pipeline con query: {test_query[:60]}...")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY no configurada.")
        sys.exit(1)

    result = run_research(test_query)
    print(json.dumps(result, ensure_ascii=False, indent=2))
