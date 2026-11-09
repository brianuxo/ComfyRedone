"""
Endpoints de tareas: crear, consultar y cancelar ejecución vía OCI.

El backend NO se conecta a ComfyUI directamente. Todo fluye a través de OCI:
  - POST /api/tasks  -> sube la tarea a OCI queue/pending/{task_id}.json
  - GET  /api/tasks/{id}  -> lee el estado desde caché local + OCI (queue/processing/, results/, errors/)
  - DELETE /api/tasks/{id} -> marca cancelado en OCI queue/cancelled/{task_id}.json
  - POST /api/tasks/txt2img  -> crea tarea txt2img (generación desde cero)
  - POST /api/tasks/edit     -> crea tarea edit (con imagen de entrada)

SINCRONIZACIÓN OCI → CACHÉ LOCAL:
  Cuando una tarea está en estado "queued" o "running" en el caché local,
  el endpoint GET consulta OCI para verificar si el daemon ya completó
  la ejecución y subió el resultado a results/{task_id}/.
"""

from __future__ import annotations

import asyncio
import base64
import json
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.db import store as store_module
from app.storage.oci_client import oci_client
from app.workflows.fibo2_edit.oci_payload import (
    build_oci_payload,
    error_key,
    meta_key,
    queue_key,
    result_key,
)
from app.workflows.fibo2_edit.schema import Fibo2EditRequest, Fibo2EditResponse
from app.workflows.fibo2_txt2img.oci_payload import build_oci_payload as build_oci_payload_txt2img
from app.workflows.fibo2_txt2img.schema import Fibo2Txt2ImgRequest, Fibo2Txt2ImgResponse
from app.workflows.moss_image import build_oci_payload as build_oci_payload_moss
from app.workflows.fibo2_txt2img.schema import MossImageRequest, MossImageResponse

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _ensure_store() -> None:
    if store_module.task_store is None:
        store_module.init_task_store(ttl_seconds=settings.TASK_TTL_SECONDS)


def _resolve_task_from_oci(task_id: str) -> Dict[str, Any] | None:
    """
    Intenta resolver el estado de una tarea consultando OCI directamente.
    Se usa cuando el caché local no tiene información definitiva (queued/running).
    """
    # Verificar si hay un resultado en OCI
    meta = oci_client.get_json(meta_key(task_id))
    if meta is not None:
        image_bytes = oci_client.get_object(result_key(task_id, index=0))
        image_b64 = (
            base64.b64encode(image_bytes).decode("utf-8") if image_bytes else None
        )
        return {
            "task_id": task_id,
            "status": meta.get("status", "completed"),
            "image_b64": image_b64,
            "error": meta.get("error"),
            "created_at": meta.get("created_at"),
            "updated_at": meta.get("finished_at", meta.get("created_at")),
            "source": "oci_results",
        }

    # Verificar si hay un error en OCI
    error_data = oci_client.get_json(error_key(task_id))
    if error_data is not None:
        return {
            "task_id": task_id,
            "status": "failed",
            "image_b64": None,
            "error": error_data.get("error", "Error desconocido"),
            "created_at": error_data.get("ts", ""),
            "updated_at": error_data.get("ts", ""),
            "source": "oci_errors",
        }

    # Verificar si la tarea está siendo procesada
    pending_data = oci_client.get_json(f"queue/processing/{task_id}.json")
    if pending_data is not None:
        return {
            "task_id": task_id,
            "status": "running",
            "image_b64": None,
            "error": None,
            "created_at": pending_data.get("created_at", ""),
            "updated_at": pending_data.get("created_at", ""),
            "source": "oci_processing",
        }

    # Verificar si la tarea sigue pendiente en OCI
    queue_data = oci_client.get_json(queue_key(task_id))
    if queue_data is not None:
        return {
            "task_id": task_id,
            "status": "queued",
            "image_b64": None,
            "error": None,
            "created_at": queue_data.get("created_at", ""),
            "updated_at": queue_data.get("created_at", ""),
            "source": "oci_pending",
        }

    # Verificar si fue cancelada
    cancelled_data = oci_client.get_json(f"queue/cancelled/{task_id}.json")
    if cancelled_data is not None:
        return {
            "task_id": task_id,
            "status": "cancelled",
            "image_b64": None,
            "error": None,
            "created_at": cancelled_data.get("cancelled_at", ""),
            "updated_at": cancelled_data.get("cancelled_at", ""),
            "source": "oci_cancelled",
        }

    return None


