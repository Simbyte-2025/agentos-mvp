# Bloque 6. CLI, comandos operativos y experiencia de uso

## Objetivo funcional del bloque

Analizar la interfaz de línea de comandos, los slash commands, comandos operativos y la experiencia de uso de `jan-research-main` — cómo expone capacidades al usuario, gestiona configuración, provee diagnósticos, y soporta extensión — y contrastarlo con la superficie operativa de AgentOS.

## Delimitación y mapa de archivos

| Archivo o área | Responsabilidad | Tamaño | Relevancia |
| --- | --- | --- | --- |
| `jan/src/commands/` (86 dirs + 15 files) | 101 slash commands cobriendo toda la operación | ~400K+ | Núcleo |
| `jan/src/commands/init.ts` (257 líneas) | Comando `/init` para inicializar CLAUDE.md con análisis automático del codebase | ~21K | Alta |
| `jan/src/commands/doctor/` | Diagnósticos de salud del sistema | ~8K | Alta |
| `jan/src/commands/config/` | Gestión de configuración | Variable | Alta |
| `jan/src/commands/memory/` | Operaciones de memoria | Variable | Media |
| `jan/src/commands/mcp/` | Gestión de MCP servers | Variable | Media |
| `jan/src/commands/compact/` | Compactación de contexto | Variable | Alta |
| `jan/src/commands/resume/` | Resume de sesiones | Variable | Alta |
| `jan/src/commands/permissions/` | Gestión de permisos | Variable | Alta |
| `jan/src/commands/model/` | Selección de modelo | Variable | Media |
| `jan/src/utils/slashCommandParsing.ts` (61 líneas) | Parser de slash commands con soporte MCP | ~1.4K | Media |
| `agentos/api/main.py` (224 líneas) | FastAPI server: healthz, /run, /builder/scaffold, /builder/apply | ~8.5K | Referencia |

## Arquitectura y flujo principal

### Sistema de comandos de jan

jan expone un sistema de slash commands masivo con 101 directorios/archivos en `src/commands/`:

#### 1. Taxonomía de comandos (101 items)

**Comandos operativos de sesión:**
- `/init` — Inicializa CLAUDE.md con análisis automático del codebase
- `/resume` — Resume sesión anterior
- `/compact` — Compacta contexto cuando se acerca al límite de tokens
- `/clear` — Limpia sesión y caches
- `/session` — Gestión de sesiones
- `/exit` — Salida limpia

**Comandos de configuración:**
- `/config` — Gestión de configuración
- `/model` — Selección de modelo
- `/permissions` — Gestión de permisos
- `/theme` — Tema visual
- `/keybindings` — Atajos de teclado
- `/output-style` — Estilo de output
- `/privacy-settings` — Configuración de privacidad
- `/env` — Variables de entorno

**Comandos de desarrollo:**
- `/diff` — Muestra diff de cambios
- `/commit` — Commit de cambios
- `/commit-push-pr` — Commit, push y PR en un solo comando
- `/review` — Code review
- `/security-review` — Review de seguridad
- `/branch` — Gestión de branches
- `/rewind` — Revert a estado anterior

**Comandos de integración:**
- `/mcp` — Gestión de MCP servers
- `/plugin` — Gestión de plugins
- `/hooks` — Gestión de hooks
- `/install` — Instalación de dependencias
- `/install-github-app` — Instalar GitHub app
- `/install-slack-app` — Instalar Slack app

**Comandos de observabilidad:**
- `/doctor` — Diagnósticos de salud
- `/status` — Estado del sistema
- `/cost` — Costos de la sesión
- `/usage` — Uso de recursos
- `/stats` — Estadísticas
- `/context` — Información de contexto

**Comandos de memoria:**
- `/memory` — Operaciones de memoria
- `/skills` — Gestión de skills

**Otros:**
- `/help` — Ayuda
- `/version` — Versión
- `/feedback` — Enviar feedback
- `/login`, `/logout` — Autenticación
- `/ultraplan` — Planeación avanzada (~67K, el más grande)
- `/insights` — Insights del codebase (~116K)

#### 2. Pattern de comando

Cada comando sigue un contrato uniforme (`Command`):
```typescript
{
  type: 'prompt' | 'local' | 'local-jsx',
  name: string,
  description: string,
  isEnabled?: (context) => boolean,
  getPromptForCommand?: () => ContentBlock[],  // para type 'prompt'
  call?: (onDone, context, args) => Promise<JSX|void>,  // para type 'local-jsx'
}
```

- **Prompt commands**: Inyectan un prompt al agente (ej: `/init`, `/review`)
- **Local commands**: Ejecutan lógica directa sin LLM (ej: `/clear`, `/exit`)
- **Local-JSX commands**: Ejecutan lógica con rendering React (ej: `/doctor`, `/config`)

#### 3. Slash command parsing (`slashCommandParsing.ts`)
- Parser simple: `/command args...`
- Soporte MCP: `/mcp:tool (MCP) args...`
- Validación de formato

#### 4. `/init` como meta-comando (257 líneas de prompt)
- **8 fases automáticas**: Ask → Explore → Interview → Write CLAUDE.md → Write CLAUDE.local.md → Create skills → Suggest optimizations → Summary
- **El prompt más rico encontrado en toda la auditoría**: describe un workflow completo de análisis, entrevistas al usuario, y generación de artefactos
- **Patrón "command as sophisticated prompt"**: el comando no ejecuta código, inyecta un prompt de 257 líneas que guía al agente

### Superficie operativa de AgentOS

AgentOS expone su funcionalidad via FastAPI REST API:

#### Endpoints
- `GET /healthz` — Health check con lista de agentes y tools
- `POST /run` — Ejecutar tarea (task, session_id, user_id)
- `POST /builder/scaffold` — Generar scaffold de código
- `POST /builder/apply` — Aplicar archivos generados al filesystem

