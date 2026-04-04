# Bloque 5. Bridge remoto, transporte e integración externa

## Objetivo funcional del bloque

Analizar los sistemas de transporte, bridge remoto, integración con proveedores de LLM, y el protocolo MCP de `jan-research-main` — cómo se comunica con APIs externas, gestiona multi-provider, implementa retry con resiliencia, y soporta extensión vía MCP — y contrastarlo con la capa de integración de AgentOS.

## Delimitación y mapa de archivos

| Archivo o área | Responsabilidad | Tamaño | Relevancia |
| --- | --- | --- | --- |
| `jan/src/services/api/client.ts` (390 líneas) | Factory de cliente Anthropic multi-provider: Direct, Bedrock, Foundry, Vertex. Custom headers, OAuth, proxy, session IDs | ~16K | Núcleo |
| `jan/src/services/api/withRetry.ts` (823 líneas) | Retry engine con exponential backoff, fast mode fallback, 529 handling, persistent retry, credential refresh, max tokens adjustment | ~28K | Alta |
| `jan/src/services/api/errors.ts` (~42K) | Error taxonomy, rate limit messages, error formatting | ~42K | Media |
| `jan/src/services/api/sessionIngress.ts` (515 líneas) | Remote session persistence: append log via JWT, optimistic concurrency (Last-Uuid), sequential writes, teleport events API | ~17K | Alta |
| `jan/src/services/api/claude.ts` (~126K) | Core query engine: streaming, message normalization, prompt assembly, tool execution loop | ~126K | Referencia |
| `jan/src/services/api/promptCacheBreakDetection.ts` (~26K) | Prompt cache break analysis and mitigation | ~26K | Referencia |
| `jan/src/services/mcp/` (23 archivos, ~500K+) | MCP protocol: client, config, auth (88K), connection manager, transports (stdio, SSE, HTTP, WS, SDK), channel permissions, elicitation, types | ~500K | Alta |
| `jan/src/services/mcp/types.ts` (259 líneas) | MCP type system: config schemas (Zod), transport types, server connection states, CLI state | ~7K | Alta |
| `agentos/llm/` | Provider abstraction, prompt building | Variable | Referencia |
| `agentos/integrations/` | External integrations | Variable | Referencia |
| `agentos/api/` | FastAPI endpoints | Variable | Referencia |

## Arquitectura y flujo principal

### Sistema de transporte de jan

jan tiene un sistema de transporte multi-layer sofisticado:

#### 1. Multi-provider client factory (`client.ts`)
- **4 proveedores**: Anthropic Direct, AWS Bedrock, Google Vertex, Azure Foundry
- **Auth strategies**: API key, OAuth tokens, AWS credentials (STS refresh), GCP credentials, Azure AD (DefaultAzureCredential)
- **Session tracking**: `x-claude-code-session-id` en cada request
- **Proxy support**: Custom fetch override con proxy options
- **Custom headers**: Soporte de `ANTHROPIC_CUSTOM_HEADERS` env var
- **Region management**: Per-model region override (Vertex) y per-type region override (Bedrock)
- **Client-side request IDs**: UUID per request para correlación con server logs en timeouts

#### 2. Retry engine (`withRetry.ts`)
- **AsyncGenerator pattern**: Yield de `SystemAPIErrorMessage` durante waits para UI feedback
- **10+ error categories**: 529 (overload), 429 (rate limit), 401 (auth), 403 (token revoked), 400 (context overflow), 408 (timeout), 409 (conflict), ECONNRESET, CredentialsProviderError
- **Fast mode fallback**: Short retry → keep fast mode; long retry → cooldown a standard speed
- **Persistent retry mode** (unattended): Indefinite retry con 30s heartbeat yields, 5min max backoff, 6hr reset cap
- **Max tokens auto-adjustment**: Cuando context overflow → reduce max_tokens con safety buffer de 1000 tokens
- **Credential rotation**: Clear caches de AWS/GCP/OAuth y re-authenticate entre retries
- **529 fallback**: Después de 3 consecutive 529s → fallback a modelo alternativo (FallbackTriggeredError)
- **Background query protection**: Sources no-foreground no retrien 529 → evitar amplificación en cascadas de capacidad

#### 3. Session ingress (`sessionIngress.ts`)
- **Remote persistence**: Append entries via PUT con JWT auth
- **Optimistic concurrency**: `Last-Uuid` header para chain integrity
- **409 recovery**: Detecta conflictos, adopta server UUID, y retries
- **Sequential writes**: Per-session queue para prevenir race conditions
- **Teleport events**: Paginated API para sesiones remotas CCR v2

