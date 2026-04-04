# Bloque 3. Herramientas, permisos y sandbox

## Objetivo funcional del bloque

Analizar en detalle el sistema de herramientas, permisos y sandbox de `jan-research-main` — cómo define, registra, valida, ejecuta y controla herramientas — y contrastarlo con el modelo de tools, allowlists y permisos declarativos de AgentOS para identificar patrones reutilizables, brechas críticas y riesgos de integración.

## Delimitación y mapa de archivos

| Archivo o área | Responsabilidad | Relevancia |
| --- | --- | --- |
| `jan/src/Tool.ts` (793 líneas) | Contrato base de herramienta: interfaces `Tool`, `ToolDef`, `ToolUseContext`, `ToolPermissionContext`, factory `buildTool`, tipos de resultado/progreso | Núcleo del bloque |
| `jan/src/tools.ts` (390 líneas) | Registro centralizado, ensamblaje dinámico del tool pool, filtrado por feature flags y deny rules, deduplicación con MCP tools | Núcleo del bloque |
| `jan/src/tools/BashTool/` (18 archivos, ~580K bytes) | Ejecución shell con ~2600 líneas de seguridad (`bashSecurity.ts`), ~2600 de permisos (`bashPermissions.ts`), validación de paths, read-only, sed, sandbox | Referencia clave de seguridad |
| `jan/src/tools/FileReadTool/` (5 archivos) | Lectura con dedup, límites de tokens, soporte PDF/imagen/notebook, permisos filesystem | Referencia de capacidad |
| `jan/src/tools/FileWriteTool/` y `FileEditTool/` | Escritura y edición con history tracking, permisos, IDE notification | Referencia de capacidad |
| `jan/src/tools/AgentTool/` (14 archivos, ~500K bytes) | Subagentes como tools: spawn, fork, resume, memoria, color management | Patrón clave de orquestación-tools |
| `jan/src/tools/TaskCreateTool/`, `TaskGetTool/`, `TaskListTool/`, `TaskOutputTool/`, `TaskStopTool/`, `TaskUpdateTool/` | CRUD de tareas como herramientas invocables por el modelo | Patrón de task management |
| `jan/src/tools/MCPTool/`, `WebFetchTool/`, `WebSearchTool/`, `SkillTool/`, `RemoteTriggerTool/`, `ScheduleCronTool/` | Integraciones externas y extensibilidad | Referencia de extensión |
| `jan/src/tools/AskUserQuestionTool/`, `BriefTool/`, `EnterPlanModeTool/`, `ExitPlanModeTool/`, `TodoWriteTool/`, `ConfigTool/` | UX, control de flujo modal, plan mode | Referencia de producto |
| `jan/src/utils/permissions/` (24 archivos, ~9.4K líneas) | Sistema completo: modes, rules, matcher, classifier, filesystem perms, setup, loader, denial tracking | Núcleo de permisos |
| `jan/src/utils/sandbox/` (2 archivos, ~1K líneas) | Adapter de sandbox con `SandboxManager`, anotación de violaciones | Referencia de sandbox |
| `jan/src/hooks/useCanUseTool.tsx` (~40K bytes) | Hook React para decisión de permiso interactivo en REPL | Referencia avanzada |
| `agentos/tools/base.py` | `BaseTool`, `ToolInput`, `ToolOutput` — contrato base | Referencia de contraste |
| `agentos/tools/registry.py` | `ToolRegistry` — registro simple | Referencia de contraste |
| `agentos/security/permissions.py` | `PermissionValidator` — permisos por perfil | Referencia de contraste |
| `agentos/security/run_command_allowlist.py` | `CommandAllowlist` — validación de comandos | Referencia de contraste |

## Arquitectura y flujo principal

### Sistema de herramientas de jan

El contrato `Tool` en jan es una interfaz TypeScript rica con ~50 campos/métodos que cubren:

1. **Definición**: `name`, `inputSchema` (Zod), `outputSchema`, `aliases`, `searchHint`, `shouldDefer`, `alwaysLoad`
2. **Ejecución**: `call()` con `ToolUseContext` completo (estado de app, abort controller, file state cache, agent ID, messages...)
3. **Permisos**: `checkPermissions()`, `validateInput()`, `preparePermissionMatcher()` — cada tool define su propia lógica de permisos
4. **Clasificación de seguridad**: `isConcurrencySafe()`, `isReadOnly()`, `isDestructive()`, `isOpenWorld()`
5. **Rendering**: `renderToolUseMessage()`, `renderToolResultMessage()`, `renderToolUseProgressMessage()`, etc. (UI en React/Ink)
6. **Factory centralizada**: `buildTool()` con defaults fail-closed (`isConcurrencySafe → false`, `isReadOnly → false`)

