# ADR 004: Long-Term Memory Backend Architecture

## Contexto

El sistema AgentOS MVP requiere memoria persistente a largo plazo para:
- Retener conocimiento entre sesiones
- Buscar información histórica relevante para nuevas tareas
- Escalar más allá de memoria en RAM (miles/millones de items)

La implementación inicial (`LongTermMemory`) era un almacén en memoria volátil con búsqueda por token-overlap:
- ❌ Datos se pierden al reiniciar el proceso
- ❌ Limitado por RAM disponible
- ❌ No hay búsqueda semántica (solo overlap de palabras)
- ❌ No hay API para cambiar el backend sin tocar código

## Decisión

Implementar **backend abstraction pattern** para memoria long-term con dos implementaciones:

### 1. Interfaz `LongTermMemoryBackend`

```python
class LongTermMemoryBackend(ABC):
    @abstractmethod
    def add(text: str, tags: List[str] | None) -> None
    
    @abstractmethod
    def retrieve(query: str, top_k: int) -> List[MemoryItem]
```

Todas las implementaciones deben cumplir este contrato.

### 2. Backend Naive (Default)

- **Implementación**: `NaiveMemoryBackend`
- **Storage**: In-memory (volátil)
- **Retrieval**: Token-overlap scoring
- **Dependencias**: Ninguna
- **Uso**: Desarrollo, testing, fallback

### 3. Backend ChromaDB (Opcional)

- **Implementación**: `ChromaMemoryBackend`
- **Storage**: Persistente en disco (SQLite via ChromaDB)
- **Retrieval**: Token-overlap scoring (⚠️ **SIN embeddings en Fase 4.2.2**)
- **Dependencias**: `chromadb` (lazy import)
- **Uso**: Persistencia entre reinicializaciones

### 4. Feature Flag: `AGENTOS_LTM_BACKEND`

```powershell
# Default (naive, en memoria)
$env:AGENTOS_LTM_BACKEND = "naive"

# Persistente (ChromaDB)
$env:AGENTOS_LTM_BACKEND = "chroma"
```

**Fallback automático**: Si ChromaDB no está instalado o falla, cae a `naive` con warning.

### 5. Configuración de Persistencia: `AGENTOS_LTM_PERSIST_DIR`

```powershell
# Default
$env:AGENTOS_LTM_PERSIST_DIR = ".agentos_memory"

# Custom
$env:AGENTOS_LTM_PERSIST_DIR = "C:\data\ltm"
```

El directorio se crea automáticamente si no existe (usando `pathlib.Path` para Windows).

### 6. Dependencia Opcional (Lazy Import)

ChromaDB **NO se agrega a `pyproject.toml`** en esta fase. La detección es 100% lazy:

```python
# En ChromaMemoryBackend.__init__()
try:
    import chromadb
except ImportError:
    raise ImportError("ChromaDB backend requires chromadb package...")
```

Si el import falla, `LongTermMemory._select_backend()` captura el error y hace fallback a naive.

**Instalación manual**:
```powershell
pip install chromadb
```

## Importantes Restricciones de Fase 4.2.2

### ❌ Sin Embeddings / Sin Modelos

Para **validar la arquitectura** sin aumentar complejidad ni descargar modelos (~80MB):

- ChromaDB se usa **solo para persistencia**, NO para vectores semánticos
- Retrieval usa **token-overlap** (mismo algoritmo que naive)
- No hay diferencia en calidad de búsqueda entre naive y chroma
- **Ventaja de chroma**: solo persistencia

### ✅ Qué se implementa en Fase 4.2.2

- Backend abstraction pattern
- Feature flag `AGENTOS_LTM_BACKEND`
- Lazy import y fallback robusto
- Persistencia local (ChromaDB)
- Tests de arquitectura y fallback

### 🔜 Qué queda para Fase 4.2.3+

- **Embeddings reales** (sentence-transformers, OpenAI, etc.)
- **Búsqueda semántica** (vector similarity search)
- **Metadata filtering** (buscar por tags, fecha, etc.)
- **Integración con Notion/GitHub** (importar datos externos)
- **Compresión/summarization** de memoria antigua
- **Dependency en pyproject.toml** (cuando embeddings sean mandatorios)

## Detalles de Implementación

### Scoring de Retrieval (Token-Overlap)

Tanto naive como chroma usan este algoritmo MVP:

```python
# Tokenizar query y documentos
qtok = set(re.findall(r"[a-zA-ZáéíóúÁÉÍÓÚñÑ0-9_]+", query.lower()))
itok = set(re.findall(r"[a-zA-ZáéíóúÁÉÍÓÚñÑ0-9_]+", doc.text.lower()))

# Score = intersección de tokens
score = len(qtok.intersection(itok))
```

**Limitaciones conocidas**:
- No entiende sinónimos ("coche" ≠ "auto")
- No entiende contexto ("banco" = mueble vs. "banco" = institución)
- Favorece documentos largos (más tokens → más overlap)

Estas limitaciones se resolverán con embeddings en Fase 4.2.3+.

### Guard-Rail: MAX_DOCS_FOR_RETRIEVAL

Para prevenir OOM en ChromaDB con millones de documentos:

```python
MAX_DOCS_FOR_RETRIEVAL = 1000
```

Si la colección tiene más de 1000 documentos, solo se cargan los primeros 1000 para scoring. Se logea warning:

```
Collection has 50000 documents. Limiting retrieval to first 1000 documents to prevent memory issues.
```

Este límite se removerá cuando se implemente búsqueda vectorial (top-k directo en ChromaDB).

## Consecuencias

### Positivas

- ✅ **Abstracción limpia**: Fácil agregar nuevos backends (Pinecone, Weaviate, etc.)
- ✅ **Zero breaking changes**: API pública de `LongTermMemory` sin cambios
- ✅ **Fallback robusto**: Sistema nunca se rompe por falta de ChromaDB
- ✅ **Persistencia validada**: Arquitectura probada sin complejidad de embeddings
- ✅ **Windows compatible**: `pathlib.Path`, lazy imports, env vars

### Negativas / Trade-offs

- ⚠️ **Latencia de ChromaDB**: ~100-500ms para inicializar client + collection (vs ~1ms naive)
- ⚠️ **Tamaño en disco**: SQLite crece con documentos (~1KB por documento + overhead)
- ⚠️ **No mejora de búsqueda**: Token-overlap es igual de "tonto" en ambos backends
- ⚠️ **Límite de 1000 docs**: Guard-rail previene OOM pero limita búsqueda
- ⚠️ **Dependencia manual**: Usuarios deben instalar chromadb explícitamente

### Windows Considerations

1. **Path handling**: Uso de `pathlib.Path` para normalizar separadores
2. **File locking**: ChromaDB usa SQLite que puede tener issues de locking en Windows (mitigado con cleanup en tests)
3. **Env vars**: PowerShell syntax (`$env:VAR`) documentada explícitamente

## Testing

### Unit Tests (siempre ejecutan)

```powershell
pytest tests/unit/test_ltm_backend_selection.py -v
```

- Default backend (naive)
- Explicit naive
- Invalid backend → fallback
- Chroma fallback cuando no está instalado
- Case-insensitive
- Funcionalidad preservada

### Integration Tests (skip si chromadb no instalado)

```powershell
pytest tests/integration/test_ltm_chroma_backend.py -v
```

- Basic add/retrieve
- **Persistencia entre instancias** (key test)
- Tags preservation
- Empty query handling
- Top-k limit

**Marcado con**:
```python
pytestmark = pytest.mark.skipif(
    not CHROMADB_AVAILABLE,
    reason="chromadb not installed - install with: pip install chromadb"
)
```

Si ChromaDB no está instalado → tests se skipean limpiamente (no fallan).

## Alternativas Consideradas

### 1. Factory Function Pattern

**Rechazada**: Cambiaría API pública de `LongTermMemory()` a función que devuelve backend.

```python
# ❌ Rompe código existente
def LongTermMemory() -> LongTermMemoryBackend:
    return NaiveMemoryBackend()
```

**Decisión**: Mantener `LongTermMemory` como clase, delegar a `self._backend` internamente.

### 2. Agregar chromadb a pyproject.toml como opcional

**Rechazada para Fase 4.2.2**: Sin embeddings, ChromaDB no aporta valor real (solo persistencia).

**Decisión**: Dejar como dependency manual hasta Fase 4.2.3 cuando embeddings sean obligatorios.

### 3. Usar pickle/json para persistencia

**Rechazada**: No escala, no tiene índices, no permite búsqueda incremental.

**Decisión**: ChromaDB provee base sólida para futura búsqueda vectorial.

## Referencias

- [docs/ADR_003_docker_backend.md](ADR_003_docker_backend.md) - Patrón de feature flag similar
- ChromaDB docs: https://docs.trychroma.com/
- Fase 4.2.1 completada: Docker backend opcional
- **Fase 4.2.3 (pendiente)**: Embeddings reales + búsqueda semántica
