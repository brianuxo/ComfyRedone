"""Endpoint para subir imagen a memoria (base64)."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.store import task_store, init_task_store

router = APIRouter(prefix="/api/images", tags=["images"])


class ImageUploadRequest(BaseModel):
    image_b64: str


class ImageUploadResponse(BaseModel):
    image_id: str
    image_b64: str
    size_bytes: int


def _ensure_store() -> None:
    if task_store is None:
        from app.core.config import settings

        init_task_store(ttl_seconds=settings.TASK_TTL_SECONDS)


@router.post("/upload", response_model=ImageUploadResponse, summary="Subir imagen a memoria")
async def upload_image(request: ImageUploadRequest) -> Any:
    """Guarda una imagen base64 en memoria y devuelve un image_id.

    La imagen nunca toca el disco del worker.
    """
    _ensure_store()
    import base64

    try:
        raw = base64.b64decode(request.image_b64, validate=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="image_b64 inválido") from exc

    image_id = task_store.create({"image_b64": request.image_b64})
    return ImageUploadResponse(
        image_id=image_id,
        image_b64=request.image_b64,
        size_bytes=len(raw),
    )