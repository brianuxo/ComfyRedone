"""
Endpoint de depuración para verificar el estado de OCI.
Útil para diagnosticar por qué el daemon de Kaggle no procesa tareas.
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from app.storage.oci_client import oci_client

router = APIRouter(prefix="/api/oci", tags=["oci-debug"])


@router.get("/status", summary="Estado de OCI para depuración")
async def oci_status() -> Dict[str, Any]:
    """
    Devuelve información sobre el estado de OCI para depuración:
    - Si OCI está configurado y accesible
    - Tareas pendientes en queue/pending/
    - Tareas en procesamiento en queue/processing/
    - Resultados disponibles en results/
    - Heartbeat del worker (status/worker.json)
    """
    configured = oci_client.is_configured()
    bucket_ok = False
    pending_keys = []
    processing_keys = []
    result_keys = []
    cancelled_keys = []
    error_keys = []
    worker_heartbeat = None

    if configured:
        try:
            bucket_ok = oci_client.bucket_exists()
            if bucket_ok:
                pending_keys = oci_client.list_objects("queue/pending/")
                processing_keys = oci_client.list_objects("queue/processing/")
                result_keys = oci_client.list_objects("results/")
                cancelled_keys = oci_client.list_objects("queue/cancelled/")
                error_keys = oci_client.list_objects("errors/")
                worker_heartbeat = oci_client.get_json("status/worker.json")
        except Exception as exc:
            # Log but don't fail the endpoint
            import logging
            logging.warning("Error consultando OCI: %s", exc)

    return {
        "bucket": oci_client.bucket if configured else None,
        "namespace": oci_client.namespace if configured else None,
        "region": oci_client.region if configured else None,
        "oci_configured": configured,
        "oci_online": bucket_ok,
        "counts": {
            "pending": len(pending_keys),
            "processing": len(processing_keys),
            "results": len(result_keys),
            "cancelled": len(cancelled_keys),
            "errors": len(error_keys),
        },
        "pending_keys": pending_keys[:20],
        "processing_keys": processing_keys[:20],
        "result_keys": result_keys[:20],
        "worker_heartbeat": worker_heartbeat,
    }


@router.get("/pending/{task_id}", summary="Verificar si una tarea está pendiente en OCI")
async def check_pending(task_id: str) -> Dict[str, Any]:
    """Verifica si una tarea específica está en queue/pending/."""
    key = f"queue/pending/{task_id}"
    if not key.endswith(".json"):
        key += ".json"
    data = oci_client.get_json(key)
    return {
        "task_id": task_id,
        "key": key,
        "exists": data is not None,
        "data": data,
    }


@router.get("/results/{task_id}", summary="Verificar si hay resultados en OCI")
async def check_results(task_id: str) -> Dict[str, Any]:
    """Verifica si hay resultados para una tarea en OCI results/."""
    meta = oci_client.get_json(f"results/{task_id}/meta.json")
    image = oci_client.get_object(f"results/{task_id}/moss_001.png")
    return {
        "task_id": task_id,
        "meta_exists": meta is not None,
        "meta": meta,
        "image_exists": image is not None,
        "image_size_bytes": len(image) if image else None,
    }