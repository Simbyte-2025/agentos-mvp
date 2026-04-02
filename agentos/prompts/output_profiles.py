"""
Loader de output profiles desde config/output_profiles/*.md
"""
from pathlib import Path
from typing import Optional

DEFAULT_PROFILES_DIR = "config/output_profiles"


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Extrae frontmatter YAML y contenido del archivo."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    import yaml
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except Exception:
        meta = {}
    return meta, parts[2].strip()


def load_output_profile(name: str, profiles_dir: str = DEFAULT_PROFILES_DIR) -> Optional[dict]:
    """Carga un output profile por nombre. Retorna None si no existe."""
    path = Path(profiles_dir) / f"{name}.md"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    meta, content = _parse_frontmatter(text)
    return {
        "name": meta.get("name", name),
        "description": meta.get("description", ""),
        "keep_base_instructions": meta.get("keep_base_instructions", True),
        "prompt": content,
    }


def list_output_profiles(profiles_dir: str = DEFAULT_PROFILES_DIR) -> list:
    """Lista todos los profiles disponibles."""
    base = Path(profiles_dir)
    if not base.exists():
        return []
    return [f.stem for f in base.glob("*.md")]
