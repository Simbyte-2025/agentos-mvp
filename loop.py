"""AutoResearch Loop — experiment harness for Research Package optimization.

Usage:
    python loop.py --once          # Baseline mode: evaluate without git changes
    python loop.py                 # Loop mode: commit improvements, revert regressions
    python loop.py --exp-id EXP_42 # Use a specific experiment ID

The loop reads benchmarks/research_queries.yaml (NEVER modified),
runs each query through rp_pipeline.run_research(), evaluates with judge.evaluate(),
and saves results to experiments/EXP_<ID>.json.

In loop mode:
    - avg_score > best → git add rp_pipeline.py && git commit
    - avg_score <= best → git checkout rp_pipeline.py  (revert)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent
BENCHMARKS_FILE = REPO_ROOT / "benchmarks" / "research_queries.yaml"
EXPERIMENTS_DIR = REPO_ROOT / "experiments"
BEST_FILE = EXPERIMENTS_DIR / "best.json"


def load_queries() -> list[dict]:
    """Carga las queries del benchmark (NUNCA modificado por el loop)."""
    with open(BENCHMARKS_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["queries"]


def load_best() -> dict:
    """Carga el mejor resultado previo."""
    if BEST_FILE.exists():
        with open(BEST_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"score": 0.0, "exp_id": None}


def save_best(score: float, exp_id: str) -> None:
    """Guarda el nuevo mejor resultado."""
    EXPERIMENTS_DIR.mkdir(exist_ok=True)
    with open(BEST_FILE, "w", encoding="utf-8") as f:
        json.dump({"score": score, "exp_id": exp_id}, f, indent=2)


def generate_exp_id() -> str:
    """Genera un ID de experimento único basado en timestamp."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"EXP_{ts}"


def run_experiment(queries: list[dict]) -> tuple[float, list[dict]]:
    """Ejecuta todas las queries y evalúa los resultados.

    Returns:
        (avg_score, results) donde results es una lista de dicts por query
    """
    from judge import evaluate
    from rp_pipeline import run_research

    results = []
    total_score = 0.0

    for i, q in enumerate(queries, 1):
        qid = q["id"]
        query_text = q["query"]
        cq = q.get("fase5_critical_questions", [])

        print(f"  [{i}/{len(queries)}] {qid}: {query_text[:60]}...")

        # Generar Research Package
        try:
            rp = run_research(query_text)
        except Exception as e:
            print(f"    ERROR en run_research: {e}")
            rp = {
                "resumen_ejecutivo": f"[ERROR] {e}",
                "hallazgos_verificados": [],
                "hallazgos_descartados": [],
                "stack_tecnico_relevante": [],
                "gaps_conocidos": [str(e)],
                "proximos_pasos": [],
                "bitacora": {"sub_queries_generadas": [], "estrategia_usada": "error", "rondas_busqueda": 0},
            }

        # Evaluar con el judge
        try:
            eval_result = evaluate(rp, query_text, cq)
        except Exception as e:
            print(f"    ERROR en evaluate: {e}")
            eval_result = {
                "scores": {
                    "completitud_estructural": 0.0,
                    "verificabilidad": 0.0,
                    "accionabilidad_fase5": 0.0,
                    "trazabilidad": 0.0,
                },
                "total": 0.0,
                "observations": [f"Error en judge: {e}"],
            }

        score = eval_result["total"]
        total_score += score
        print(f"    score={score:.4f} | {', '.join(eval_result['observations'][:2])}")

        results.append(
            {
                "query_id": qid,
                "domain": q.get("domain", ""),
                "query": query_text,
                "research_package": rp,
                "evaluation": eval_result,
            }
        )

    avg_score = total_score / len(queries) if queries else 0.0
    return avg_score, results


def save_experiment(exp_id: str, avg_score: float, results: list[dict]) -> None:
    """Guarda el experimento completo a disco."""
    EXPERIMENTS_DIR.mkdir(exist_ok=True)
    exp_file = EXPERIMENTS_DIR / f"{exp_id}.json"

    payload = {
        "exp_id": exp_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "avg_score": round(avg_score, 4),
        "query_count": len(results),
        "results": results,
    }

    with open(exp_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"  Guardado: {exp_file}")


def git_commit_pipeline(exp_id: str, score: float) -> None:
    """Hace git add + commit de rp_pipeline.py con el score como mensaje."""
    msg = f"exp({exp_id}): avg_score={score:.4f} — improve rp_pipeline"
    subprocess.run(
        ["git", "add", "rp_pipeline.py"],
        check=True,
        cwd=REPO_ROOT,
    )
    subprocess.run(
        ["git", "commit", "-m", msg],
        check=True,
        cwd=REPO_ROOT,
    )
    print(f"  Commiteado: {msg}")


def git_revert_pipeline() -> None:
    """Revierte rp_pipeline.py al último commit (descarta cambios)."""
    subprocess.run(
        ["git", "checkout", "rp_pipeline.py"],
        check=True,
        cwd=REPO_ROOT,
    )
    print("  Revertido: rp_pipeline.py restaurado al último commit.")


def main() -> None:
    parser = argparse.ArgumentParser(description="AutoResearch Loop")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Modo baseline: evalúa sin hacer git commit/revert",
    )
    parser.add_argument(
        "--exp-id",
        type=str,
        default=None,
        help="ID de experimento personalizado (default: auto-generado)",
    )
    args = parser.parse_args()

    # Verificar API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY no configurada.")
        sys.exit(1)

    # Cargar benchmark
    queries = load_queries()
    print(f"Benchmark cargado: {len(queries)} queries")

    # ID de experimento
    exp_id = args.exp_id or generate_exp_id()
    print(f"Experimento: {exp_id} | modo={'--once (baseline)' if args.once else 'loop'}")
    print()

    # Ejecutar experimento
    print("Ejecutando investigación + evaluación...")
    start = time.time()
    avg_score, results = run_experiment(queries)
    elapsed = time.time() - start

    print()
    print(f"Resultado: avg_score={avg_score:.4f} | tiempo={elapsed:.1f}s")

    # Guardar experimento
    save_experiment(exp_id, avg_score, results)

    if args.once:
        print(f"\nModo --once: sin cambios en git. Score baseline={avg_score:.4f}")
        # Guardar como best si no hay best previo
        best = load_best()
        if best["score"] == 0.0:
            save_best(avg_score, exp_id)
            print(f"Best inicializado: {avg_score:.4f}")
        return

    # Modo loop: comparar con best y decidir commit/revert
    best = load_best()
    best_score = best["score"]

    print(f"\nComparando: nuevo={avg_score:.4f} vs best={best_score:.4f}")

    if avg_score > best_score:
        print(f"MEJORA detectada (+{avg_score - best_score:.4f}) → commit")
        git_commit_pipeline(exp_id, avg_score)
        save_best(avg_score, exp_id)
    else:
        print(f"Sin mejora ({avg_score:.4f} <= {best_score:.4f}) → revert")
        git_revert_pipeline()

    print(f"\nLoop iteration completada. Best score: {max(avg_score, best_score):.4f}")


if __name__ == "__main__":
    main()
