"""Configuración centralizada mediante variables de entorno.

Todas las variables se leen con valores por defecto seguros para desarrollo.
Copiar backend/.env.example a .env y ajustar según el entorno.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List

# Cargar variables de entorno desde .env ANTES de crear Settings
# Usar ruta absoluta relativa a este archivo para encontrar backend/.env
from dotenv import load_dotenv
ENV_PATH = Path(__file__).parent.parent.parent / ".env"
load_dotenv(ENV_PATH)


class Settings:
    """Ajustes de la aplicación."""

    # --- App ---
    APP_NAME: str = "comfy-spa"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

    # --- Servidor backend ---
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # --- ComfyUI (worker local) ---
    COMFY_HOST: str = os.getenv("COMFY_HOST", "127.0.0.1")
    COMFY_PORT: int = int(os.getenv("COMFY_PORT", "8188"))

    @property
    def COMFY_URL(self) -> str:
        return f"http://{self.COMFY_HOST}:{self.COMFY_PORT}"

    @property
    def WS_URL(self) -> str:
        return f"ws://{self.COMFY_HOST}:{self.COMFY_PORT}"

    # --- CORS ---
    CORS_ORIGINS: List[str] = [
        o.strip()
        for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
        if o.strip()
    ]

    # --- OCI / Object Storage (respaldo opcional en nube, nunca disco local) ---
    # Credenciales via variables de entorno (.env), NO hardcodeadas
    OCI_NAMESPACE: str = os.getenv("OCI_NAMESPACE", "")
    OCI_BUCKET: str = os.getenv("OCI_BUCKET", "")
    OCI_REGION: str = os.getenv("OCI_REGION", "")
    OCI_ACCESS_KEY_ID: str = os.getenv("OCI_ACCESS_KEY_ID", "")
    OCI_SECRET_ACCESS_KEY: str = os.getenv("OCI_SECRET_ACCESS_KEY", "")
    OCI_ENDPOINT: str = os.getenv("OCI_ENDPOINT", "")

    # --- TTL de tareas en memoria (segundos) ---
    TASK_TTL_SECONDS: int = int(os.getenv("TASK_TTL_SECONDS", "3600"))

    # --- Timeouts ---
    COMFY_REQUEST_TIMEOUT: int = int(os.getenv("COMFY_REQUEST_TIMEOUT", "60"))
    COMFY_WS_TIMEOUT: int = int(os.getenv("COMFY_WS_TIMEOUT", "120"))
    COMFY_EXECUTION_TIMEOUT: int = int(os.getenv("COMFY_EXECUTION_TIMEOUT", "3600"))


@lru_cache()
def get_settings() -> Settings:
    """Devuelve la instancia de configuración (cached)."""
    return Settings()


settings = get_settings()