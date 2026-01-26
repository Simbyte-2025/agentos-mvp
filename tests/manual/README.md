# Manual Test Scripts

These scripts are for manual verification and demonstration. They are **not** part of the automated test suite.

## Available Scripts

### `ltm_persist_demo.py`

Demonstrates Long-Term Memory persistence with both naive and chroma backends.

**Usage:**

```powershell
# With naive backend (default)
.\.venv\Scripts\python tests\manual\ltm_persist_demo.py

# With chroma backend (requires: pip install chromadb)
$env:AGENTOS_LTM_BACKEND = "chroma"
.\.venv\Scripts\python tests\manual\ltm_persist_demo.py
```

### `chroma_verification.py`

Low-level verification of ChromaDB backend functionality. Only runs if chromadb is installed.

**Usage:**

```powershell
# Requires: pip install chromadb
.\.venv\Scripts\python tests\manual\chroma_verification.py
```

