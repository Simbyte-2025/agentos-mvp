import os
import sys
from pathlib import Path

# Agregar el directorio raíz del proyecto al PYTHONPATH para que los tests encuentren el paquete agentos
root_dir = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(root_dir))

# Configurar variables de entorno globales seguras para tests (mock)
os.environ["AGENTOS_WORKSPACE_ROOT"] = str(root_dir / "tests" / "fixtures" / "workspace")
os.environ["ANTHROPIC_API_KEY"] = "sk-mock-key-for-testing"
os.environ["MINIMAX_API_KEY"] = "mock-key"
