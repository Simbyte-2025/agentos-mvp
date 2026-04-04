# AutoResearch Loop — Setup & Usage

## Resumen

Este sistema implementa un loop de optimización de Research Packages (RPs). El pipeline `rp_pipeline.py` es evaluado por `judge.py` en cada iteración. Si el score mejora, el pipeline se commitea; si no, se revierte.

```
benchmarks/research_queries.yaml   ← FIJO, nunca modificado
         │
         ▼
   rp_pipeline.py                  ← MODIFICADO por el loop para mejorar
         │
         ▼
      judge.py                     ← INMUTABLE, evalúa con temperature=0
         │
         ▼
  experiments/EXP_*.json           ← Resultados históricos
```

---

## Instalación

```bash
pip install anthropic pyyaml
```

Verificar que estén instalados:

```bash
python -c "import anthropic, yaml; print('OK')"
```

---

## Configuración

Configura la API key de Anthropic:

```bash
# Linux/macOS
export ANTHROPIC_API_KEY="sk-ant-..."

# Windows (PowerShell)
$env:ANTHROPIC_API_KEY = "sk-ant-..."

# Windows (CMD)
set ANTHROPIC_API_KEY=sk-ant-...
```

---

## Uso

### 1. Verificar el judge

Primero, verifica que el evaluador funciona correctamente:

```bash
python judge.py
```

Debe imprimir scores y observaciones para un RP sintético de prueba.

### 2. Ejecutar baseline (modo --once)

Evalúa el pipeline actual sin hacer commits. Establece el score de referencia:

```bash
python loop.py --once
```

Resultados guardados en `experiments/EXP_<timestamp>.json`.

### 3. Ejecutar el loop completo

Cuando estés listo para iterar (el loop hará commits automáticos si mejora):

```bash
python loop.py
```

En cada iteración:
- Si `avg_score > best` → `git commit` de `rp_pipeline.py`
- Si `avg_score <= best` → `git checkout rp_pipeline.py` (revert)

### 4. Ver el mejor resultado

```bash
cat experiments/best.json
```

### 5. Ver resultados de un experimento

```bash
python -c "
import json
with open('experiments/EXP_<ID>.json') as f:
    d = json.load(f)
print(f'Score: {d[\"avg_score\"]}')
for r in d['results']:
    print(f'  {r[\"query_id\"]}: {r[\"evaluation\"][\"total\"]:.4f}')
"
```

---

## Estructura de archivos

```
.
├── benchmarks/
│   └── research_queries.yaml     # 10 queries fijas (NUNCA modificar)
├── experiments/
│   ├── .gitkeep
│   ├── best.json                  # Mejor score registrado
│   └── EXP_<timestamp>.json       # Resultados por experimento
├── agentos/llm/
│   └── anthropic_client.py        # Cliente Claude (base)
├── rp_pipeline.py                 # Pipeline modificable por el loop
├── judge.py                       # Evaluador inmutable
├── loop.py                        # Harness del experimento
├── research_directives.md         # Instrucciones estratégicas
└── SETUP.md                       # Este archivo
```

---

## Dimensiones de evaluación (judge.py)

| Dimensión              | Peso | Descripción                                      |
|------------------------|------|--------------------------------------------------|
| completitud_estructural| 0.35 | Todas las secciones presentes con contenido real |
| verificabilidad        | 0.30 | Claims marcados, fuentes citadas, descartes documentados |
| accionabilidad_fase5   | 0.25 | Pasos ejecutables, versiones específicas, preguntas críticas respondidas |
| trazabilidad           | 0.10 | Bitácora con sub-queries y estrategia documentada |

Score máximo: **1.0** — Un score > 0.75 indica un RP de alta calidad.

---

## Troubleshooting

**`RuntimeError: ANTHROPIC_API_KEY no configurada`**
→ Configura la variable de entorno (ver sección Configuración)

**`ModuleNotFoundError: No module named 'anthropic'`**
→ Ejecuta `pip install anthropic`

**`ModuleNotFoundError: No module named 'yaml'`**
→ Ejecuta `pip install pyyaml`

**Judge retorna scores de 0.0 en todas las dimensiones**
→ El RP tiene errores de formato. Revisa que `run_research()` retorne JSON válido con todas las secciones.

**Git commit falla en loop mode**
→ Verifica que estás en la rama correcta y no hay conflictos pendientes.