#### 4. MCP protocol (`services/mcp/`)
- **23 archivos, 500K+ bytes**: La implementación MCP más completa encontrada
- **8 transport types**: stdio, SSE, SSE-IDE, HTTP, WebSocket, WS-IDE, SDK, claude.ai-proxy
- **Config scopes**: local, user, project, dynamic, enterprise, claudeai, managed
- **Auth**: OAuth2 completo (88K en `auth.ts`), XAA (Cross-App Access), header helpers, token refresh
- **Connection management**: Pending → connected → failed → needs-auth → disabled states
- **Channel permissions**: Allowlist, per-channel permission evaluation
- **Elicitation handler**: Interactive prompts from MCP servers

### Sistema de integración de AgentOS

AgentOS tiene una capa de integración funcional pero más simple:

- **LLM provider**: Abstracción con `BaseLLM` y provider registry (OpenAI, Claude, etc.)
- **API**: FastAPI endpoints para REST
- **Integrations**: Módulo de integración externa básico
- **Sin MCP**: No hay soporte de protocolo MCP
- **Sin multi-provider LLM client**: El provider se selecciona una vez, sin fallback

## Interfaces, dependencias y acoplamientos

- **jan** acopla el retry engine con UI (yield de SystemAPIErrorMessage), analytics, y feature flags
- **jan** tiene auth distribuida: OAuth en `client.ts`, JWT en `sessionIngress.ts`, OAuth2 en MCP `auth.ts`
- **jan** depende de `@anthropic-ai/sdk` para Direct, Bedrock, Foundry, Vertex — 4 SDKs
- **jan** tiene 88K bytes solo en MCP auth (`auth.ts`) — más que todo el módulo LLM de AgentOS
- **AgentOS** mantiene separación limpia entre provider, API y herramientas
- **AgentOS** no tiene coupling entre retry logic y UI

## Fortalezas y debilidades

### Fortalezas

- **jan** tiene el retry engine más completo encontrado: handles 10+ error categories, fast mode fallback, persistent retry, credential rotation, context overflow recovery, y 529 cascade protection
- **jan** soporta 4 cloud providers con auth strategy por provider — true multi-cloud
- **jan** tiene implementación MCP production-grade con 8 transports y OAuth completo
- **jan** implementa optimistic concurrency para remote session persistence — production-ready para distributed environments
- **AgentOS** tiene API REST limpia con FastAPI
- **AgentOS** mantiene la complejidad del provider LLM contenida

### Debilidades

- **jan** tiene 88K bytes en un solo archivo de auth MCP — unmaintainable
- **jan** acopla retry con UI (yield pattern) lo que impide extracción como librería
- **jan** es monolítico en su approach: cada componente sabe cómo hablar con múltiples servicios
- **AgentOS** no tiene retry con resiliencia avanzada (exponential backoff, credential rotation, fallback model)
- **AgentOS** no soporta MCP
- **AgentOS** no tiene multi-provider con fallback
- **AgentOS** no tiene remote session persistence

## Riesgos técnicos y de seguridad

- El retry engine de jan expone tokens de sesión y API keys en headers que se pueden loguear accidentalmente
- La auth MCP de 88K bytes es una superficie de ataque significativa si no se audita regularmente
- Sin retry con resiliencia, AgentOS falla en el primer error de red o rate limit
- Importar MCP completo de jan requeriría separar ~500K bytes en módulos independientes

## Deuda técnica detectada

- AgentOS no tiene retry engine con exponential backoff ni manejo de rate limits
- AgentOS no tiene fallback de modelo (primary → secondary)
- AgentOS no tiene MCP ni protocolo de extensión de tools via servidores externos
- AgentOS no tiene credential refresh automático (AWS STS, GCP, OAuth)
- AgentOS no tiene tracking de session ID en requests a LLM providers

## Contraste con AgentOS

| Capacidad en jan | Equivalente en AgentOS | Brecha | Decisión |
| --- | --- | --- | --- |
| Multi-provider client factory (Direct, Bedrock, Vertex, Foundry) | Provider registry simple (selección estática) | Brecha alta | `Adaptar` |
| Retry engine multi-category con fast mode, persistent retry, credential rotation | Sin retry avanzado | Brecha máxima | `Adoptar` |
| 529 cascade protection (background queries no retry) | No existe | Brecha alta | `Adoptar` |
| Max tokens auto-adjustment en context overflow | No existe | Brecha alta | `Adoptar` |
| Fallback model (primary → secondary after 3 consecutive 529s) | No existe | Brecha alta | `Adaptar` |
| Client-side request ID para correlación | No existe | Brecha moderada | `Adoptar` |
| MCP protocol completo (8 transports, OAuth, config scopes) | No existe | Brecha máxima | `Postergar` (ver notas) |
| Remote session persistence con optimistic concurrency | No existe | Brecha alta | `Postergar` |
| Credential rotation (AWS STS, GCP, OAuth token refresh) | No existe | Brecha moderada | `Adaptar` |
| Session ID tracking en requests | No existe | Brecha baja | `Adoptar` |
| Custom headers y proxy support | No existe | Brecha baja | `Adoptar` |

