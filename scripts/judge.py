"""Judge — IMMUTABLE evaluator. Never modified by the loop.

Evaluates Research Packages on 4 dimensions using Claude with temperature=0.
Returns a structured JSON with scores, weighted total, and observations.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import anthropic

# ---------------------------------------------------------------------------
# Evaluation dimensions and weights — DO NOT MODIFY
# ---------------------------------------------------------------------------
DIMENSIONS = {
    "completitud_estructural": {
        "weight": 0.35,
        "description": (
            "Todas las secciones requeridas están presentes y tienen contenido sustancial: "
            "resumen_ejecutivo, hallazgos_verificados (≥3), hallazgos_descartados (≥1), "
            "stack_tecnico_relevante (≥2), gaps_conocidos (≥1), proximos_pasos (≥3), bitacora."
        ),
    },
    "verificabilidad": {
        "weight": 0.30,
        "description": (
            "Las afirmaciones inciertas están marcadas con [INCIERTO] u otros marcadores. "
            "hallazgos_verificados incluye fuentes. "
            "hallazgos_descartados explica razones de descarte. "
            "No hay afirmaciones absolutas sin respaldo."
        ),
    },
    "accionabilidad_fase5": {
        "weight": 0.25,
        "description": (
            "proximos_pasos son concretos y ejecutables (no vagos). "
            "stack_tecnico_relevante incluye versiones específicas. "
            "Las preguntas críticas de Fase 5 están respondidas directa o indirectamente. "
            "Un desarrollador puede actuar inmediatamente con la información provista."
        ),
    },
    "trazabilidad": {
        "weight": 0.10,
        "description": (
            "bitacora registra sub_queries_generadas y estrategia_usada. "
            "Es posible reproducir o auditar el proceso de investigación. "
            "stack_tecnico_relevante tiene url_docs cuando aplica."
        ),
    },
}

JUDGE_SYSTEM_PROMPT = """Eres un evaluador experto de Research Packages técnicos. Tu tarea es puntuar un Research Package (RP) en 4 dimensiones.

Para cada dimensión, asigna un score de 0.0 a 1.0:
- 0.0: Completamente ausente o inútil
- 0.25: Muy deficiente, mínimo esfuerzo
- 0.50: Parcial, cumple algunos requisitos
- 0.75: Bueno, cumple la mayoría de requisitos con deficiencias menores
- 1.0: Excelente, cumple todos los requisitos

Devuelve ÚNICAMENTE un JSON válido con esta estructura exacta:
{
  "scores": {
    "completitud_estructural": <float 0.0-1.0>,
    "verificabilidad": <float 0.0-1.0>,
    "accionabilidad_fase5": <float 0.0-1.0>,
    "trazabilidad": <float 0.0-1.0>
  },
  "observations": [
    "observación concreta sobre el RP (máximo 6 observaciones, mezcla positivas y negativas)"
  ]
}

