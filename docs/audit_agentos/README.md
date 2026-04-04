# Programa de Auditoría e Integración

Este directorio implementa el plan metodológico para auditar `jan-research-main` y contrastarlo con `agentos-mvp-main`.

## Objetivo

Evaluar utilidad técnica real para AgentOS por bloques funcionales coherentes, con entregables comparables y trazables.

## Orden de ejecución

0. Baseline comparativo
1. Núcleo de ejecución y entrada del sistema
2. Orquestación, tareas y coordinación de agentes
3. Herramientas, permisos y sandbox
4. Sesión, memoria, historial y persistencia de contexto
5. Bridge remoto, transporte e integración externa
6. CLI, comandos operativos y experiencia de uso técnica
7. Servicios transversales y utilidades críticas
8. Componentes UI y superficies no nucleares

## Artefactos

- `00_marco_metodologico.md`: marco de evaluación congelado.
- `01_baseline_comparativo.md`: mapa funcional resumido y tabla definitiva de bloques.
- `02_registro_maestro.md`: acumulador de hallazgos, patrones y backlog.
- `templates/block_analysis_template.md`: plantilla única por bloque.
- `blocks/block_01_core_runtime.md`: primer bloque auditado.

## Convenciones

- Decisión por hallazgo: `Adoptar`, `Adaptar`, `Rechazar`, `Postergar`.
- Veredicto de reutilización: `reusable directly`, `reusable with refactor`, `useful as reference only`, `not recommended for AgentOS`.
- Escala de esfuerzo y riesgo: `Bajo`, `Medio`, `Alto`.
