from __future__ import annotations

import os
import re
from pathlib import Path, PureWindowsPath
from typing import Set

class PathPolicy:
    """Políticas de seguridad para rutas de archivos.
    
    Implementa defensa en profundidad para bloquear:
    - Path traversal (..)
    - Rutas absolutas (Linux/Windows)
    - Unidades de Windows (C:, D:)
    - Rutas protegidas (config, deployments, .cursor)
    """

    # Archivos/Directorios protegidos (relativos al root)
    PROTECTED_DIRS = {".cursor", "deployments"}
    PROTECTED_FILES = {str(Path("config/profiles.yaml"))}
    
    # Excepciones permitidas
    ALLOWED_FILES = {".cursorfile"}

    def __init__(self, root_dir: Path):
        self.root = root_dir.resolve()

    def validate_path(self, path_str: str) -> Path:
        """Valida y resuelve una ruta relativa al root.
        
        Args:
            path_str: Ruta relativa string
            
        Returns:
            Path resuelto y validado dentro del root.
            
        Raises:
            ValueError: Si la ruta viola alguna política.
        """
        if not path_str:
            raise ValueError("Path vacío")

        # 1. Bloqueo de rutas absolutas y unidades Windows
        # Check básico de string primero
        if os.path.isabs(path_str):
             raise ValueError(f"Ruta absoluta no permitida: {path_str}")
             
        # Check específico de Windows (incluso en Linux runtime)
        win_path = PureWindowsPath(path_str)
        if win_path.drive:
            raise ValueError(f"Unidad Windows no permitida: {path_str}")
        
        # Check de inicio con separadores absolutos
        if path_str.startswith("/") or path_str.startswith("\\"):
            raise ValueError(f"Ruta absoluta no permitida: {path_str}")

        # 2. Path Traversal (..)
        if ".." in path_str.split("/") or ".." in path_str.split("\\"):
             raise ValueError(f"Path traversal (..) no permitido: {path_str}")

        # 3. Resolución segura dentro de ROOT
        try:
            # Unir con root
            full_path = self.root / path_str
            resolved = full_path.resolve()
            
            # Verificar containment (relative_to lanza error si no está dentro)
            # Esto protege contra ../.. resueltos y symlinks que salen del root
            resolved.relative_to(self.root)
            
        except (ValueError, RuntimeError) as e:
            raise ValueError(f"Path escapa del proyecto: {path_str}")

        # 4. Verificar Protected Paths (sobre la ruta relativa normalizada)
        rel_path = resolved.relative_to(self.root)
        
        # Caso especial: .cursor vs .cursorfile
        # Si el archivo es exactamente .cursorfile permitimos (si no está en directory protegido)
        if rel_path.name == ".cursorfile" and str(rel_path) == ".cursorfile":
             return resolved

        # Bloqueo de directorios protegidos
        # Verificamos si algún componente padre (o el mismo path si es dir) está en protegidos
        parts = rel_path.parts
        if parts and parts[0] in self.PROTECTED_DIRS:
             raise ValueError(f"Directorio protegido: {parts[0]}")
             
        # Bloqueo de archivos protegidos exactos
        if str(rel_path) in self.PROTECTED_FILES:
            raise ValueError(f"Archivo protegido: {str(rel_path)}")
            
        return resolved