No incluyas texto fuera del JSON."""


def evaluate(
    research_package: dict[str, Any],
    query: str,
    fase5_critical_questions: list[str] | None = None,
) -> dict[str, Any]:
    """Evalúa un Research Package y retorna scores ponderados.

    Args:
        research_package: El RP generado por rp_pipeline.run_research()
        query: La query original de investigación
        fase5_critical_questions: Preguntas críticas para accionabilidad_fase5

    Returns:
        dict con:
            - scores: dict con score por dimensión (0.0-1.0)
            - total: float, score ponderado total (0.0-1.0)
            - observations: list[str]
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY no configurada. Necesaria para el judge."
        )

    client = anthropic.Anthropic(api_key=api_key)

    # Construir prompt de evaluación
    cq_section = ""
    if fase5_critical_questions:
        cq_section = (
            "\n## PREGUNTAS CRÍTICAS DE FASE 5 (evalúa si el RP las responde)\n"
            + "\n".join(f"- {q}" for q in fase5_critical_questions)
            + "\n"
        )

    dimensions_desc = "\n".join(
        f"### {name} (peso {info['weight']})\n{info['description']}"
        for name, info in DIMENSIONS.items()
    )

    eval_prompt = f"""{JUDGE_SYSTEM_PROMPT}

## DIMENSIONES A EVALUAR
{dimensions_desc}

## QUERY ORIGINAL
{query}
{cq_section}
## RESEARCH PACKAGE A EVALUAR
{json.dumps(research_package, ensure_ascii=False, indent=2)}

Evalúa el Research Package anterior según las 4 dimensiones descritas."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        temperature=0,
        messages=[{"role": "user", "content": eval_prompt}],
    )

    raw = message.content[0].text.strip()

    # Parsear respuesta JSON
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        import re
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            result = json.loads(match.group(0))
        else:
            raise RuntimeError(f"Judge no pudo parsear respuesta: {raw[:300]}")

    scores = result.get("scores", {})
    observations = result.get("observations", [])

    # Calcular total ponderado
    total = sum(
        scores.get(dim, 0.0) * info["weight"]
        for dim, info in DIMENSIONS.items()
    )

    return {
        "scores": scores,
        "total": round(total, 4),
        "observations": observations,
    }


if __name__ == "__main__":
    """Smoke test: evalúa un RP sintético mínimo."""
    print("=== Judge smoke test ===")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("SKIP: ANTHROPIC_API_KEY no configurada.")
        sys.exit(0)

    # RP sintético mínimo para smoke test
    sample_rp = {
        "resumen_ejecutivo": "FastAPI con SQLite es el stack más simple para un solo developer en 2026.",
        "hallazgos_verificados": [
            {
                "hallazgo": "FastAPI 0.111+ soporta async nativo con SQLAlchemy 2.0",
                "fuente": "https://fastapi.tiangolo.com/",
                "confianza": "alta",
            },
            {
                "hallazgo": "SQLite es suficiente hasta ~100k requests/día para un solo developer",
                "fuente": "SQLite documentation",
                "confianza": "media",
            },
            {
                "hallazgo": "python-jose es la librería auth más usada con FastAPI [INCIERTO]",
                "fuente": "[SIN VERIFICAR]",
                "confianza": "baja",
            },
        ],
        "hallazgos_descartados": [
            {
                "opcion": "Django",
                "razon_descarte": "Overhead excesivo para un solo developer, curva de aprendizaje alta para APIs simples",
            }
        ],
        "stack_tecnico_relevante": [
            {
                "nombre": "FastAPI",
                "version": "0.111.0",
                "rol": "Framework API REST",
                "url_docs": "https://fastapi.tiangolo.com/",
            },
            {
                "nombre": "SQLite",
                "version": "3.45+",
                "rol": "Base de datos",
                "url_docs": "https://sqlite.org/docs.html",
            },
        ],
        "gaps_conocidos": ["Benchmarks de performance SQLite vs PostgreSQL en 2026 no disponibles"],
        "proximos_pasos": [
            {
                "accion": "Crear proyecto FastAPI con `fastapi-cli new`",
                "prioridad": "alta",
                "herramienta": "fastapi-cli",
            },
            {
                "accion": "Configurar SQLAlchemy 2.0 con SQLite y Alembic para migraciones",
                "prioridad": "alta",
                "herramienta": "SQLAlchemy + Alembic",
            },
            {
                "accion": "Agregar autenticación JWT con python-jose o authlib",
                "prioridad": "media",
                "herramienta": "python-jose / authlib",
            },
        ],
        "bitacora": {
            "sub_queries_generadas": [
                "¿Qué ORM usar con FastAPI?",
                "¿SQLite o PostgreSQL para solo developer?",
                "¿Qué auth library para FastAPI?",
            ],
            "estrategia_usada": "decompose + cross_reference",
            "rondas_busqueda": 2,
        },
    }

    sample_query = "¿Cuál es el stack mínimo viable para una micro-web con autenticación, base de datos y API REST mantenible por un solo desarrollador en 2026?"
    sample_cq = ["¿SQLite o Postgres para solo developer?", "¿Qué auth library usar?"]

    print(f"Evaluando RP sintético para: {sample_query[:60]}...")

    try:
        result = evaluate(sample_rp, sample_query, sample_cq)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"\nTotal ponderado: {result['total']:.4f}")
        print("Judge smoke test: OK")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
