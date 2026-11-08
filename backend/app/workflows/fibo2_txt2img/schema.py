"""
Schema Pydantic para parámetros de entrada de FIBO 2.0 Txt2Img (generación desde cero).
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field, validator


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