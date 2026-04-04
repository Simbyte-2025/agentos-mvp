# Baseline Comparativo

## Resumen ejecutivo

`agentos-mvp-main` es un runtime pequeño y explícito orientado a API, seguridad por perfiles, orquestación acotada y memoria modular.  
`jan-research-main` es una base mucho más amplia, orientada a CLI/REPL, sesiones ricas, permisos interactivos, bridge remoto, plugins, skills y operación multi-superficie.

La oportunidad no está en migrar módulos completos, sino en extraer patrones concretos de runtime, sesión, permisos y operación que refuercen AgentOS sin absorber complejidad innecesaria.

## Mapa funcional resumido de AgentOS

| Dominio | Evidencia principal | Lectura |
| --- | --- | --- |
| API | `agentos/api/main.py` | FastAPI con bootstrap de agentes, tools y orquestador. |
| Orquestación | `agentos/orchestrators/planner_executor.py` | Planner-Executor acotado con replan y límites explícitos. |
| Herramientas | `agentos/tools/*`, `agentos/tools/registry.py` | Registro y ejecución simples, con foco en control. |
| Seguridad | `agentos/security/permissions.py`, ADR 002 | Permisos por perfil y allowlists explícitas. |
| Memoria | `agentos/memory/*`, ADR 004 | Short-term, working state y long-term desacoplados. |
| Integración LLM | `agentos/llm/*`, `agentos/integrations/mcp/*` | Integración mínima, encapsulada y relativamente limpia. |
| Observabilidad | `agentos/observability/logging.py` | Logging estructurado básico. |

## Mapa funcional resumido de jan-research-main

| Dominio | Evidencia principal | Lectura |
| --- | --- | --- |
| Entrada y runtime | `src/main.tsx`, `src/setup.ts`, `src/bootstrap/state.ts` | Arranque denso, muchas side effects y estado global amplio. |
| Núcleo conversacional | `src/QueryEngine.ts`, `src/query.ts` | Motor de conversación/sesión persistente con budgets, tools y contexto. |
| Herramientas y permisos | `src/Tool.ts`, `src/tools`, `src/utils/permissions` | Sistema amplio, con contexto rico y controles interactivos. |
| Sesión e historial | `src/history.ts`, `src/memdir`, `src/utils/sessionStorage.ts` | Persistencia y recuperación de contexto mucho más maduras. |
| Bridge remoto | `src/bridge/*`, `src/remote/*`, `src/server/*` | Capacidades remotas relevantes para futuras integraciones. |
| CLI y comandos | `src/cli/*`, `src/commands/*` | Superficie operativa extensa y opinionated. |
| Extensibilidad | `src/plugins/*`, `src/skills/*`, `src/services/mcp/*` | Ecosistema de extensiones y conectores. |

## Diferencias estructurales clave

| Eje | AgentOS | jan-research-main | Implicación |
| --- | --- | --- | --- |
| Superficie principal | API runtime | CLI/REPL runtime | Integración directa de UI/CLI no es prioritaria. |
| Estado global | Reducido | Extenso y centralizado | Alto riesgo de importar complejidad accidental. |
| Seguridad | Permisos declarativos simples | Permisos interactivos y contextuales | Útil como referencia para una futura capa avanzada. |
| Sesión | Checkpoints y memoria MVP | Gestión de sesión madura y persistente | Gran fuente de ideas para evolución de AgentOS. |
| Extensibilidad | Agentes/tools configurados por YAML | Plugins, skills, MCP, comandos, remote | Conviene extraer patrones, no copiar arquitectura completa. |

## Tabla definitiva de bloques

| Bloque | Nombre | Alcance primario en jan-research-main | Prioridad |
| --- | --- | --- | --- |
| 0 | Baseline comparativo | Mapas funcionales y correspondencias | Alta |
| 1 | Núcleo de ejecución y entrada del sistema | `main.tsx`, `setup.ts`, `bootstrap/state.ts`, `context.ts`, `replLauncher.tsx`, `projectOnboardingState.ts` | Alta |
| 2 | Orquestación, tareas y coordinación de agentes | `QueryEngine.ts`, `query.ts`, `tasks*`, `assistant`, `coordinator` | Alta |
| 3 | Herramientas, permisos y sandbox | `Tool.ts`, `tools`, `utils/permissions`, hooks relacionados | Alta |
| 4 | Sesión, memoria, historial y persistencia | `history.ts`, `memdir`, `sessionStorage`, restore y caches | Alta |
| 5 | Bridge remoto, transporte e integración externa | `bridge`, `remote`, `server`, transports | Media |
| 6 | CLI, comandos y operación | `cli`, `commands` | Media |
| 7 | Servicios transversales y utilidades críticas | `services`, `utils`, `migrations`, plugins, skills | Media |
| 8 | UI y superficies no nucleares | `components`, `screens`, `buddy`, `voice`, `vim` | Baja |

## Correspondencias iniciales entre dominios

| jan-research-main | AgentOS equivalente o aspiracional | Observación |
| --- | --- | --- |
| `QueryEngine` | `PlannerExecutorOrchestrator` + routers + memoria | Similaridad parcial; QueryEngine es más amplio y conversacional. |
| `Tool` / permisos contextuales | `BaseTool` + `PermissionValidator` | AgentOS está más simple y más controlado. |
| `history` / session storage | `ShortTermMemory` + `WorkingStateStore` | Brecha importante a favor de jan. |
| `main/setup/bootstrap` | `api/main.py` bootstrap | AgentOS tiene arranque más limpio y más pequeño. |
| `bridge/remote` | `integrations/mcp/*` | jan aporta ideas para capas futuras de conectividad. |

## Criterio operativo para el resto de bloques

- Priorizar patrones reutilizables sobre módulos completos.
- Evitar trasladar estado global masivo a AgentOS.
- Favorecer ideas que fortalezcan seguridad, sesión, trazabilidad y operación.
- Tratar UI, REPL y ergonomía CLI como referencia secundaria salvo que resuelvan una brecha nuclear.
