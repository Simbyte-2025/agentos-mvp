from __future__ import annotations

import re
from pathlib import Path, PureWindowsPath
from typing import List, Optional

class PathSecurityError(Exception):
    """Excepción lanzada cuando se detecta una violación de seguridad en una ruta."""
    pass

class PathPolicy:
    def __init__(self, root_dir: str | Path, protected_paths: Optional[List[str]] = None):
        self.root_dir = Path(root_dir).resolve()
        
        # Rutas protegidas por defecto
        if not protected_paths:
            protected_paths = [
                "config/profiles.yaml",
                ".cursor/",
                "deployments/",
                ".env",
                "agentos/security/",
                "agentos/api/auth.py"
            ]
        
        # Convertir a objetos Path relativos para comparación consistente
        self.protected_paths = [Path(p) for p in protected_paths]

    def validate_path(self, target_path: str) -> Path:
        """
        Valida una ruta contra ataques de traversal, rutas absolutas y áreas protegidas.
        Retorna la ruta resuelta relativa al root si es válida.
        """
        # 1. Bloqueo de unidades de Windows (C:, D:, etc.) 
        # Usamos PureWindowsPath para detectar el drive incluso si estamos en Linux
        if PureWindowsPath(target_path).drive or re.match(r'^[a-zA-Z]:', target_path):
            raise PathSecurityError(f"Rutas con unidad de Windows no permitidas: {target_path}")

        p = Path(target_path)

        # 2. Bloquear rutas absolutas (Linux /)
        if p.is_absolute():
            raise PathSecurityError(f"Rutas absolutas no permitidas: {target_path}")

        # 3. Resolver ruta y verificar que esté dentro del root usando relative_to
        try:
            # Unimos root con la ruta objetivo y resolvemos para eliminar .. y symlinks
            resolved_path = (self.root_dir / p).resolve()
            # relative_to lanzará ValueError si resolved_path no está bajo self.root_dir
            relative_path = resolved_path.relative_to(self.root_dir)
        except (ValueError, RuntimeError):
            raise PathSecurityError(f"Intento de Path Traversal o ruta fuera del root detectado: {target_path}")

        # 4. Verificar contra rutas protegidas usando lógica de Path
        for protected in self.protected_paths:
            # Caso 1: Coincidencia exacta (archivo o directorio)
            if relative_path == protected:
                raise PathSecurityError(f"Acceso a ruta protegida denegado: {target_path}")
            
            # Caso 2: La ruta objetivo está dentro de un directorio protegido
            if protected in relative_path.parents:
                raise PathSecurityError(f"Acceso a contenido dentro de directorio protegido denegado: {target_path}")

        return relative_path
