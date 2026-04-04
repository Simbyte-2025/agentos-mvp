# Bloque 1. Núcleo de ejecución y entrada del sistema

## Objetivo funcional del bloque

Analizar cómo `jan-research-main` inicializa el runtime, prepara estado global, arma contexto de ejecución y lanza la superficie principal; luego contrastarlo con el bootstrap actual de AgentOS para determinar qué patrones conviene incorporar sin perder simplicidad ni control.

## Delimitación y mapa de archivos

| Archivo o área | Responsabilidad | Relevancia |
| --- | --- | --- |
| `jan-research-main/src/main.tsx` | Punto de entrada principal, carga temprana, flags, wiring de servicios y sesión | Núcleo del arranque |
| `jan-research-main/src/setup.ts` | Preparación del entorno, cwd, worktrees, hooks, session setup y prerequisitos operativos | Núcleo operativo |
| `jan-research-main/src/bootstrap/state.ts` | Store global de estado del proceso/sesión | Contrato estructural crítico |
| `jan-research-main/src/context.ts` | Construcción de system/user context para conversaciones | Fuente de valor integrable |
| `jan-research-main/src/replLauncher.tsx` | Carga diferida de UI REPL | Secundario para AgentOS |
| `jan-research-main/src/projectOnboardingState.ts` | Estado de onboarding del proyecto | Bajo valor para AgentOS MVP |
| `agentos-mvp-main/agentos/api/main.py` | Bootstrap actual de AgentOS vía FastAPI | Referencia de contraste |

## Arquitectura y flujo principal

El arranque de `jan-research-main` es denso y altamente composicional. `main.tsx` dispara side effects tempranos, carga utilidades de seguridad/configuración/telemetría, prepara el estado de sesión y conecta múltiples subsistemas antes de delegar en la superficie final. `setup.ts` ejecuta la preparación operativa: validación del entorno, gestión de cwd, hooks, worktrees, tmux, memoria de sesión y otros prerequisitos. `bootstrap/state.ts` centraliza gran parte del estado vivo del proceso. `context.ts` arma contexto de sistema y usuario con cachés y acceso al entorno real.

El arranque de AgentOS, en cambio, está concentrado en `agentos/api/main.py`: carga agentes, tools y perfiles desde YAML, instancia memorias y elige el orquestador. Es un bootstrap explícito, corto y fácil de razonar, pero hoy está muy acoplado a la superficie FastAPI y carece de una capa formal de contexto operativo comparable a la de `jan`.

## Interfaces, dependencias y acoplamientos

- `jan` depende de un store global amplio para coordinar sesión, telemetría, configuración, permisos, render y estado operativo.
- `jan` mezcla responsabilidades de bootstrap, producto y operación en el mismo punto de entrada.
- `jan` separa bien el proveedor de contexto (`context.ts`) del resto del motor conversacional, y esa separación sí es aprovechable.
- AgentOS depende de singletons de módulo en `api/main.py`; esto simplifica el MVP, pero deja poco margen para reutilizar el runtime fuera de la API.

## Fortalezas y debilidades

### Fortalezas

- `jan` muestra una disciplina fuerte de preparación del entorno antes de operar.
- `jan` tiene un modelo maduro de contexto de sistema/usuario con caché y enriquecimiento desde git, memoria y configuración.
- AgentOS mantiene un bootstrap pequeño, explícito y compatible con su principio de mínimo privilegio.

### Debilidades

- `jan` concentra demasiada complejidad en el arranque y en un estado global muy grande.
- El store de `jan` es difícil de portar sin introducir fuerte acoplamiento transversal.
- AgentOS no tiene una capa interna de bootstrap reusable fuera de FastAPI.
- AgentOS no expone todavía un proveedor de contexto operativo equivalente para enriquecer orquestación y trazas.

## Riesgos técnicos y de seguridad

- Importar el patrón de estado global de `jan` degradaría la trazabilidad y testabilidad de AgentOS.
- Replicar side effects de arranque de `jan` aumentaría superficie de fallo y complejidad operativa.
- La ausencia en AgentOS de una capa de contexto estructurado limita evolución futura de prompts, auditoría y sesiones.

## Deuda técnica detectada

- En AgentOS, el bootstrap del sistema está mezclado con la inicialización del servidor HTTP en `agentos/api/main.py`.
- La selección de orquestador, memoria y perfiles ocurre en import-time, lo que complica pruebas más finas y múltiples superficies de entrada.
- Falta un contrato explícito de `runtime context` para enriquecer ejecución con datos del workspace, estado de sesión y entorno.

## Contraste con AgentOS

| Capacidad en código auditado | Equivalente en AgentOS | Brecha | Decisión |
| --- | --- | --- | --- |
| Bootstrap multietapa con preparación operativa | Bootstrap simple en `agentos/api/main.py` | AgentOS carece de capa reusable de runtime | `Adaptar` |
| Store global de sesión/proceso | Singletons pequeños por módulo | jan es demasiado amplio para AgentOS | `Rechazar` |
| Proveedor de contexto de sistema/usuario | Contexto implícito repartido entre memoria, request y orchestrator | Brecha clara en AgentOS | `Adaptar` |
| Lazy loading de superficies pesadas | Sin necesidad actual en API MVP | Valor acotado | `Postergar` |
| Estado de onboarding y ergonomía REPL | No existe en AgentOS | No prioritario para integración | `Rechazar` |

## Evaluación de utilidad para integración

| Capacidad | Veredicto | Esfuerzo | Riesgo | Recomendación |
| --- | --- | --- | --- | --- |
| Separar bootstrap interno del entrypoint HTTP | reusable with refactor | Medio | Bajo | Crear un `runtime bootstrap` independiente de FastAPI |
| Introducir proveedor de contexto operativo | reusable with refactor | Medio | Bajo | Definir un contrato de contexto para orquestación, memoria y observabilidad |
| Copiar store global de `bootstrap/state.ts` | not recommended for AgentOS | Alto | Alto | Mantener estado mínimo y modular |
| Emular side effects tempranos de `main.tsx` | useful as reference only | Medio | Medio | Tomar solo ideas de orden de inicialización |
| REPL launcher y onboarding | useful as reference only | Bajo | Bajo | Ignorar por ahora en roadmap nuclear |

## Recomendación accionable

- Crear un módulo de bootstrap de runtime en AgentOS que construya agentes, tools, permisos, memorias y orquestador sin depender de FastAPI.
- Introducir un objeto de contexto de ejecución con datos de request, sesión, usuario, workspace y señales observables.
- Mantener explícitamente como guardrail arquitectónico que AgentOS no debe adoptar un store global del tamaño y mezcla de responsabilidades de `jan`.
- Preparar un ADR para separar `runtime bootstrap` de `transport layer`.

## Informe técnico ejecutivo

### Resumen ejecutivo

El Bloque 1 confirma que `jan-research-main` resuelve muy bien el problema de arranque operativo y enriquecimiento contextual, pero lo hace con una complejidad de producto y estado global que no encaja directamente en AgentOS.

### Utilidad concreta para AgentOS

La utilidad principal está en dos patrones: desacoplar el runtime del entrypoint actual y crear una capa formal de contexto de ejecución. No conviene trasladar el bootstrap completo ni su store global.

### Decisión recomendada

`Adaptar`

### Esfuerzo estimado

`Medio`

### Riesgo estimado

`Medio`

### Prioridad sugerida para roadmap

`Alta`
