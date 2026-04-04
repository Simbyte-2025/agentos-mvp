# Bloque 4. Sesión, memoria, historial y persistencia

## Objetivo funcional del bloque

Analizar los sistemas de sesión, memoria, historial y persistencia de estado de `jan-research-main` — cómo almacena, recupera, persiste y gestiona conversaciones, tool results y memoria del agente — y contrastarlo con el modelo de memoria de AgentOS para identificar patrones reutilizables, brechas de capacidad y riesgos de integración.

## Delimitación y mapa de archivos

| Archivo o área | Responsabilidad | Tamaño | Relevancia |
| --- | --- | --- | --- |
| `jan/src/history.ts` (465 líneas) | Historial de prompts del usuario: add, get, undo, flush. Persistencia a JSONL con locking, paste store, dedup por proyecto/sesión | ~14K | Alta |
| `jan/src/utils/sessionStorage.ts` (5106 líneas) | Mega-módulo: Project singleton, transcript persistence JSONL, write queues con batching, metadata caching, subagent/remote agent transcript management, session file materialization | ~180K | Núcleo |
| `jan/src/utils/sessionRestore.ts` (552 líneas) | Resume de sesión: worktree, agent context, file history, attribution, context collapse, coordinator mode, todo state | ~20K | Alta |
| `jan/src/utils/sessionState.ts` (151 líneas) | Estado de sesión: idle/running/requires_action, metadata listener, permission mode change, SDK event stream | ~5K | Media |
| `jan/src/utils/conversationRecovery.ts` (598 líneas) | Carga y deserialización de conversaciones: migración de legacy, detección de interrupciones, tool_use resolution, skill restoration | ~21K | Alta |
| `jan/src/utils/toolResultStorage.ts` (1041 líneas) | Persistencia de tool results grandes a disco: budget enforcement, content replacement state, preview generation, replacement re-apply | ~38K | Alta |
| `jan/src/memdir/memdir.ts` (508 líneas) | Sistema de memoria tipada: MEMORY.md entrypoint, index truncation, memory prompt building, team memory, daily log mode | ~21K | Alta |
| `jan/src/memdir/memoryTypes.ts` (272 líneas) | Taxonomía de memoria: user, feedback, project, reference. Frontmatter format, behavioral instructions | ~23K | Media |
| `agentos/memory/base.py` (40 líneas) | `MemoryItem`, `LongTermMemoryBackend` ABC | ~1K | Referencia |
| `agentos/memory/short_term.py` (20 líneas) | `ShortTermMemory`: deque por session_id | ~0.6K | Referencia |
| `agentos/memory/long_term.py` (86 líneas) | `LongTermMemory` con backend strategy: naive (token overlap) o chroma | ~3K | Referencia |
| `agentos/memory/working_state.py` (52 líneas) | `WorkingStateStore`: checkpoints SQLite | ~1.8K | Referencia |
| `agentos/memory/chroma.py` (154 líneas) | `ChromaMemoryBackend`: ChromaDB sin embeddings (MVP) | ~6K | Referencia |

**Total jan analizado: ~322K bytes (~7500 líneas)**
**Total AgentOS analizado: ~12K bytes (~352 líneas)**

## Arquitectura y flujo principal

### Sistema de sesión y persistencia de jan

jan tiene un sistema de persistencia sofisticado de grado producción:

#### 1. Historial de prompts (`history.ts`)
- **Persistencia**: JSONL append-only con file locking (via `proper-lockfile`)
- **Modelo write-behind**: Buffer en memoria (`pendingEntries`), flush async con retry exponencial, cleanup handler al cierre
- **Contenido pegado**: Hash + paste store externo para contenido grande, inline para contenido ≤1024 chars
- **Dedup**: Por proyecto + sesión, con skip de sesiones de verificación (tmux/Tungsten)
- **Undo**: `removeLastFromHistory()` con fast-path (pop de buffer) y slow-path (skip-set de timestamps para entradas ya flushed)

#### 2. Transcript persistence (`sessionStorage.ts` — 5106 líneas)
- **Project singleton**: Gestiona sesión, metadata, write queues, flush timer
- **Write queue**: Enqueue async → batch drain cada 100ms → `appendToFile` con mkdir-on-demand → 100MB max chunk
- **Transcript format**: JSONL con entradas tipadas (user, assistant, attachment, system, custom-title, tag, agent-name, worktree-state, etc.)
- **Metadata caching**: `currentSessionTitle`, `currentSessionTag`, `currentSessionAgentName`, `currentSessionMode`, `currentSessionWorktree`, etc. — re-appended al cierre para que `readLiteMetadata` los encuentre en el tail
- **Subagent transcripts**: Separate files bajo `{sessionId}/subagents/`
- **Remote agent metadata**: Sidecar JSON files para tareas CCR
- **Session file lifecycle**: Lazily materialized on first user/assistant message, tombstone on session end

