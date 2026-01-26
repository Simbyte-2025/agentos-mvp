# Spec: AgentOS + Agente Constructor (Builder)

## 1. Propósito

Construir un runtime (AgentOS) capaz de **orquestar agentes** y ejecutar herramientas de forma segura en entornos local y cloud.

## 2. Misión declarativa

"AgentOS ejecuta tareas complejas mediante agentes especializados y herramientas controladas, con trazabilidad, memoria y permisos mínimos."

## 3. Perímetro (NO hará)

- No auto-asignará permisos ni credenciales.
- No ejecutará herramientas destructivas sin aprobación humana.
- No escribirá/modificará archivos del host fuera de un workspace permitido.

## 4. Casos de uso (MVP)

1) Ejecutar una tarea simple por API (`/run`) y devolver resultado con trazas.
2) Seleccionar dinámicamente un agente especialista y subconjunto de tools.
3) Persistir checkpoints por session (working-state).
4) Recuperar memoria relevante (long-term) sin cargar todo el historial.
5) Builder Agent: generar un **plan de scaffolding** para crear:
   - un nuevo agente
   - una nueva tool

## 5. Métricas

- Tasa de éxito de tareas (por tipo): objetivo inicial > 70% (MVP).
- Latencia p95: < 5s en tareas sin herramientas externas.
- Tasa de escalado humano (HITL): reportar, objetivo < 20% en MVP.
- Costo por tarea (tokens): reportar.

## 6. Arquitectura

Componentes:
- API Gateway (FastAPI)
- Orchestrator (router + ejecución)
- Agent registry (carga desde YAML)
- Tool registry (carga desde YAML)
- Memory manager (short-term / working / long-term)
- Security (permission validator)
- Observability (logging estructurado)

## 7. Decisiones

- En MVP: tool router por heurística. En siguientes iteraciones: embeddings.
- En MVP: long-term memory naive. En siguientes iteraciones: vector store real.
- En MVP: Builder devuelve plan, no escribe en disco. Aplicación de cambios queda fuera.