@router.post(
    "",
    response_model=Fibo2EditResponse,
    summary="Lanzar ejecución FIBO 2.0 Edit (sube a OCI queue/pending)",
)
async def create_task(request: Fibo2EditRequest) -> Any:
    """
    Recibe los parámetros del usuario, construye el workflow JSON de FIBO 2.0 Edit,
    lo valida y lo sube como objeto a OCI queue/pending/{task_id}.json.

    El daemon de ComfyUI en Kaggle/Colab polléa este prefijo, ejecuta el workflow
    y sube el resultado a OCI results/{task_id}/.

    Nunca se conecta a ComfyUI directamente. Nunca escribe en disco del worker.
    """
    _ensure_store()

    task_id_param = getattr(request, "task_id", None) or None
    payload = build_oci_payload(request.dict(), task_id=task_id_param)
    task_id = payload["task_id"]

    # DEBUG: escribir inputs del nodo 3 a archivo
    node3_inputs = payload["workflow"]["prompt"].get("3", {}).get("inputs", {})
    with open(r"C:\Users\brian\Desktop\ALL\Proyectos\RustComfyCrear\debug_task.log", "w") as f:
        f.write(f"task_id={task_id}, nodo3 inputs={node3_inputs}\n")
        f.write(f"request.dict()={request.dict()}\n")
        f.write(f"builder.py file={__import__('app.workflows.fibo2_edit.builder', fromlist=['x']).__file__}\n")

    # Registrar en almacén local (caché rápido) con el mismo task_id de OCI
    store_module.task_store.create(payload["workflow"], task_id=task_id)

    # Subir a OCI queue/pending
    success = oci_client.put_object_json(queue_key(task_id), payload)
    if not success:
        store_module.task_store.update_status(task_id, "failed", error="No se pudo subir la tarea a OCI")
        raise HTTPException(status_code=500, detail="Error subiendo tarea a OCI")

    store_module.task_store.update_status(task_id, "queued")

    return Fibo2EditResponse(
        task_id=task_id,
        status="queued",
        created_at=payload["created_at"],
    )


@router.post(
    "/txt2img",
    response_model=Fibo2Txt2ImgResponse,
    status_code=201,
    summary="Lanzar ejecución FIBO 2.0 Txt2Img (generación desde cero)",
)
async def create_txt2img_task(request: Fibo2Txt2ImgRequest) -> Fibo2Txt2ImgResponse:
    """
    Recibe los parámetros del usuario, construye el workflow JSON de FIBO 2.0 Txt2Img
    (generación desde cero, SIN imagen de entrada), lo valida y lo sube como objeto
    a OCI queue/pending/{task_id}.json con mode="txt2img".

    El daemon de ComfyUI en Kaggle/Colab polléa este prefijo, ejecuta el workflow
    y sube el resultado a OCI results/{task_id}/.

    Nunca se conecta a ComfyUI directamente. Nunca escribe en disco del worker.
    """
    _ensure_store()

    task_id_param = getattr(request, "task_id", None) or None
    payload = build_oci_payload_txt2img(request.dict(), task_id=task_id_param)
    task_id = payload["task_id"]

    # DEBUG: escribir inputs del nodo 3 a archivo
    node3_inputs = payload["workflow"]["prompt"].get("3", {}).get("inputs", {})
    with open(r"C:\Users\brian\Desktop\ALL\Proyectos\RustComfyCrear\debug_task_txt2img.log", "w") as f:
        f.write(f"task_id={task_id}, nodo3 inputs={node3_inputs}\n")
        f.write(f"request.dict()={request.dict()}\n")

    # Registrar en almacén local (caché rápido) con el mismo task_id de OCI
    store_module.task_store.create(payload["workflow"], task_id=task_id)

    # Subir a OCI queue/pending
    success = oci_client.put_object_json(queue_key(task_id), payload)
    if not success:
        store_module.task_store.update_status(task_id, "failed", error="No se pudo subir la tarea a OCI")
        raise HTTPException(status_code=500, detail="Error subiendo tarea a OCI")

    store_module.task_store.update_status(task_id, "queued")

    return Fibo2Txt2ImgResponse(
        task_id=task_id,
        status="queued",
        created_at=payload["created_at"],
    )