#### 3. Session restore (`sessionRestore.ts`)
- **Full resume pipeline**: session ID setup → worktree cd → agent definition restore → cost state restore → mode persistence → context collapse restore → initial state computation
- **Fork support**: `--fork-session` creates new session with content replica
- **Worktree restore**: Process.chdir back into last worktree, with graceful fallback si el directorio fue eliminado

#### 4. Conversation recovery (`conversationRecovery.ts`)
- **Chain walk**: UUID-linked chain (parentUuid) para reconstruir conversación desde JSONL
- **Interruption detection**: 3-way (none, interrupted_prompt, interrupted_turn) con auto-continue
- **Legacy migration**: Transforma tipos de attachment antiguos
- **Skill restoration**: Re-hydrata skills desde snapshots de compactación

#### 5. Tool result persistence (`toolResultStorage.ts` — 1041 líneas)
- **Budget enforcement por mensaje**: Per-message aggregate budget (~200K chars default)
- **Content replacement state**: Decisiones persist across turns para prompt cache stability
- **3-phase partitioning**: mustReapply (re-apply cached) → frozen (don't touch) → fresh (eligible for replacement)
- **Largest-first replacement**: Ordena por tamaño descendente, reemplaza hasta estar dentro del budget
- **Preview generation**: 2KB preview con corte en newline boundary
- **Re-apply byte-identical**: El replacement cacheado se re-aplica 100% idéntico para preservar prefix cache

#### 6. Memory system (`memdir/`)
- **Modelo file-based**: MEMORY.md como index + topic files con YAML frontmatter
- **Taxonomía tipada**: 4 tipos (user, feedback, project, reference) con scopes (private/team)
- **Daily log mode** (KAIROS): Append-only log files por fecha, distilled nightly
- **Team memory**: Shared directory con scoping explícito
- **Index truncation**: 200 líneas max, 25KB max, con warning si se excede
- **Behavioral instructions**: Prompt engineering extenso para cuándo guardar, qué no guardar, cuándo acceder, y cómo verificar

### Sistema de memoria de AgentOS

AgentOS tiene un sistema de memoria funcional pero significativamente más simple:

#### 1. Short-term memory (`short_term.py`)
- **Modelo**: Deque por session_id con max_items configurable (default 10)
- **API**: `add(session_id, message)` / `get(session_id)`
- **Sin persistencia**: In-memory only

#### 2. Long-term memory (`long_term.py` + `base.py`)
- **Backend strategy**: `NaiveMemoryBackend` (token overlap) o `ChromaMemoryBackend`
- **LongTermMemoryBackend ABC**: `add(text, tags)` / `retrieve(query, top_k)`
- **Naive**: In-memory list con regex tokenization y overlap scoring
- **Chroma**: ChromaDB PersistentClient sin embeddings (MVP), token overlap scoring
- **Config**: `AGENTOS_LTM_BACKEND` env var

#### 3. Working state (`working_state.py`)
- **Checkpoints SQLite**: `(session_id, name, data_json, created_at)` con UPSERT
- **API**: `save_checkpoint()` / `load_checkpoint()`

## Interfaces, dependencias y acoplamientos

- **jan** tiene acoplamiento fuerte entre persistencia y UI (React state, REPL hooks, progress messages)
- **jan** depende de filesystem primitives (JSONL, lockfiles, mkdir) con zero dependency en databases
- **jan** tiene cadena UUID (`parentUuid`) para versioning de conversaciones — soporta branching, forking y sidechains
- **jan** tiene feature flags extensos (`bun:bundle`) para gating de capabilities (KAIROS, TEAMMEM, CONTEXT_COLLAPSE, BG_SESSIONS)
- **AgentOS** mantiene separación limpia entre memoria y el resto del sistema via ABC y backend strategy
- **AgentOS** tiene persistencia dual (SQLite para checkpoints, ChromaDB para LTM) sin coupling con ejecución

## Fortalezas y debilidades

### Fortalezas

- **jan** tiene un sistema de persistencia de grado producción: write-behind buffering, file locking, retry, cleanup handlers, chunk limits — nunca pierde datos
- **jan** maneja la complejidad de prompt cache con brillantez: content replacement state con 3-phase partitioning garantiza que las decisiones de reemplazo son estables turn-over-turn
- **jan** soporta resume completo: conversación, agent context, worktree, cost state, attribution, context collapse — se puede cerrar y reabrir sin pérdida
- **jan** clasifica memoria en una taxonomía cerrada (user/feedback/project/reference) que evita la "memory sprawl"
- **jan** maneja tool results grandes (~200K+ chars) con persistencia a disco + preview, en lugar de truncamiento
- **AgentOS** tiene una abstracción limpia de backend con strategy pattern
- **AgentOS** tiene checkpoints con SQLite — un patrón sólido para estado persistente
- **AgentOS** separación total entre capas de memoria (short/long/working)

### Debilidades

- **jan** tiene un módulo de 5106 líneas (`sessionStorage.ts`) que es un god-module de facto
- **jan** mezcla metadata de sesión, transcripción, analytics y file management en un solo singleton
- **jan** tiene acoplamiento con React state y hooks (useCanUseTool, REPL, progress) que impide extracción limpia
- **AgentOS** no tiene historial de conversaciones persistente — la sesión muere cuando el proceso termina
- **AgentOS** no tiene mecanismo de resume ni recovery
- **AgentOS** no maneja tool results grandes (sin persistence, sin budget)
- **AgentOS** no tiene taxonomía de memoria ni behavioral instructions para el modelo
- **AgentOS** carece de write-behind buffering ni manejo de concurrencia en persistencia
- **AgentOS** ChromaDB sin embeddings es funcionalmente equivalente al NaiveBackend + overhead de infraestructura

## Riesgos técnicos y de seguridad

- Importar sessionStorage.ts requeriría separar ~5100 líneas en al menos 5-7 módulos desacoplados
- El modelo de chain-walk por UUID es poderoso pero introduce complejidad significativa para debugging
- El mecanismo de prompt cache stability (content replacement) es frágil ante cambios en formato de preview o serialización
- Sin persistencia de conversación, AgentOS no puede ofrecer resume, audit trail, ni debugging post-mortem de sesiones
- Sin budget para tool results, AgentOS es vulnerable a OOM con tools que produzcan salida masiva

## Deuda técnica detectada

- `ShortTermMemory` no tiene TTL ni eviction — crece sin límite por sesión
- `WorkingStateStore` no tiene cleanup ni rotation de datos antiguos
- `ChromaMemoryBackend.retrieve()` fetches ALL documents para scoring — O(n) retrieval
- No hay historial de conversación persistente
- No hay mecanismo para tool result persistence ni budget management
- No hay taxonomía de memoria ni metadata (tipo, scope, timestamps)
- No hay support para resume/recovery de sesiones

## Contraste con AgentOS

| Capacidad en jan | Equivalente en AgentOS | Brecha | Decisión |
| --- | --- | --- | --- |
| Historial de prompts JSONL con locking, dedup, paste store, undo | No existe | Brecha alta | `Adaptar` |
| Transcript JSONL con write-behind, batching, metadata caching | No existe | Brecha máxima | `Adaptar` |
| Full session resume (conversation, agent, worktree, cost, attribution) | No existe | Brecha máxima | `Adaptar` |
| Conversation recovery con chain-walk UUID, interruption detection | No existe | Brecha alta | `Adaptar` |
| Tool result persistence con budget enforcement y cache stability | No existe | Brecha alta | `Adoptar` |
| Memoria tipada con taxonomía (user/feedback/project/reference) y frontmatter | `MemoryItem(text, tags)` — sin taxonomía | Brecha moderada | `Adaptar` |
| Daily log mode (KAIROS) para sesiones longevas | No existe | Brecha baja (no prioridad) | `Postergar` |
| Team memory con scoping private/team | No existe | Brecha baja (no prioridad) | `Postergar` |
| Behavioral instructions para el modelo sobre cuándo/cómo usar memoria | No existe | Brecha moderada | `Adaptar` |
| Content replacement state con 3-phase stability | No existe | Brecha alta | `Postergar` |
| Short-term memory (deque por session) | `ShortTermMemory` — similar | Brecha baja | `Retener` |
| Long-term memory con backend strategy | `LongTermMemory` con ChromaDB/naive | Brecha baja en pattern, alta en producción | `Evolucionar` |
| Checkpoints persistentes | `WorkingStateStore` con SQLite | Brecha baja | `Retener` |
| Subagent transcript management | No existe | Brecha media | `Postergar` |
| Session metadata (title, tag, agent, worktree, mode) | No existe | Brecha moderada | `Adaptar` |

## Evaluación de utilidad para integración

| Capacidad | Veredicto | Esfuerzo | Riesgo | Recomendación |
| --- | --- | --- | --- | --- |
| Implementar persistencia de conversación JSONL | reusable with refactor | Alto | Medio | Diseñar un `ConversationStore` con append-only JSONL (pattern de jan) pero sin metadata de REPL |
| Implementar session resume básico | reusable with refactor | Alto | Medio | Derivar de `sessionRestore.ts` simplificado: conversation load + agent state restore |
| Implementar tool result budget | reusable with refactor | Medio | Bajo | Adoptar el patrón de persistence threshold + preview, sin content replacement state |
| Agregar taxonomía a `MemoryItem` | reusable directly | Bajo | Bajo | Agregar `type: Literal["user","feedback","project","reference"]`, `scope`, `timestamps` |
| Agregar behavioral instructions a prompts | useful as reference only | Bajo | Bajo | Adaptar los prompt sections de `memoryTypes.ts` al system prompt de AgentOS |
| Implementar prompt history | useful as reference only | Medio | Bajo | Diseñar para API (no REPL) pero mantener dedup y undo pattern |
| Adoptar write-behind buffering para persistencia | reusable with refactor | Medio | Medio | Útil para producción — evitar escritura síncrona en cada turn |
| Portar content replacement state (3-phase) | not recommended for AgentOS | Alto | Alto | Complejidad excesiva para MVP — el budget básico es suficiente |
| Portar chain-walk UUID y branching | not recommended for AgentOS | Alto | Alto | Demasiada complejidad para el modelo de sesión lineal de AgentOS |
| Portar subagent transcript management | not recommended for AgentOS (ahora) | Alto | Alto | Requiere el subsistema de subagentes primero |
| Agregar embeddings a ChromaDB | not related to jan audit | Medio | Bajo | Evolución natural del backend — no requiere patrones de jan |

## Recomendación accionable

1. **Diseñar un `ConversationStore`**: Módulo lean de ~200 líneas que guarde la conversación en formato append-only JSONL con session_id indexado. Sin singleton, sin metadata de UI. Pattern de jan (JSONL + lockfile) pero scope de AgentOS.

2. **Implementar session resume básico**: Un `SessionRestorer` que cargue la última conversación y restaure el estado del agente. Sin cadena UUID — modelo lineal con timestamping. Suficiente para `agentctl session resume`.

3. **Adoptar tool result budget simplificado**: Threshold por tool + preview + disco. Sin content replacement state. Per-tool de jan pero sin per-message aggregate.

4. **Enriquecer `MemoryItem`**: Agregar `type`, `scope`, `created_at`, `updated_at`, `source_session_id`. Adoptar la taxonomía cerrada de 4 tipos de jan.

5. **Agregar instrucciones de memoria al system prompt**: Adaptar las secciones de `memoryTypes.ts` (what to save, what NOT to save, when to access) al contexto headless/API de AgentOS.

6. **Evitar**: Chain-walk UUID, content replacement state (3-phase), subagent transcripts, session metadata UI, daily log mode.

## Informe técnico ejecutivo

### Resumen ejecutivo

El Bloque 4 revela la segunda brecha más significativa entre jan y AgentOS. jan tiene un sistema de persistencia de grado producción con ~8000 líneas que cubre historial de prompts (JSONL con locking y undo), transcripciones de conversación con write-behind buffering, resume completo de sesiones (agente, worktree, costs, attribution), recovery de conversaciones interrumpidas, budget management de tool results con prompt cache stability, y un sistema de memoria tipada con behavioral instructions para el modelo. AgentOS tiene ~350 líneas que cubren memoria short-term (deque), long-term (ChromaDB sin embeddings), y checkpoints (SQLite) — pero sin persistencia de conversación, sin resume, sin budget de resultados, y sin taxonomía de memoria.

### Utilidad concreta para AgentOS

La utilidad es alta en tres áreas:
1. **Persistencia de conversación JSONL** — habilita resume, audit trail, debugging post-mortem (alto esfuerzo, alto valor)
2. **Tool result budget** — previene OOM y optimiza token usage (medio esfuerzo, alto valor)  
3. **Taxonomía de memoria** — mejora la calidad de retrieval y evita memory sprawl (bajo esfuerzo, medio valor)

No conviene portar: el god-module de 5106 líneas, chain-walk UUID, content replacement state, metadata de UI/REPL, daily log mode, team memory scoping.

### Decisión recomendada

`Adaptar`

### Esfuerzo estimado

`Alto` (requiere nuevo módulo de persistencia + resume + budget + cambios en memory)

### Riesgo estimado

`Medio` (los cambios son extensiones, pero la persistencia de conversación toca el core loop)

### Prioridad sugerida para roadmap

`Alta` — la persistencia de conversación es prerequisito para observabilidad, debugging, audit trail, y resume. El budget de tool results es prerequisito para tools que producen salida grande.
