# Bloque 2. Orquestación, tareas y coordinación de agentes

## Objetivo funcional del bloque

Analizar cómo `jan-research-main` coordina conversación, tools, subagentes y tareas asíncronas dentro de un loop operativo continuo; luego contrastarlo con la orquestación actual de AgentOS para determinar qué capacidades conviene adoptar como evolución del runtime sin absorber el modelo completo de REPL/CLI.

## Delimitación y mapa de archivos

| Archivo o área | Responsabilidad | Relevancia |
| --- | --- | --- |
| `jan-research-main/src/QueryEngine.ts` | Motor de conversación por sesión y turnos, con estado persistente entre mensajes | Núcleo del bloque |
| `jan-research-main/src/query.ts` | Query loop, control de turns, budgets, herramientas y compactación | Núcleo del bloque |
| `jan-research-main/src/Task.ts` | Contratos base de tarea, estados y contexto de ejecución | Contrato estructural clave |
| `jan-research-main/src/tasks.ts` | Registro y despacho por tipo de tarea | Capa de extensión |
| `jan-research-main/src/tasks/LocalAgentTask/LocalAgentTask.tsx` | Gestión de subagentes locales como tareas de fondo | Patrón relevante |
| `jan-research-main/src/services/tools/toolOrchestration.ts` | Orquestación serial/paralela de tool calls | Patrón reutilizable con límites |
| `jan-research-main/src/services/tools/StreamingToolExecutor.ts` | Ejecución incremental de tools con concurrencia y cancelación | Referencia avanzada |
| `jan-research-main/src/coordinator/coordinatorMode.ts` | Coordinación explícita entre workers y fases de trabajo | Referencia de producto/orquestación |
| `agentos-mvp-main/agentos/orchestrators/planner_executor.py` | Orquestador principal de AgentOS | Referencia de contraste |
| `agentos-mvp-main/agentos/orchestrators/router.py` | Selección de agente y tools | Referencia de contraste |
| `agentos-mvp-main/agentos/orchestrators/sequential.py` | Ruta simple de ejecución | Referencia de contraste |

## Arquitectura y flujo principal

En `jan-research-main`, la orquestación no se limita a “planificar y ejecutar”. El sistema combina:

- un `QueryEngine` persistente por conversación
- un `query loop` que itera entre modelo, tool calls, compactación, presupuestos y estados de corte
- un sistema de tareas tipadas para background agents, shell, workflows, monitores y sesiones remotas
- una capa de coordinación explícita para trabajo concurrente con workers

El loop principal acepta un mensaje, acumula contexto, delega al modelo, ejecuta tools en serie o en paralelo según seguridad/concurrencia, actualiza estado y puede continuar múltiples turns bajo límites de `maxTurns` y `taskBudget`. A esto se suma una abstracción de `Task` con ciclo de vida claro (`pending`, `running`, `completed`, `failed`, `killed`) y mecanismos de kill, progreso, notificación y evicción.

AgentOS hoy tiene dos variantes de orquestación más simples:

- `SequentialOrchestrator`: selecciona un agente, elige tools permitidas y ejecuta una tarea.
- `PlannerExecutorOrchestrator`: divide una tarea en subtareas, usa LLM para plan y replan, ejecuta cada subtarea y consolida resultados.

Esto hace que AgentOS sea mucho más pequeño y controlable, pero también deja brechas claras: no existe un contrato formal de subtarea con progreso observable más allá del `Subtask` interno, no hay lifecycle rico para tareas activas, no existe paralelismo controlado entre tools, y la coordinación entre agentes sigue siendo muy básica.

## Interfaces, dependencias y acoplamientos

- `jan` acopla la orquestación al modelo conversacional continuo, a la UI/SDK y a estados de sesión complejos.
- `Task.ts` y `tasks/*` definen un contrato más reusable que el loop conversacional completo.
- `toolOrchestration.ts` separa una idea útil: clasificar tool calls por seguridad de concurrencia y ejecutar batches acordes.
- `StreamingToolExecutor.ts` agrega cancelación, buffering, orden y recuperación, pero está muy ligado a streaming de modelo y semántica de mensajes.
- En AgentOS, `PlannerExecutorOrchestrator` encapsula bien la secuencia plan-ejecución-replan, pero el contrato operativo termina siendo demasiado estrecho para futuras capacidades de progreso, background work o coordinación explícita.

## Fortalezas y debilidades

### Fortalezas

- `jan` posee un modelo mucho más maduro de lifecycle operativo, con tareas tipadas, estados terminales y mecanismos de cancelación.
- `jan` trata la concurrencia de tools con criterios explícitos de seguridad, no solo como optimización.
- `jan` hace visible el progreso de agentes y tareas, lo que mejora operación y depuración.
- AgentOS mantiene una orquestación mucho más fácil de razonar y de asegurar.

### Debilidades