@router.post(
    "/moss",
    response_model=MossImageResponse,
    status_code=201,
    summary="Lanzar ejecución Moss Image (text-to-image)",
)
async def create_moss_task(request: MossImageRequest) -> MossImageResponse:
    """
    Recibe los parámetros del usuario, construye el workflow JSON de Moss Image
    (generación desde cero, SIN imagen de entrada), lo valida y lo sube como objeto
    a OCI queue/pending/{task_id}.json.

    El daemon de ComfyUI en Kaggle/Colab polléa este prefijo, ejecuta el workflow
    y sube el resultado a OCI results/{task_id}/.

    Nunca se conecta a ComfyUI directamente. Nunca escribe en disco del worker.
    """
    _ensure_store()

    task_id_param = getattr(request, "task_id", None)
    payload = build_oci_payload_moss(request.dict(), task_id=task_id_param)
    task_id = payload["task_id"]

    # Registrar en almacén local (caché rápido) con el mismo task_id de OCI
    store_module.task_store.create(payload["workflow"], task_id=task_id)

    # Subir a OCI queue/pending
    success = oci_client.put_object_json(queue_key(task_id), payload)
    if not success:
        store_module.task_store.update_status(task_id, "failed", error="No se pudo subir la tarea a OCI")
        raise HTTPException(status_code=500, detail="Error subiendo tarea a OCI")

    store_module.task_store.update_status(task_id, "queued")

    return MossImageResponse(
        task_id=task_id,
        status="queued",
        created_at=payload["created_at"],
    )


@router.get("/{task_id}", summary="Consultar estado y resultado de una tarea (desde OCI)")
async def get_task(task_id: str) -> Dict[str, Any]:
    """
    Consulta el estado de una tarea. Primero revisa el caché local, y si el estado
    no es definitivo (queued/running), también consulta OCI para obtener el estado
    real (queue/processing/, results/, errors/).
    """
    _ensure_store()

    record = store_module.task_store.get(task_id)

    # Si el caché local tiene un estado definitivo (completed/failed/cancelled), devolverlo
    if record and record.status in ("completed", "failed", "cancelled"):
        response: Dict[str, Any] = {
            "task_id": record.task_id,
            "status": record.status,
            "image_b64": record.image_b64,
            "error": record.error,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "source": "cache",
        }
        # Si está completada y no tenemos imagen en caché, intentar leer de OCI
        if record.status == "completed" and not record.image_b64:
            image_bytes = oci_client.get_object(result_key(task_id, index=0))
            if image_bytes:
                response["image_b64"] = base64.b64encode(image_bytes).decode("utf-8")
                store_module.task_store.update_status(
                    task_id, "completed", image_b64=response["image_b64"]
                )
        return response

    # El estado no es definitivo (queued/running) o no existe en caché local.
    # Consultar OCI para obtener el estado real.
    oci_result = _resolve_task_from_oci(task_id)
    if oci_result is not None:
        # Sincronizar con el caché local
        store_module.task_store.create({}, task_id=task_id)
        store_module.task_store.update_status(
            oci_result["task_id"],
            oci_result["status"],
            image_b64=oci_result.get("image_b64"),
            error=oci_result.get("error"),
        )
        return oci_result

    # Si no existe en caché local ni en OCI, tarea no encontrada
    if record is None:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")

    # Devolver desde caché local (estado no definitivo)
    return {
        "task_id": record.task_id,
        "status": record.status,
        "image_b64": record.image_b64,
        "error": record.error,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "source": "cache",
    }


@router.get("/{task_id}/stream", summary="Stream de estado via Server-Sent Events (SSE)")
async def stream_task_status(task_id: str):
    """
    Endpoint SSE para recibir actualizaciones de estado en tiempo real.
    Elimina la necesidad de polling en el frontend.
    
    Eventos:
    - data: {task_id, status, image_b64?, error?, ...}
    
    Conexión se cierra automáticamente al llegar a estado final (completed/failed/cancelled).
    """
    _ensure_store()
    
    # Verificar que la tarea existe
    record = store_module.task_store.get(task_id)
    if not record:
        # Verificar en OCI
        oci_result = _resolve_task_from_oci(task_id)
        if not oci_result:
            raise HTTPException(status_code=404, detail="Tarea no encontrada")
    
    async def event_generator():
        # Obtener estado actual una sólo vez (sin bucle de polling que bloquee el event loop)
        current_record = store_module.task_store.get(task_id)
        oci_result = None

        if current_record:
            status = current_record.status
            image_b64 = current_record.image_b64
            error = current_record.error
            created_at = current_record.created_at
            updated_at = current_record.updated_at

            # Si el estado no es definitivo O faltó la imagen, consultar OCI una sólo vez
            if status in ("queued", "running") or (status == "completed" and not image_b64):
                oci_result = _resolve_task_from_oci(task_id)
                if oci_result:
                    status = oci_result["status"]
                    image_b64 = oci_result.get("image_b64") or image_b64
                    error = oci_result.get("error") or error
                    created_at = oci_result.get("created_at", created_at)
                    updated_at = oci_result.get("updated_at", updated_at)
                    # Sincronizar con el caché local para peticiones futuras
                    store_module.task_store.update_status(
                        task_id,
                        status,
                        image_b64=image_b64,
                        error=error,
                    )
        else:
            # No existe en caché local, consultar OCI
            oci_result = _resolve_task_from_oci(task_id)
            if oci_result:
                status = oci_result["status"]
                image_b64 = oci_result.get("image_b64")
                error = oci_result.get("error")
                created_at = oci_result.get("created_at", "")
                updated_at = oci_result.get("updated_at", "")
            else:
                status = "unknown"
                image_b64 = None
                error = None
                created_at = ""
                updated_at = ""

        # Enviar evento con el estado actual
        payload = {
            "task_id": task_id,
            "status": status,
            "created_at": created_at,
            "updated_at": updated_at,
        }
        if image_b64:
            payload["image_b64"] = image_b64
        if error:
            payload["error"] = error

        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "close",
            "X-Accel-Buffering": "no",
        }
    )
