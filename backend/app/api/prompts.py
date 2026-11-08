"""
Endpoints para gestión de prompts guardados.
Permite listar, crear, obtener, actualizar y eliminar prompts con título.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.db import store as store_module

router = APIRouter(prefix="/api/prompts", tags=["prompts"])


class PromptCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=100, description="Título del prompt")
    prompt: str = Field(..., min_length=1, max_length=2000, description="Prompt positivo")
    negative_prompt: str = Field(default="", max_length=2000, description="Prompt negativo")


class PromptUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    prompt: str = Field(..., min_length=1, max_length=2000)
    negative_prompt: str = Field(default="", max_length=2000)


class PromptResponse(BaseModel):
    id: str
    title: str
    prompt: str
    negative_prompt: str
    created_at: float
    updated_at: float


def _ensure_store() -> None:
    if store_module.prompt_store is None:
        store_module.init_prompt_store()


@router.get("", response_model=list[PromptResponse], summary="Listar prompts guardados")
async def list_prompts() -> list[PromptResponse]:
    """Lista todos los prompts guardados, ordenados por fecha de actualización descendente."""
    _ensure_store()
    prompts = store_module.prompt_store.list()
    return [
        PromptResponse(
            id=p.id,
            title=p.title,
            prompt=p.prompt,
            negative_prompt=p.negative_prompt,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in prompts
    ]


@router.post("", response_model=PromptResponse, status_code=201, summary="Crear prompt guardado")
async def create_prompt(data: PromptCreate) -> PromptResponse:
    """Guarda un nuevo prompt con su título."""
    _ensure_store()
    prompt_id = store_module.prompt_store.create(
        title=data.title,
        prompt=data.prompt,
        negative_prompt=data.negative_prompt,
    )
    prompt = store_module.prompt_store.get(prompt_id)
    if not prompt:
        raise HTTPException(status_code=500, detail="Error al crear prompt")
    return PromptResponse(
        id=prompt.id,
        title=prompt.title,
        prompt=prompt.prompt,
        negative_prompt=prompt.negative_prompt,
        created_at=prompt.created_at,
        updated_at=prompt.updated_at,
    )


@router.get("/{prompt_id}", response_model=PromptResponse, summary="Obtener prompt por ID")
async def get_prompt(prompt_id: str) -> PromptResponse:
    """Obtiene un prompt guardado por su ID."""
    _ensure_store()
    prompt = store_module.prompt_store.get(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt no encontrado")
    return PromptResponse(
        id=prompt.id,
        title=prompt.title,
        prompt=prompt.prompt,
        negative_prompt=prompt.negative_prompt,
        created_at=prompt.created_at,
        updated_at=prompt.updated_at,
    )


@router.put("/{prompt_id}", response_model=PromptResponse, summary="Actualizar prompt")
async def update_prompt(prompt_id: str, data: PromptUpdate) -> PromptResponse:
    """Actualiza un prompt existente."""
    _ensure_store()
    success = store_module.prompt_store.update(
        prompt_id=prompt_id,
        title=data.title,
        prompt=data.prompt,
        negative_prompt=data.negative_prompt,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Prompt no encontrado")
    prompt = store_module.prompt_store.get(prompt_id)
    return PromptResponse(
        id=prompt.id,
        title=prompt.title,
        prompt=prompt.prompt,
        negative_prompt=prompt.negative_prompt,
        created_at=prompt.created_at,
        updated_at=prompt.updated_at,
    )


@router.delete("/{prompt_id}", summary="Eliminar prompt")
async def delete_prompt(prompt_id: str) -> dict:
    """Elimina un prompt guardado."""
    _ensure_store()
    success = store_module.prompt_store.delete(prompt_id)
    if not success:
        raise HTTPException(status_code=404, detail="Prompt no encontrado")
    return {"ok": True, "message": "Prompt eliminado"}