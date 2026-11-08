"""Endpoint de salud: verificar si el worker (ComfyUI) está encendido."""

from __future__ import annotations

from fastapi import APIRouter

from app.workers.health import worker_health

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("", summary="Verificar estado del worker")
async def health_check():
    """Devuelve si ComfyUI está online y sus estadísticas básicas.

    Este es el módulo que el frontend consulta para saber si puede enviar
    tareas de ejecución. Si devuelve `online: false`, el frontend debe
    deshabilitar el botón de ejecutar y mostrar un aviso.
    """
    return worker_health.check()