## Evaluación de utilidad para integración

| Capacidad | Veredicto | Esfuerzo | Riesgo | Recomendación |
| --- | --- | --- | --- | --- |
| Implementar retry engine con exponential backoff y categorías de error | reusable with refactor | Medio | Bajo | Extraer el patrón de `withRetry` sin AsyncGenerator yield — usar callback para logging |
| Agregar fallback model pattern | reusable directly | Bajo | Bajo | Configurar primary + fallback model con threshold de failures |
| Agregar max tokens auto-adjustment | reusable directly | Bajo | Bajo | Parsear error de context overflow y ajustar max_tokens |
| Agregar credential refresh automático | reusable with refactor | Medio | Medio | Implementar para los providers soportados por AgentOS |
| Agregar session ID tracking | reusable directly | Bajo | Bajo | Header `x-session-id` en cada request al LLM |
| Agregar client-side request IDs | reusable directly | Bajo | Bajo | UUID per request para correlación |
| Implementar MCP protocol | useful as reference only | Alto | Alto | El volumen (500K+) es excesivo para MVP; evaluar después de estabilizar el core |
| Portar session ingress remoto | not recommended for AgentOS (ahora) | Alto | Alto | Requiere infraestructura de backend primero |
| Portar fast mode / persistent retry | not recommended for AgentOS | Alto | Medio | Específico de Anthropic Max/Pro pricing — no aplica |

## Recomendación accionable

1. **Implementar `RetryEngine`**: Un módulo de ~150 líneas que implemente exponential backoff con jitter, categorías de error (retryable/non-retryable), credential refresh hook, y max_tokens adjustment. Pattern de `withRetry.ts` pero sin AsyncGenerator — usar callback para status reporting.

2. **Agregar fallback model**: Config `primary_model` + `fallback_model` en el provider, con threshold configurable de failures antes de switch.

3. **Agregar session ID y request ID tracking**: Header `x-session-id` y `x-request-id` (UUID) en cada request al LLM provider para observabilidad y debugging.

4. **Agregar background query protection**: Queries de utilidad (resumen, clasificación) no deben retrier en 429/529 — solo queries del usuario.

5. **Postergar MCP**: Demasiado volumen y complejidad para el estado actual de AgentOS. Registrar un ADR para evaluación futura cuando haya demand for external tool servers.

6. **Evitar**: Fast mode (Anthropic-specific), persistent retry (unattended mode), session ingress remoto, MCP auth de 88K bytes.

## Informe técnico ejecutivo

### Resumen ejecutivo

El Bloque 5 revela competencias de transporte y resiliencia que son fundamentales para operación en producción pero que AgentOS no posee. jan tiene un retry engine de 823 líneas que maneja 10+ categorías de error incluyendo fast mode fallback, persistent retry para sesiones desatendidas, cascade protection para queries de background, credential rotation automática, y max_tokens auto-adjustment. Además, soporta 4 cloud providers (Anthropic, Bedrock, Vertex, Foundry) con auth strategies dedicadas, y tiene la implementación MCP más completa encontrada con 500K+ bytes, 8 transports y OAuth2 completo. AgentOS tiene un provider registry simple sin retry avanzado, sin fallback, sin MCP, y sin credential refresh.

### Utilidad concreta para AgentOS

La utilidad es alta en dos áreas:
1. **Retry engine con resiliencia** — exponential backoff, error categorization, fallback model, max_tokens adjustment (medio esfuerzo, alto valor)
2. **Observabilidad de requests** — session IDs, request IDs, background query protection (bajo esfuerzo, medio valor)

No conviene portar: MCP protocol completo (500K+), fast mode, persistent retry, session ingress remoto, auth MCP de 88K bytes.

### Decisión recomendada

`Adaptar`

### Esfuerzo estimado

`Medio` (retry engine + fallback + observabilidad)

### Riesgo estimado

`Bajo` (extensiones al provider existente, no reescrituras)

### Prioridad sugerida para roadmap

`Alta` — la resiliencia de API es prerequisito para operación en producción y la observabilidad de requests es prerequisito para debugging eficiente.
