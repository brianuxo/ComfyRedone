"""
Constructor del payload para subir una tarea a OCI (queue/pending).

El backend NO ejecuta ComfyUI directamente. En su lugar, construye el JSON
del workflow y lo sube como objeto a OCI. El daemon de ComfyUI en Kaggle/Colab
polléa este prefijo, ejecuta el workflow y sube el resultado a results/.

Estructura del objeto en OCI queue/pending/{task_id}.json:
{
  "task_id": "<uuid>",
  "workflow": {
    "prompt": { "<nodo_id>": { "class_type": "...", "inputs": {...} } },
    "client_id": "<uuid>"
  },
  "created_at": "<iso_timestamp>",
  "status": "pending"
}
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from app.workflows.fibo2_edit.builder import build_workflow
from app.workflows.fibo2_edit.validator import validate


def build_oci_payload(params: dict, task_id: str | None = None) -> Dict[str, Any]:
    """
    Construye el payload completo para subir a OCI queue/pending.

    Args:
        params: Parámetros del usuario (prompt, image_b64, loras, seed, steps, ...)
        task_id: ID de tarea opcional. Si no se proporciona, se genera uno.

    Returns:
        Diccionario listo para serializar como JSON y subir a OCI.
    """
    if task_id is None:
        task_id = str(uuid.uuid4())

    # Construir y validar el workflow de ComfyUI
    workflow = build_workflow(params)
    validate(workflow)

    payload: Dict[str, Any] = {
        "task_id": task_id,
        "workflow": {
            "prompt": workflow,
            "client_id": task_id,
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
    }

    return payload


def queue_key(task_id: str) -> str:
    """Devuelve la clave OCI para una tarea pendiente."""
    return f"queue/pending/{task_id}.json"


def result_key(task_id: str, index: int = 0) -> str:
    """Devuelve la clave OCI para una imagen resultado."""
    return f"results/{task_id}/moss_{index + 1:03d}.png"


def meta_key(task_id: str) -> str:
    """Devuelve la clave OCI para los metadatos de una tarea completada."""
    return f"results/{task_id}/meta.json"


def error_key(task_id: str) -> str:
    """Devuelve la clave OCI para el error de una tarea."""
    return f"errors/{task_id}.json"