#### Características
- API key auth via `require_api_key`
- Bootstrap desde YAML config (`agents.yaml`, `tools.yaml`, `profiles.yaml`)
- Feature flags via environment variables (`AGENTOS_ORCHESTRATOR`, `AGENTOS_LLM_PROVIDER`)
- Sin slash commands
- Sin CLI interactivo
- Sin sistema de comandos extensible

## Contraste con AgentOS

| Capacidad en jan | Equivalente en AgentOS | Brecha | Decisión |
| --- | --- | --- | --- |
| 101 slash commands categorizados | 4 REST endpoints | Brecha máxima en superficie, pero brechas estratégicas son selectivas | Ver notas |
| Sistema de comandos tipado (prompt/local/local-jsx) | No existe | Brecha alta | `Adaptar` |
| `/init` con análisis automático del codebase | No existe | Brecha alta | `Adaptar` (como capability, no como CLI) |
| `/doctor` para diagnósticos de salud | `GET /healthz` (básico) | Brecha moderada | `Adaptar` |
| `/compact` para compactación de contexto | No existe | Brecha alta | `Adaptar` |
| `/resume` para resume de sesiones | No existe (cubierto en Bloque 4) | Brecha alta | Ya registrado (B-014) |
| `/config` para gestión de configuración | Env vars + YAML files | Brecha moderada | `Retener` |
| `/diff`, `/commit`, `/review` para VCS | No existe (fuera de scope de API) | Brecha baja | `Postergar` |
| `/mcp`, `/plugin`, `/hooks` para extensión | No existe | Brecha alta | `Postergar` |
| `/cost`, `/usage`, `/stats` para observabilidad | No existe | Brecha moderada | `Adaptar` |
| Slash command parsing con extensión MCP | No existe | Brecha baja (no prioridad) | `Postergar` |
| Prompt commands (comando como prompt sofisticado) | No existe | Brecha alta | `Adaptar` |

## Evaluación de utilidad para integración

| Capacidad | Veredicto | Esfuerzo | Riesgo | Recomendación |
| --- | --- | --- | --- | --- |
| Sistema de comandos tipado como extension point | reusable with refactor | Medio | Bajo | Diseñar un `CommandRegistry` con tipos (prompt-inject, direct-execute, diagnostic) que permita extensión |
| Pattern "prompt command" | reusable directly | Bajo | Bajo | Implementar "task templates" que inyecten prompts sofisticados como el `/init` de jan |
| Diagnósticos de salud expandidos | useful as reference only | Bajo | Bajo | Extender `/healthz` con checks de providers, memory, tools, permissions |
| Compactación de contexto | reusable with refactor | Medio | Medio | Útil cuando AgentOS tenga sesiones largas — no urgente para MVP |
| Observabilidad de costos y uso | useful as reference only | Medio | Bajo | Tracking de tokens, costos, y duración por sesión |
| VCS commands (diff, commit, review) | not recommended for AgentOS | Alto | Alto | Fuera del scope de un runtime API — dejar como tools |
| Extensión via plugins/hooks | not recommended for AgentOS (ahora) | Alto | Alto | Premature — estabilizar el core primero |

## Recomendación accionable

1. **Diseñar un `CommandRegistry`**: Abstracción ligera para registrar "capabilities" tipadas que pueden invocarse vía API, prompt injection, o directamente. No necesita ser CLI — puede ser un `POST /run` con `task_type: "init"` que active un prompt template.

2. **Implementar "prompt templates" como commands**: El patrón más valioso de jan es que `/init` es realmente un prompt de 257 líneas. AgentOS puede tener un mapeo `task_type → prompt_template` que inyecte instrucciones sofisticadas al agente sin código adicional.

3. **Expandir healthz a diagnostics**: Agregar checks de conectividad a LLM provider, estado de memoria, estado de tools, validez de configuración.

4. **Agregar tracking de métricas por sesión**: Tokens consumidos, costos estimados, duración, tools usadas — endpoints `GET /session/{id}/metrics`.

5. **Postergar**: VCS commands, plugins/hooks, MCP commands, CLI interactivo, slash command parsing.

## Informe técnico ejecutivo

### Resumen ejecutivo

El Bloque 6 revela que jan tiene una superficie operativa masiva (101 slash commands) que cubre todo desde inicialización de proyectos hasta VCS, extensiones, diagnósticos y observabilidad. El patrón más valioso no es la cantidad de comandos sino su tipología: los "prompt commands" que inyectan prompts sofisticados al agente (como `/init` con 257 líneas de instrucciones multi-fase) representan un mecanismo potente para exponer capacidades complejas sin código adicional. AgentOS tiene 4 endpoints REST que cubren funcionalidad básica pero carece de un sistema extensible de commands, prompt templates, diagnósticos avanzados, y tracking de métricas.

### Utilidad concreta para AgentOS

La utilidad es moderada-alta en dos patrones:
1. **Prompt templates como commands** — el patrón `/init` de inyectar prompts multi-fase es directamente aplicable a AgentOS via `task_type → prompt_template` (bajo esfuerzo, alto valor)
2. **Diagnósticos expandidos** — extender healthz con checks de providers, memoria, tools y config (bajo esfuerzo, medio valor)

No conviene portar: los 101 slash commands, CLI interactivo, VCS integration, plugin system, slash command parsing.

### Decisión recomendada

`Adaptar`

### Esfuerzo estimado

`Bajo-Medio`

### Riesgo estimado

`Bajo`

### Prioridad sugerida para roadmap

`Media` — los prompt templates son alto-valor pero el sistema actual de `/run` ya funciona. Los diagnósticos son importantes para operación pero no bloquean la funcionalidad.
