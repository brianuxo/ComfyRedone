"""Schemas Pydantic para workflows Moss Image y FIBO 2.0."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class Fibo2Txt2ImgRequest(BaseModel):
    """Parámetros ajustables por el usuario para FIBO 2.0 Txt2Img (generación desde cero)."""

    prompt: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Prompt positivo (instrucción de generación para FIBO 2.0 Txt2Img)",
    )
    negative_prompt: str = Field(
        default="",
        max_length=2000,
        description="Prompt negativo (cosas a evitar en la generación)",
    )
    loras: List[str] = Field(
        default_factory=list,
        max_items=5,
        description="Lista de nombres de LoRA encadenadas (imitando AusBoss)",
    )
    seed: Optional[int] = Field(
        None,
        ge=0,
        description="Seed para el ruido aleatorio. Si no se indica, se genera automáticamente.",
    )
    steps: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Número de pasos de muestreo",
    )
    scheduler: str = Field(
        default="euler",
        description="Scheduler propio de FIBO (ej: euler)",
    )
    guidance: float = Field(
        default=3.5,
        ge=0.0,
        le=20.0,
        description="Escala de guía (BasicGuider)",
    )
    width: int = Field(default=1024, ge=256, le=2048, description="Ancho del latent vacío")
    height: int = Field(default=1024, ge=256, le=2048, description="Alto del latent vacío")


class Fibo2Txt2ImgResponse(BaseModel):
    task_id: str
    status: str
    created_at: str


class MossImageRequest(BaseModel):
    """Parámetros ajustables por el usuario para Moss Image (text-to-image)."""

    prompt: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Prompt positivo para Moss Image",
    )
    negative_prompt: str = Field(
        default="mutated,missing limb,malformed hands,cross-eyed,mutated hands and fingers,malformed limbs,mutation,ugly,floating limbs,bad hands,missing fingers,disconnected limbs,extra limbs,extra fingers,extra arms,extra legs,watermark,text,signature,logo,username,blurry,low quality,worst quality,normal quality",
        max_length=2000,
        description="Prompt negativo (cosas a evitar en la generación)",
    )
    loras: List[str] = Field(
        default_factory=list,
        max_items=5,
        description="Lista de nombres de LoRA encadenadas",
    )
    seed: Optional[int] = Field(
        None,
        ge=0,
        description="Seed para el ruido aleatorio. Si no se indica, se genera automáticamente.",
    )
    steps: int = Field(
        default=8,
        ge=1,
        le=100,
        description="Número de pasos de muestreo (Moss usa 8 pasos)",
    )
    scheduler: str = Field(
        default="simple",
        description="Scheduler (ej: simple, normal, karras)",
    )
    guidance: float = Field(
        default=1.0,
        ge=0.0,
        le=20.0,
        description="Escala de guía CFG (Moss usa 1.0)",
    )
    width: int = Field(default=1024, ge=256, le=2048, description="Ancho de la imagen")
    height: int = Field(default=1440, ge=256, le=2048, description="Alto de la imagen")


class MossImageResponse(BaseModel):
    task_id: str
    status: str
    created_at: str