El registro (`tools.ts`) ensambla dinámicamente el pool usando feature flags (`bun:bundle`), conditional imports, filtrado por deny rules, y merge con MCP tools. Soporta presets y simple mode.

### Sistema de permisos de jan

El sistema de permisos es extremadamente sofisticado:

- **Modos**: `default`, `plan`, `auto/yolo`, `bypass` — cada uno con diferente nivel de confianza
- **Reglas**: `alwaysAllow`, `alwaysDeny`, `alwaysAsk` con soporte de wildcards y prefijos
- **Classifier**: Un sistema ML/heurístico (`yoloClassifier.ts`, 52K bytes) que evalúa si un comando es seguro para auto-approve
- **Por herramienta**: Cada tool implementa `checkPermissions()` con lógica específica (ej: BashTool tiene 2600 líneas de validación de seguridad de comandos shell)
- **Filesystem**: `permissions/filesystem.ts` (62K bytes) con validación granular de paths, working directories, deny rules para archivos
- **Denial tracking**: Seguimiento de denegaciones para auto-fallbacks

### Sistema de herramientas de AgentOS

El contrato de AgentOS es deliberadamente minimalista:

- `BaseTool`: ABC con `name`, `description`, `risk` (read/write/delete/execute), un `execute()` abstracto
- `ToolInput`/`ToolOutput`: Pydantic models simples
- `ToolRegistry`: Dict simple con `register()`/`get()`/`list()`
- `CommandAllowlist`: Allowlist estricta con 8 capas de seguridad pero solo para `run_command`
- `PermissionValidator`: Permisos declarativos por perfil YAML, matching simple por nombre de tool + acción

## Interfaces, dependencias y acoplamientos

- **jan** tiene un acoplamiento fuerte entre tools y UI (React rendering), estado de app (`AppState`), sistema de mensajes, y modo de permiso interactivo
- **jan** define `ToolUseContext` como un mega-objeto con ~40 campos que incluye estado de sesión, app state, abort controller, file caches, agent identity, etc.
- **jan** integra permissions dentro de cada tool (co-locate), no en una capa centralizada
- **AgentOS** mantiene tools completamente desacoplados de UI, con permisos centralizados y un contrato de tool muy estrecho
- **AgentOS** usa YAML para configuración estática, jan usa settings dinámicos + rules en tiempo de ejecución

## Fortalezas y debilidades

### Fortalezas

- **jan** tiene el sistema de seguridad de ejecución shell más completo que se puede encontrar en un agente: parsing de AST bash, tree-sitter analysis, validación de heredocs, detección de inyección de comandos, sandbox, path validation, read-only validation, sed validation — todo auditado con comentarios de seguridad extremadamente detallados
- **jan** clasifica cada tool por `isReadOnly`, `isConcurrencySafe`, `isDestructive` — habilitando políticas de ejecución diferenciadas
- **jan** tiene un modelo de `ToolDef → buildTool()` con defaults fail-closed que previene errores de configuración
- **jan** soporta herramientas como subagentes (`AgentTool`), tareas CRUD (`TaskCreateTool`...), y skills (`SkillTool`) — extensibilidad composicional
- **AgentOS** mantiene simplicidad y claridad en el contrato de tools
- **AgentOS** tiene separación limpia entre tool execution y security validation

### Debilidades

- **jan** tiene un contrato de tool de ~50 campos con fuerte acoplamiento a UI, sesión y estado global — imposible de portar directamente
- **jan** mezcla en `ToolUseContext` responsabilidades de ejecución, rendering, sesión y estado — un god object de facto
- **jan** distribuye lógica de permisos entre el tool individual, el sistema general y la UI (useCanUseTool hook)
- **AgentOS** carece de clasificación de seguridad por tool (`isReadOnly`, `isConcurrencySafe`, `isDestructive`)
- **AgentOS** no tiene validación de input por tool más allá de la estructura Pydantic
- **AgentOS** no soporta feature flags para tools condicionales
- **AgentOS** no tiene mecanismo de deny rules, wildcards, ni reglas de permiso por input/contenido

