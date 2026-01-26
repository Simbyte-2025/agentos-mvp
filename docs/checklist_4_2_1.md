# Checklist de Verificación - Fase 4.2.1

Este checklist debe completarse antes de iniciar desarrollos en la Fase 4.2.1.

## 1. Entorno Python
- [ ] **Versión >= 3.11**: `python --version`
- [ ] **Venv Activo**: `Get-Command python` (PowerShell) o `where python` (CMD)

## 2. Dependencias
- [ ] **Instalación Editable**: `pip show agentos-mvp`
- [ ] **Librerías Base**: `pip list` (confirmar fastapi, uvicorn, pydantic, pytest)

## 3. Estado de Tests
- [ ] **Suite Completa**: `pytest -v`
- [ ] **Integration/Smoke Test**: `pytest tests/integration/test_run_planner_smoke.py -v`