@router.delete("/{task_id}", summary="Cancelar una tarea (marca en OCI queue/cancelled)")
async def delete_task(task_id: str) -> Dict[str, str]:
    """
    Marca una tarea como cancelada subiendo un archivo a OCI
    queue/cancelled/{task_id}.json. El daemon de ComfyUI verifica este prefijo
    antes de ejecutar.
    """
    _ensure_store()

    if not store_module.task_store.get(task_id):
        raise HTTPException(status_code=404, detail="Tarea no encontrada")

    # Marcar como cancelada en OCI
    cancel_payload = {
        "task_id": task_id,
        "cancelled_at": datetime.now(timezone.utc).isoformat(),
        "status": "cancelled",
    }
    oci_client.put_object_json(f"queue/cancelled/{task_id}.json", cancel_payload)

    store_module.task_store.update_status(task_id, "cancelled")
    return {"task_id": task_id, "status": "cancelled"}


@router.get("", summary="Listar tareas recientes (caché local + OCI)")
async def list_tasks() -> List[Dict[str, Any]]:
    """
    Lista tareas recientes. Combina el almacén local (caché) con
    las tareas pendientes en OCI queue/pending/ y resultados en OCI results/.
    """
    _ensure_store()

    records = store_module.task_store.list()
    result: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()

    # 1. Tareas del caché local
    for r in records:
        seen_ids.add(r.task_id)
        result.append(
            {
                "task_id": r.task_id,
                "status": r.status,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
                "has_image": r.image_b64 is not None,
                "error": r.error,
                "source": "cache",
            }
        )

    # 2. Completar con resultados de OCI (results/{task_id}/)
    if oci_client.is_configured() and oci_client.bucket_exists():
        try:
            result_keys = oci_client.list_objects("results/")
            # Extraer task_ids únicos de results/
            oci_task_ids: dict[str, float] = {}
            for key in result_keys:
                # key format: results/{task_id}/moss_001.png
                parts = key.split("/")
                if len(parts) >= 2:
                    task_id = parts[1]
                    # Obtener last_modified del meta.json para ordenar
                    if task_id not in oci_task_ids:
                        meta = oci_client.get_json(f"results/{task_id}/meta.json")
                        if meta:
                            # Usar timestamp del meta o del objeto
                            from datetime import datetime
                            try:
                                ts = datetime.fromisoformat(meta.get("last_modified", "").replace("Z", "+00:00")).timestamp()
                            except Exception:
                                ts = 0
                            oci_task_ids[task_id] = ts
            
            # Añadir tareas de OCI que no estén en caché local
            for task_id, ts in sorted(oci_task_ids.items(), key=lambda x: x[1], reverse=True):
                if task_id not in seen_ids:
                    seen_ids.add(task_id)
                    result.append(
                        {
                            "task_id": task_id,
                            "status": "completed",
                            "created_at": ts,
                            "updated_at": ts,
                            "has_image": True,
                            "error": None,
                            "source": "oci_results",
                        }
                    )
        except Exception:
            # Si falla la consulta a OCI, solo devolver caché local
            pass

    # Ordenar resultado final por fecha descendente (más reciente primero)
    result.sort(key=lambda x: x.get("created_at", 0) or 0, reverse=True)

    return result