## Riesgos técnicos y de seguridad

- Importar el contrato completo de `Tool` de jan implicaría absorber dependencias de UI, estado global y sesión
- El sistema de permisos de jan está optimizado para interacción humana (REPL con prompts, approval dialogs) — no encaja en un runtime API headless
- Adoptar el classifier de permisos requeriría evaluar riesgos de false-positives/negatives en un contexto sin supervisión humana
- La allowlist actual de AgentOS cubre solo el 10% de las validaciones que jan hace para ejecución shell
- Sin clasificación de tools por riesgo, AgentOS no puede implementar ejecución concurrente segura ni políticas diferenciadas

## Deuda técnica detectada

- `BaseTool` de AgentOS no tiene `inputSchema` validable, `outputSchema`, ni metadatos de seguridad
- `ToolRegistry` de AgentOS no soporta filtrado por permisos, deny rules, ni feature flags
- No hay un patrón de `ToolContext` en AgentOS que provea el execution context necesario para tools complejas
- `PermissionValidator` solo soporta matching exacto por nombre de tool, no wildcards ni matching por input/contenido
- No existe validación pre-ejecución (`validateInput`) separada de permisos (`checkPermissions`) en AgentOS

## Contraste con AgentOS

| Capacidad en código auditado | Equivalente en AgentOS | Brecha | Decisión |
| --- | --- | --- | --- |
| Contrato `Tool` rico con ~50 campos y factory `buildTool` con defaults fail-closed | `BaseTool` con 5 atributos y `execute()` | Brecha alta en contrato y defaults | `Adaptar` |
| Clasificación de seguridad por tool: `isReadOnly`, `isConcurrencySafe`, `isDestructive` | Solo `risk` como string (read/write/delete/execute) | Brecha alta — sin granularidad operativa | `Adoptar` |
| Validación pre-ejecución `validateInput()` separada de `checkPermissions()` | No existe — todo en `execute()` | Brecha moderada | `Adoptar` |
| Registro dinámico con feature flags, deny rules y merge con MCP tools | Dict simple sin filtrado | Brecha alta | `Adaptar` |
| `ToolUseContext` con ~40 campos (estado, abort, caches, agent) | Sin contexto de ejecución formal | Brecha alta | `Adaptar` |
| BashTool: 2600 líneas de seguridad shell (AST, tree-sitter, heredoc, injection) | `CommandAllowlist`: 130 líneas, allowlist estática | Brecha máxima en seguridad shell | `Adaptar` |
| Permisos con modes, rules, wildcards, classifier, filesystem validation | `PermissionValidator` con matching exacto por nombre | Brecha máxima en permisos | `Adaptar` |
| Sandbox adapter con annotación de violaciones | Tempdir isolation básico | Brecha moderada | `Postergar` |
| AgentTool: subagentes como tools invocables | No existe | Brecha alta para composición | `Adaptar` |
| TaskCRUD tools (Create/Get/List/Stop/Update) | No existe — tasks son internas al orchestrator | Brecha moderada | `Adaptar` |
| SkillTool, WebSearchTool, RemoteTriggerTool, CronTools | `http_fetch` básico, sin skills ni cron | Brecha moderada en extensibilidad | `Postergar` |
| Rendering React/Ink por tool | No aplica — AgentOS es API headless | No es brecha | `Rechazar` |
| PlanMode tools (Enter/Exit), BriefTool, TodoWriteTool | No existe | Bajo valor para MVP | `Postergar` |

## Evaluación de utilidad para integración

