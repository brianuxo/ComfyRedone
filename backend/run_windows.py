#!/usr/bin/env python
"""
Entry point para Windows - Configura event loop policy ANTES de importar uvicorn/FastAPI.
Debe ejecutarse ANTES de cualquier otro import que cree event loops.
"""
import sys
import asyncio

# IMPORTANTE: Configurar policy ANTES de cualquier import que use asyncio
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    print("[OK] WindowsSelectorEventLoopPolicy configurado")

# Ahora importar y ejecutar uvicorn
if __name__ == "__main__":
    import uvicorn
    from app.core.config import settings
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        loop="asyncio",
        log_level="info",
    )