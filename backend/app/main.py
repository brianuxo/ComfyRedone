"""Punto de entrada de la aplicación FastAPI."""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.images import router as images_router
from app.api.oci_debug import router as oci_debug_router
from app.api.prompts import router as prompts_router
from app.api.tasks import router as tasks_router
from app.core.config import settings
from app.db import store as store_module

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestión del ciclo de vida de la aplicación."""
    logger.info("Iniciando ComfyUI SPA Backend...")
    store_module.init_prompt_store()
    yield
    logger.info("Apagando ComfyUI SPA Backend...")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    description="SPA para ejecución de workflows FIBO 2.0 Edit sin nodos visuales.",
    lifespan=lifespan,
)

# Middleware para capturar errores de socket en Windows (WinError 64)
@app.middleware("http")
async def windows_socket_error_handler(request: Request, call_next):
    try:
        return await call_next(request)
    except OSError as e:
        if getattr(e, "winerror", None) == 64:  # "The specified network name is no longer available"
            logger.warning(f"WinError 64 ignorado (cliente desconectado abruptamente): {e}")
            return Response(status_code=499, content="Client disconnected")
        raise

# CORS para permitir llamadas desde el frontend SPA
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rutas
app.include_router(health_router)
app.include_router(tasks_router)
app.include_router(images_router)
app.include_router(oci_debug_router)
app.include_router(prompts_router)


@app.get("/", tags=["root"])
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "comfy_url": settings.COMFY_URL,
    }


@app.get("/health/simple", tags=["health"])
async def simple_health():
    """Health check ligero sin depender de ComfyUI."""
    return {"status": "ok"}