- El loop de `jan` tiene una complejidad muy superior a la necesaria para el estado actual de AgentOS.
- Gran parte de su valor depende de un ecosistema más amplio: streaming, UI, sesión interactiva, workers y background tasks.
- AgentOS no tiene hoy un contrato operativo común para subtareas más allá de estructuras ad hoc dentro del orquestador.
- La coordinación multiagente de AgentOS sigue siendo implícita y con poca telemetría fina.

## Riesgos técnicos y de seguridad

- Portar el loop conversacional completo de `jan` introduciría complejidad de producto y superficie de fallo excesivas para AgentOS.
- Habilitar paralelismo de tools sin aislamiento y permisos más ricos podría romper el modelo de mínimo privilegio.
- Incorporar subagentes o workers sin un contrato claro de cancelación, ownership y observabilidad generaría ejecución difícil de auditar.

## Deuda técnica detectada

- `PlannerExecutorOrchestrator` carece de un contrato reutilizable de task/subtask lifecycle fuera del dataclass `Subtask`.
- `SequentialOrchestrator` y `PlannerExecutorOrchestrator` comparten conceptos, pero no un framework operacional común.
- No hay aún un modelo estándar para progreso, cancelación, reintentos y notificación por subtarea.
- La selección y ejecución de tools en AgentOS sigue siendo síncrona y lineal, incluso cuando algunas operaciones podrían agruparse de forma segura.

## Contraste con AgentOS

| Capacidad en código auditado | Equivalente en AgentOS | Brecha | Decisión |
| --- | --- | --- | --- |
| Loop conversacional persistente por turnos | `SequentialOrchestrator` y `PlannerExecutorOrchestrator` | AgentOS no busca operar como REPL continuo | `Rechazar` |
| Tareas tipadas con lifecycle explícito | `Subtask` interno y resultados finales | Brecha clara en contratos operativos | `Adaptar` |
| Coordinación explícita de workers/subagentes | Replan + router simple | AgentOS no tiene coordinación rica | `Adaptar` |
| Concurrencia segura de tools por lotes | Selección lineal de tools | Brecha moderada y sensible a seguridad | `Postergar` |
| Progress, cancelación y notificación de tareas | Logging y checkpoint básicos | Brecha clara de observabilidad operativa | `Adaptar` |
| Streaming tool executor | No existe | Demasiado acoplado al modelo conversacional de jan | `Postergar` |

## Evaluación de utilidad para integración

| Capacidad | Veredicto | Esfuerzo | Riesgo | Recomendación |
| --- | --- | --- | --- | --- |
| Introducir contrato común de task/subtask state | reusable with refactor | Medio | Bajo | Modelar subtareas y ejecuciones con estados, timestamps, retry y cancelación |
| Mejorar observabilidad de progreso por subtarea | reusable with refactor | Medio | Bajo | Extender checkpoints y logging con eventos operativos más granulares |
| Coordinar subagentes o workers explícitos | useful as reference only | Alto | Medio | Diseñar luego de consolidar lifecycle y permisos |
| Ejecutar tools read-only en paralelo | reusable with refactor | Medio | Medio | Explorar solo tras definir clases de riesgo y aislamiento |
| Portar QueryEngine/query loop | not recommended for AgentOS | Alto | Alto | Mantener AgentOS como runtime acotado, no REPL completo |
| Portar StreamingToolExecutor completo | useful as reference only | Alto | Alto | Extraer solo ideas de cancelación y orden de resultados |

## Recomendación accionable

- Diseñar un contrato operativo compartido en AgentOS para ejecución de tareas y subtareas, con estados, retry, timestamps, error y cancelación.
- Extender `PlannerExecutorOrchestrator` para emitir progreso estructurado por subtarea en `working_state` y logs, no solo el resultado final.
- Mantener fuera del corto plazo la adopción del loop conversacional continuo de `jan`.
- Evaluar en una fase posterior un `tool execution policy` que permita paralelismo solo para herramientas clasificadas como seguras y no mutantes.
- Preparar un ADR para “task runtime model” antes de incorporar subagentes, background work o tool concurrency.

## Informe técnico ejecutivo

### Resumen ejecutivo

`jan-research-main` resuelve la orquestación como un sistema conversacional continuo, con tareas vivas, coordinación explícita y ejecución de tools bajo políticas de concurrencia. Esa arquitectura supera ampliamente lo que AgentOS necesita hoy, pero contiene patrones valiosos para evolucionar su runtime.

### Utilidad concreta para AgentOS

La principal utilidad está en formalizar el lifecycle de tareas/subtareas, mejorar la observabilidad operativa y, más adelante, estudiar paralelismo seguro de tools. No conviene importar el motor conversacional completo.

### Decisión recomendada

`Adaptar`

### Esfuerzo estimado

`Medio`

### Riesgo estimado

`Medio`

### Prioridad sugerida para roadmap

`Alta`
