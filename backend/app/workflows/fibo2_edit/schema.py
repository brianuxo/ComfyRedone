"""Schema Pydantic para parámetros de entrada de FIBO 2.0 Edit."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field, validator


class Fibo2EditRequest(BaseModel):
    """Parámetros ajustables por el usuario para FIBO 2.0 Edit."""

    prompt: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Instrucción de edición (prompt de FIBO 2.0 Edit)",
    )
    image_b64: Optional[str] = Field(
        None,
        description="Imagen de entrada en base64 (solo modo edit). Se envía al nodo LoadImageRAM.",
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

    @validator("image_b64")
    def _validate_b64(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        # Validación básica de que parece base64
        import base64

        try:
            base64.b64decode(v, validate=True)
        except Exception as exc:
            raise ValueError("image_b64 no es base64 válido") from exc
        return v


class Fibo2EditResponse(BaseModel):
    task_id: str
    status: str
    created_at: str