| Capacidad | Veredicto | Esfuerzo | Riesgo | Recomendación |
| --- | --- | --- | --- | --- |
| Enriquecer `BaseTool` con metadatos de seguridad y `buildTool` factory | reusable with refactor | Medio | Bajo | Agregar `is_read_only`, `is_concurrent_safe`, `is_destructive`, `validate_input()` y factory con defaults |
| Separar `validate_input()` de `check_permissions()` | reusable directly | Bajo | Bajo | Agregar ciclo de vida pre-ejecución en dos fases |
| Introducir `ToolExecutionContext` para reemplazar params ad hoc | reusable with refactor | Medio | Bajo | Diseñar un context object lean (request, session, permissions, abort) sin UI |
| Clasificar tools por nivel de riesgo operativo | reusable directly | Bajo | Bajo | Extender `risk` a un modelo multi-dimensional |
| Agregar deny rules y wildcards a permisos | reusable with refactor | Medio | Medio | Extender `PermissionValidator` con patterns y deny lists |
| Portar validación de seguridad shell de BashTool | useful as reference only | Alto | Alto | Usar como referencia para evolución de `run_command` — el volumen y complejidad son excesivos para AgentOS hoy |
| Portar el classifier de permisos (yoloClassifier) | not recommended for AgentOS | Alto | Alto | Requiere datos de entrenamiento y evaluación — no encaja en MVP |
| Introducir tools como subagentes (AgentTool pattern) | useful as reference only | Alto | Medio | Diseñar después de tener task lifecycle (B-004) |
| Task CRUD como tools invocables por LLM | reusable with refactor | Medio | Bajo | Útil tras implementar contrato de tareas (B-004) |
| Portar rendering React/Ink de tools | not recommended for AgentOS | N/A | N/A | AgentOS es headless |
| Sandbox adapter con policy-based decisions | useful as reference only | Medio | Medio | Referencia para evolución del backend Docker |
| Deferred tools con ToolSearch | useful as reference only | Alto | Medio | Patrón interesante para optimización cuando el catálogo de tools crezca |

## Recomendación accionable

1. **Enriquecer `BaseTool` inmediatamente**: Agregar `is_read_only: bool`, `is_concurrent_safe: bool`, `is_destructive: bool`, y separar `validate_input()` de `check_permissions()` como métodos opcionales con defaults fail-closed (como `buildTool` de jan).
2. **Crear `ToolExecutionContext`**: Un dataclass lean que contenga `request_id`, `session_id`, `user_id`, `permissions`, `abort_signal`, `workspace_path` — sin UI ni estado global.
3. **Extender `PermissionValidator`**: Soportar deny rules, wildcards (`*` y prefijos con `:`), y matching por contenido del input además de por nombre de tool.
4. **Adoptar el patrón de validación por fases**: `validate_input()` → `check_permissions()` → `execute()` como pipeline estándar.
5. **Estudiar la seguridad shell de jan como referencia**: No portar las 5000+ líneas, pero extraer el patrón de capas (AST parsing, path validation, read-only detection, operator blocking) para evolucionar `run_command`.
6. **Preparar un ADR para "tool security classification"**: Definir formalmente qué significa `read_only`, `concurrent_safe`, `destructive` en AgentOS y cómo se consume en orquestación y permisos.

## Informe técnico ejecutivo

### Resumen ejecutivo

El Bloque 3 revela la brecha más grande entre `jan-research-main` y AgentOS detectada hasta ahora. jan posee un sistema de herramientas con contrato rico (~50 campos), clasificación de seguridad integrada, 5000+ líneas de validación de seguridad shell, un sistema de permisos con 24 archivos especializados, y herramientas composicionales (subagentes, CRUD de tareas, skills). AgentOS tiene un contrato de tool de 5 atributos, un registry de 23 líneas, y permisos declarativos de 62 líneas. La brecha no es solo de volumen sino de modelo: jan trata cada tool como un ciudadano de primera clase con ciclo de vida completo, mientras AgentOS trata tools como funciones simples envueltas en ABC.

### Utilidad concreta para AgentOS

La utilidad es alta en cuatro áreas:
1. **Contrato de tool enriquecido** con metadatos de seguridad y factory con defaults (bajo esfuerzo, alto valor)
2. **Pipeline de validación por fases** — validate → permissions → execute (bajo esfuerzo, alto valor)
3. **Permisos más granulares** con deny rules y wildcards (medio esfuerzo, alto valor)
4. **Contexto de ejecución formal** — un `ToolExecutionContext` desacoplado de UI (medio esfuerzo, medio valor)

No conviene portar: rendering de tools, classifier ML de permisos, validación shell completa ($5000+ líneas), ni el patrón de AgentTool como subagente (requiere task lifecycle primero).

### Decisión recomendada

`Adaptar`

### Esfuerzo estimado

`Alto` (múltiples cambios en el modelo de tools, permisos y registry)

### Riesgo estimado

`Medio` (los cambios son extensiones, no reescrituras — mantener backward compatibility)

### Prioridad sugerida para roadmap

`Alta` — las mejoras en el contrato de tool y permisos son prerequisito para la mayoría de los ítems del backlog (B-004, B-005, B-006).
