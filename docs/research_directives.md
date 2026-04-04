# Research Directives — Strategic Instructions for the AutoResearch Loop

## Contexto: Quién es Nicolás

Nicolás es un desarrollador Python/FastAPI solo (solodev) basado en Chile, con experiencia en:
- **APIs y backends**: FastAPI, SQLAlchemy, Pydantic
- **Automatización**: Notion API, GitHub Actions, webhooks
- **IA aplicada**: Claude API (Anthropic), pipelines de agentes, tool use
- **Stack actual**: Python 3.11+, FastAPI, SQLite/PostgreSQL, Railway/Fly.io para deploy
- **Contexto regional**: Precios en USD, latencia desde Chile, sistemas chilenos (RUT, MINEDUC, etc.)

Los Research Packages deben ser **inmediatamente accionables** por un solo desarrollador sin necesidad de un equipo DevOps.

---

## Prioridades de Verificación

1. **Documentación oficial primero**: Anthropic docs, Notion API docs, FastAPI docs > blogs > posts de Medium/Dev.to
2. **Pricing 2026**: Precios de APIs cambian frecuentemente. Siempre marcar con [INCIERTO] si el precio no puede verificarse a la fecha actual.
3. **Versiones específicas**: Preferir versiones concretas (ej: `fastapi==0.111.0`) sobre referencias vagas ("la última versión").
4. **Disponibilidad en Chile**: Para servicios de deploy, verificar disponibilidad y latencia desde Sudamérica cuando aplique.
5. **Rate limits actuales**: Para Notion API, Claude API, GitHub API — los límites cambian. Marcar con [INCIERTO] si no son verificables.

---

## Secciones Críticas para Fase 5

### `stack_tecnico_relevante` (OBLIGATORIO)
- Mínimo 2 entradas, idealmente 3-5
- **Versión específica** para cada herramienta (no "latest")
- URL de docs oficiales en `url_docs`
- Rol claro en el stack (`rol` debe ser descriptivo, no genérico)

### `proximos_pasos` (OBLIGATORIO)
- Mínimo **3 acciones** concretas y ejecutables
- Cada acción debe ser realizable por Nicolás solo
- `herramienta` debe ser el nombre exacto del tool/library/comando
- `prioridad` debe reflejar secuencia lógica: no puede haber 3 items de prioridad "alta" si dependen unos de otros

### `hallazgos_descartados` (OBLIGATORIO — al menos 1)
- Mínimo **1 entrada** que documente una alternativa considerada y rechazada
- `razon_descarte` debe ser específica (ej: "overhead excesivo para solodev", "no disponible en Chile", "deprecado en 2025")
- Ejemplos válidos: un framework alternativo rechazado, una API sin soporte Python, una solución con costo prohibitivo

---

## Errores Comunes a Evitar

1. **Afirmaciones absolutas sin fuente**: "Notion soporta webhooks" → debe ser "Notion soporta webhooks (verificar docs: [url]) o [INCIERTO] si no está confirmado"
2. **`proximos_pasos` vagos**: "Investigar más sobre el tema" NO es un próximo paso válido. Debe ser "Ejecutar `pip install fastapi sqlalchemy` y crear `main.py` con los endpoints X, Y, Z"
3. **Versiones sin verificar**: No poner versiones inventadas. Preferir "[INCIERTO - verificar PyPI]" sobre una versión incorrecta
4. **`bitacora` vacío**: El campo `sub_queries_generadas` debe tener las sub-preguntas realmente usadas para razonar
5. **Ignorar el contexto chileno**: Para queries sobre deploy, educación, o sistemas locales, considerar la perspectiva chilena

---

## Lo que el Loop Agent PUEDE Modificar

El loop agent (un LLM externo que mejora `rp_pipeline.py` entre iteraciones) puede:

- ✅ Modificar valores en `RESEARCH_CONFIG` (estrategia, rounds, markers, etc.)
- ✅ Modificar el texto de `RESEARCH_SYSTEM_PROMPT` para mejorar la calidad de los RPs
- ✅ Cambiar el modelo en `run_research()` (ej: pasar a claude-opus-4-6 para mejor calidad)
- ✅ Ajustar `max_tokens` en el cliente
- ✅ Modificar `_build_research_prompt()` para construir prompts mejores
- ✅ Agregar lógica de post-procesamiento en `run_research()` (ej: validar secciones, rellenar campos vacíos)

## Lo que el Loop Agent NO PUEDE Modificar

- ❌ `benchmarks/research_queries.yaml` — benchmark fijo, nunca tocar
- ❌ `judge.py` — evaluador inmutable, nunca tocar
- ❌ `loop.py` — harness de experimentos, nunca tocar
- ❌ `research_directives.md` — este archivo, nunca tocar
- ❌ Archivos en `agentos/` — código del sistema subyacente
- ❌ Archivos en `experiments/` — resultados históricos (solo agregar, nunca modificar)

---

## Guía de Calidad para RPs

Un Research Package de alta calidad (score > 0.80) debe:

1. Tener un `resumen_ejecutivo` que sea accionable en 2-4 oraciones (no solo descriptivo)
2. Incluir hallazgos verificados con confianza diferenciada (no todos "alta")
3. Responder implícita o explícitamente las `fase5_critical_questions` del benchmark
4. Tener al menos 1 hallazgo descartado con razón específica
5. Listar tools con versiones y URLs de docs verificables
6. Tener gaps_conocidos honestos (admitir lo que no se sabe)
7. Tener bitácora con sub_queries que muestren el razonamiento
