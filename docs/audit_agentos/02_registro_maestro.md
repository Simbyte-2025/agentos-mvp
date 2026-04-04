# Registro Maestro de Hallazgos

## Patrones transversales detectados

| ID | Patrón | Origen | Lectura inicial | Estado |
| --- | --- | --- | --- | --- |
| P-001 | Runtime con contexto y estado de sesión muy rico | jan | Alto valor para evolución de AgentOS, pero no reusable directo. | Abierto |
| P-002 | Seguridad más contextual e interactiva | jan | Útil para una capa avanzada sobre el modelo declarativo actual de AgentOS. | Abierto |
| P-003 | Bootstrap pequeño y explícito | AgentOS | Debe preservarse; evita importar complejidad de entrada desde jan. | Fijado |
| P-004 | Orquestación como loop conversacional con budgets, streaming y tools intercaladas | jan | Útil como referencia para evolución del planner, no para adopción literal. | Abierto |
| P-005 | Tareas tipadas con progreso y lifecycle explícito | jan | Patrón con alto valor para trazabilidad y ejecución futura en AgentOS. | Abierto |
| P-006 | Contrato de tool como ciudadano de primera clase con metadatos de seguridad y factory fail-closed | jan | Patrón de alto valor: `buildTool()` con defaults seguros y clasificación multi-dimensional de riesgo. | Abierto |
| P-007 | Pipeline de validación por fases: validate → permissions → execute | jan | Separa validación de input de autorización, mejorando testabilidad y seguridad. | Abierto |
| P-008 | Permisos distribuidos entre tool individual y sistema general | jan | Riesgo de fragmentación; AgentOS debe favorecer centralización con extensión por tool. | Abierto |
| P-009 | Persistencia append-only JSONL con write-behind buffering y file locking | jan | Patrón production-grade para persistencia sin database — alto valor para conversaciones. | Abierto |
| P-010 | Tool result budget con threshold per-tool y persistence a disco | jan | Previene OOM y optimiza tokens en contextos con tools de output masivo. | Abierto |
| P-011 | Memoria tipada con taxonomía cerrada y behavioral instructions para el modelo | jan | Mejora calidad de retrieval y reduce memory sprawl vs. tags libres. | Abierto |
| P-012 | Retry engine multi-category con exponential backoff, credential rotation y fallback model | jan | Patrón de resiliencia crítico para producción — sin esto, el primer error de red tumba el agente. | Abierto |
| P-013 | Background query protection: queries de utilidad no retrien en cascadas de capacidad | jan | Reduce amplificación de carga en servicios saturados, protegiendo el servicio upstream. | Abierto |
| P-014 | Prompt commands: capacidades complejas expuestas como prompts multi-fase inyectados al agente | jan | El patrón más eficiente encontrado: 0 código de ejecución, máximo leverage del LLM. | Abierto |
| P-015 | Token estimation multi-strategy con bytes-per-token por file type y per-block counting | jan | Prerequisito para context management, compactación y budget de tool results. | Abierto |
| P-016 | Taxonomía de errores con mensajes user-friendly y acciones sugeridas | jan | Mejora experiencia del operador y habilita retry inteligente por categoría de error. | Abierto |

## Hallazgos por bloque

| Bloque | Estado | Decisión dominante | Resumen |
| --- | --- | --- | --- |
| 0 | Completado | `Adaptar` | La correspondencia entre dominios es real, pero la integración debe ser selectiva. |
| 1 | Completado | `Adaptar` | jan aporta patrones de runtime y contexto; su bootstrap completo no conviene migrarlo. |
| 2 | Completado | `Adaptar` | jan aporta patrones avanzados de loop conversacional, task orchestration y concurrencia; no conviene portar su runtime conversacional completo. |
| 3 | Completado | `Adaptar` | jan tiene el sistema de tools, permisos y seguridad shell más completo encontrado — AgentOS debe adoptar clasificación de riesgo y pipeline de validación, no las 5000+ líneas de validación shell ni rendering. |
| 4 | Completado | `Adaptar` | jan tiene persistencia de conversación de grado producción, resume completo, budget de tool results y memoria tipada — AgentOS debe adoptar JSONL persistence, resume básico, budget simplificado y taxonomía de memoria. |
| 5 | Completado | `Adaptar` | jan tiene retry engine production-grade (10+ error categories, fast mode, persistent retry), multi-provider con fallback, y MCP completo (500K+) — AgentOS debe adoptar retry con resiliencia y observabilidad de requests, postergar MCP. |
| 6 | Completado | `Adaptar` | jan tiene 101 slash commands con patrón "prompt command" que inyecta instrucciones sofisticadas al agente — AgentOS debe adoptar prompt templates y diagnósticos expandidos, no CLI ni VCS integration. |
| 7 | Completado | `Adaptar` | jan tiene token estimation multi-strategy, analytics completo (135K), taxonomía de errores rica y config multi-scope — AgentOS debe adoptar token estimation, error taxonomy y event logging, postergar analytics y feature flags. |
| 8 | Excluido | - | Excluido por decisión del usuario. |

## Backlog consolidado de integración

