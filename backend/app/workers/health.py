"""
Comprobación de salud del worker vía OCI.

El backend NO se conecta directamente a ComfyUI. En su lugar, lee el archivo
`status/worker.json` del bucket OCI, que el daemon de ComfyUI en Kaggle/Colab
escribe cada 20 segundos con su estado (online, comfy_alive, pending, timestamp).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict

from app.storage.oci_client import oci_client

logger = logging.getLogger(__name__)

WORKER_STATUS_KEY = "status/worker.json"

# Si el heartbeat tiene más de esto de antigüedad, el worker se considera offline
HEARTBEAT_TTL_SECONDS = 60


class WorkerHealth:
    """Encapsula la comprobación de salud del worker mediante OCI."""

    def __init__(self) -> None:
        self.oci = oci_client

    def check(self) -> Dict[str, Any]:
        """Devuelve el estado del worker leído desde OCI.

        Ejemplo de respuesta:
        {
            "online": True,
            "comfy_alive": True,
            "comfy_url": "http://127.0.0.1:8188",
            "gpu_name": "NVIDIA ...",
            "vram_total": 16192,
            "vram_free": 8192,
            "pending_tasks": 0,
            "timestamp": "2026-11-08T12:00:00Z",
            "oci_online": True,
            "error": None
        }
        """
        result: Dict[str, Any] = {
            "online": False,
            "comfy_alive": False,
            "comfy_url": None,
            "gpu_name": None,
            "vram_total": None,
            "vram_free": None,
            "pending_tasks": None,
            "timestamp": None,
            "oci_online": False,
            "error": None,
        }

        # Verificar que OCI esté configurado y accesible
        if not self.oci.is_configured():
            result["error"] = "OCI no configurado (faltan credenciales)"
            logger.warning(result["error"])
            return result

        if not self.oci.bucket_exists():
            result["error"] = f"Bucket OCI no accesible: {self.oci.bucket}"
            logger.warning(result["error"])
            return result

        result["oci_online"] = True

        # Leer el heartbeat del worker desde OCI
        worker_status = self.oci.get_json(WORKER_STATUS_KEY)
        if worker_status is None:
            result["error"] = "No se encontró status/worker.json en OCI (worker no ha escrito heartbeat)"
            logger.warning(result["error"])
            return result

        # Mapear campos del heartbeat de OCI al formato de respuesta
        heartbeat_online = worker_status.get("online", False)
        result["comfy_alive"] = worker_status.get("comfy_alive", False)
        result["pending_tasks"] = worker_status.get("pending")
        ts_str = worker_status.get("ts") or worker_status.get("timestamp")
        result["timestamp"] = ts_str
        result["comfy_url"] = "http://127.0.0.1:8188"  # URL conocida del worker en Kaggle

        # Verificar que el heartbeat no esté expirado (más de 60s sin actualizar)
        heartbeat_expired = True
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                age_seconds = (now - ts).total_seconds()
                heartbeat_expired = age_seconds > HEARTBEAT_TTL_SECONDS
                if heartbeat_expired:
                    logger.warning(
                        f"Heartbeat expirado: {age_seconds:.0f}s de antigüedad "
                        f"(máximo {HEARTBEAT_TTL_SECONDS}s)"
                    )
            except Exception as exc:
                logger.warning(f"No se pudo parsear el timestamp del heartbeat: {exc}")
                heartbeat_expired = True

        # El worker está online solo si el heartbeat dice online Y no está expirado
        result["online"] = heartbeat_online and not heartbeat_expired

        # Opcional: extraer GPU info si está presente en el heartbeat
        if isinstance(worker_status.get("gpu"), dict):
            gpu = worker_status["gpu"]
            result["gpu_name"] = gpu.get("name") or gpu.get("device_name")
            result["vram_total"] = gpu.get("vram_total") or gpu.get("total_vram")
            result["vram_free"] = gpu.get("vram_free") or gpu.get("free_vram")

        return result

    def is_online(self) -> bool:
        """Devuelve True si el worker responde vía OCI."""
        return self.check().get("online", False)


# Instancia reutilizable
worker_health = WorkerHealth()