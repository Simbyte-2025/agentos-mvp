# Marco Metodológico Congelado

## Alcance

- Código auditado principal: `jan-research-main`
- Plataforma objetivo de contraste: `agentos-mvp-main`
- Unidad de avance: bloque funcional completo
- Criterio rector: maximizar utilidad real para AgentOS

## Ejes comparativos de AgentOS

1. Orquestación
2. Herramientas
3. Seguridad
4. Memoria
5. Estado y sesión
6. Observabilidad
7. API
8. Integración externa

## Criterios de utilidad técnica

Cada capacidad auditada se evalúa con estos criterios:

| Criterio | Pregunta rectora |
| --- | --- |
| Compatibilidad arquitectónica | ¿Encaja con el runtime, modelo de permisos y límites de AgentOS? |
| Costo de integración | ¿Cuánto refactor, adaptación o infraestructura nueva exige? |
| Riesgo de seguridad | ¿Amplía superficie de ataque o complica control de privilegios? |
| Dependencia externa | ¿Introduce runtimes, SDKs, servicios o acoplamientos no deseados? |
| Impacto operativo | ¿Mejora operación, depuración, despliegue o uso diario del sistema? |
| Valor funcional | ¿Aporta capacidad claramente superior o faltante en AgentOS? |
| Mantenibilidad | ¿Su complejidad y tamaño son sostenibles en el contexto de AgentOS? |

## Matriz de decisión por hallazgo

| Decisión | Uso |
| --- | --- |
| `Adoptar` | La capacidad calza con cambios menores o nulos. |
| `Adaptar` | La idea es valiosa, pero debe rediseñarse para AgentOS. |
| `Rechazar` | No conviene integrarla por riesgo, costo o incompatibilidad. |
| `Postergar` | Tiene valor futuro, pero no encaja en la etapa actual de AgentOS. |

## Veredicto de reutilización

| Veredicto | Significado |
| --- | --- |
| `reusable directly` | Reutilizable casi tal cual en AgentOS. |
| `reusable with refactor` | Reutilizable con rediseño o extracción parcial. |
| `useful as reference only` | Útil como referencia arquitectónica o de producto. |
| `not recommended for AgentOS` | No recomendable para incorporar. |

## Escalas normalizadas

### Riesgo

- `Bajo`: efecto limitado y fácil de contener
- `Medio`: requiere controles y validación antes de integrar
- `Alto`: impacta seguridad, operación o complejidad estructural

### Esfuerzo

- `Bajo`: cambios localizados
- `Medio`: cambios entre módulos o contratos
- `Alto`: rediseño transversal o nuevas dependencias estructurales

### Prioridad de roadmap

- `Alta`: útil para cerrar brechas actuales del MVP
- `Media`: valiosa tras estabilizar núcleo y seguridad
- `Baja`: útil en fases posteriores o como referencia

## Secuencia fija por bloque

1. Delimitación del bloque
2. Análisis interno detallado
3. Contraste contra AgentOS
4. Evaluación de utilidad para integración
5. Recomendación accionable
6. Cierre documental y actualización del registro maestro