| ID | Propuesta | Origen | Tipo | Prioridad |
| --- | --- | --- | --- | --- |
| B-001 | Diseñar un bootstrap interno desacoplado de la API para soportar más de una superficie de entrada | Bloque 1 | ADR / refactor | Alta |
| B-002 | Introducir un proveedor de contexto de ejecución y sesión para prompts, traces y estado operativo | Bloque 1 | feature | Alta |
| B-003 | Mantener el principio de estado global mínimo y prohibir un store global equivalente al de jan | Bloque 1 | guardrail arquitectónico | Alta |
| B-004 | Incorporar un contrato explícito de subtask/task runtime con estados, progreso y cancelación | Bloque 2 | feature | Alta |
| B-005 | Evaluar ejecución concurrente segura de tools por clases de riesgo en el orquestador | Bloque 2 | ADR / feature | Media |
| B-006 | Añadir límites operativos más ricos por turnos, presupuesto y cancelación sin convertir AgentOS en un REPL | Bloque 2 | feature | Media |
| B-007 | Enriquecer `BaseTool` con `is_read_only`, `is_concurrent_safe`, `is_destructive`, `validate_input()`, `check_permissions()` y factory con defaults fail-closed | Bloque 3 | feature / refactor | Alta |
| B-008 | Crear `ToolExecutionContext` lean (request, session, permissions, abort, workspace) sin dependencia de UI | Bloque 3 | feature | Alta |
| B-009 | Extender `PermissionValidator` con deny rules, wildcards y matching por input/contenido | Bloque 3 | feature | Alta |
| B-010 | Adoptar pipeline de validación por fases: `validate_input()` → `check_permissions()` → `execute()` | Bloque 3 | feature | Alta |
| B-011 | Preparar ADR para "tool security classification" definiendo qué significa cada clasificación y cómo se consume | Bloque 3 | ADR | Alta |
| B-012 | Estudiar seguridad shell de jan como referencia para capas adicionales en `run_command` (AST, path validation, read-only detection) | Bloque 3 | investigación | Media |
| B-013 | Diseñar un `ConversationStore` con persistencia JSONL append-only, session_id indexado, y write-behind buffering | Bloque 4 | feature | Alta |
| B-014 | Implementar session resume básico: carga de última conversación + restauración de estado de agente | Bloque 4 | feature | Alta |
| B-015 | Implementar tool result budget simplificado: threshold per-tool + preview + persistencia a disco | Bloque 4 | feature | Alta |
| B-016 | Enriquecer `MemoryItem` con taxonomía tipada (user/feedback/project/reference), scope, timestamps y source_session_id | Bloque 4 | feature / refactor | Media |
| B-017 | Agregar instrucciones de memoria al system prompt (qué guardar, qué no, cuándo acceder) adaptadas a contexto API/headless | Bloque 4 | feature | Media |
| B-018 | Agregar TTL y eviction a `ShortTermMemory` y cleanup de datos antiguos a `WorkingStateStore` | Bloque 4 | deuda técnica | Baja |
| B-019 | Implementar `RetryEngine` con exponential backoff, jitter, categorías de error, credential refresh hook, y max_tokens adjustment | Bloque 5 | feature | Alta |
| B-020 | Agregar fallback model: config primary + fallback con threshold de failures antes de switch | Bloque 5 | feature | Alta |
| B-021 | Agregar session ID (`x-session-id`) y request ID (`x-request-id`) tracking en requests a LLM providers | Bloque 5 | feature | Media |
| B-022 | Implementar background query protection: queries de utilidad no retrien en 429/529 | Bloque 5 | feature | Media |
| B-023 | Evaluar adopción de MCP protocol como mecanismo de extensión de tools vía servidores externos (ADR) | Bloque 5 | ADR / investigación | Baja |
| B-024 | Implementar `PromptTemplateRegistry` para exponer capacidades complejas como prompt templates invocables via task_type | Bloque 6 | feature | Media |
| B-025 | Expandir `/healthz` a diagnósticos completos: checks de LLM provider, memoria, tools, permisos, y configuración | Bloque 6 | feature | Media |
| B-026 | Agregar tracking de métricas por sesión: tokens, costos, duración, tools usadas — endpoint `GET /session/{id}/metrics` | Bloque 6 | feature | Baja |
| B-027 | Implementar `estimate_tokens(content, file_type)` con bytes-per-token ratio por tipo de archivo y per-block counting | Bloque 7 | feature | Alta |
| B-028 | Crear `AgentOSError` hierarchy: `LLMError`, `ToolError`, `ConfigError` con `user_message` y `suggested_action` | Bloque 7 | feature / refactor | Alta |
| B-029 | Agregar event logging básico: `log_event(event_type, metadata)` para task lifecycle (start, tool_use, end) como structured log entries | Bloque 7 | feature | Media |

## Riesgos estratégicos

| ID | Riesgo | Mitigación inicial |
| --- | --- | --- |
| R-001 | Sobreintegrar complejidad de un producto CLI/REPL en un runtime API pequeño | Integrar por capacidades, no por copia de subsistemas |
| R-002 | Debilitar el modelo de mínimo privilegio de AgentOS al importar ergonomía operativa de jan | Conservar permiso declarativo como base y evaluar extensiones en ADRs |
| R-003 | Introducir concurrencia de tools o subtareas sin un modelo explícito de aislamiento y cancelación | Agregar primero contratos y límites, luego paralelismo |
| R-004 | Enriquecer el contrato de tool sin mantener backward compatibility con tools existentes | Usar factory pattern con defaults — tools existentes siguen funcionando sin cambios |
| R-005 | Distribuir lógica de permisos entre tools individuales fragmentando la superficie de seguridad | Centralizar validación general en `PermissionValidator` y permitir solo refinamiento en tools |
| R-006 | Sin persistencia de conversación, AgentOS no puede ofrecer audit trail, debugging post-mortem ni resume de sesiones | Implementar `ConversationStore` como primera prioridad del bloque 4 |
| R-007 | Sin budget de tool results, tools con output masivo pueden causar OOM o exceder límites de tokens | Implementar threshold + preview como segunda prioridad del bloque 4 |
| R-008 | Sin retry con resiliencia, AgentOS falla en el primer error de red o rate limit — inaceptable en producción | Implementar `RetryEngine` como primera prioridad del bloque 5 |
