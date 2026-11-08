"""
Executor del workflow FIBO 2.0 Txt2Img.

Ejecuta el workflow de generación desde cero (txt2img) contra ComfyUI.
Diferencia con Edit: NO hay imagen de entrada, es generación pura desde texto.
"""

from __future__ import annotations

import base64
import json
import logging
import time
import uuid
from typing import Any, Dict, Optional

import requests
import websocket

from app.core.config import settings
from app.db.store import task_store
from app.workflows.fibo2_txt2img.builder import build_workflow

logger = logging.getLogger(__name__)


class ComfyUIExecutor:
    """Ejecuta un workflow de FIBO 2.0 Txt2Img contra ComfyUI local."""

    def __init__(self) -> None:
        self.ws_url = settings.WS_URL
        self.http_url = settings.COMFY_URL
        self.timeout = settings.COMFY_REQUEST_TIMEOUT
        self.ws_timeout = settings.COMFY_WS_TIMEOUT
        self.execution_timeout = settings.COMFY_EXECUTION_TIMEOUT

    def execute(
        self,
        params: dict,
        task_id: str,
    ) -> Dict[str, Any]:
        """Ejecuta el workflow txt2img y devuelve el resultado con la imagen en base64."""
        workflow = build_workflow(params)
        client_id = str(uuid.uuid4())

        # Guardar el prompt enviado para referencia
        task_store.update_status(task_id, "running")

        ws: Optional[websocket.WebSocket] = None
        try:
            # Conectar WebSocket con reintentos
            ws = self._connect_websocket(client_id)

            # Enviar ejecución a ComfyUI
            resp = requests.post(
                f"{self.http_url}/prompt",
                json={"prompt": workflow, "client_id": client_id},
                timeout=self.timeout,
            )
            if not resp.ok:
                raise RuntimeError(
                    f"ComfyUI rechazó la ejecución: {resp.text[:3000]}"
                )
            prompt_id = resp.json()["prompt_id"]

            # Escuchar mensajes por WebSocket
            images: list[bytes] = []
            current_node: Optional[str] = None
            completed = False
            error: Optional[str] = None
            deadline = time.time() + self.execution_timeout

            # Nodo guardador (SaveImageWebsocket) es el "11"
            save_node_id = "11"

            while time.time() < deadline:
                # Comprobar cancelación externa (opcional, por ahora sin cola S3)
                try:
                    msg = ws.recv()
                except websocket.WebSocketTimeoutException:
                    continue

                if isinstance(msg, str):
                    ev = json.loads(msg)
                    et = ev.get("type")
                    data = ev.get("data", {})
                    if et == "executing" and data.get("prompt_id") == prompt_id:
                        current_node = data.get("node")
                        if current_node is None:
                            completed = True
                            break
                    elif et == "execution_error" and data.get("prompt_id") == prompt_id:
                        error = json.dumps(data, ensure_ascii=False)[:5000]
                        break
                else:
                    # Mensaje binario: imagen del nodo SaveImageWebsocket
                    if str(current_node) == save_node_id and len(msg) > 8:
                        png = msg[8:]  # Saltar los primeros 8 bytes de prefijo
                        if png.startswith(b"\x89PNG\r\n\x1a\n"):
                            images.append(png)

            if error:
                task_store.update_status(task_id, "failed", error=error)
                raise RuntimeError("Error en workflow: " + error)
            if not completed:
                task_store.update_status(task_id, "failed", error="Timeout")
                raise TimeoutError("La ejecución no finalizó a tiempo.")
            if not images:
                task_store.update_status(task_id, "failed", error="Sin imágenes")
                raise RuntimeError("No se recibió ninguna imagen PNG por WebSocket.")

            # Devolver la primera imagen como base64 (en memoria)
            image_b64 = base64.b64encode(images[0]).decode("utf-8")
            task_store.update_status(
                task_id, "completed", image_b64=image_b64
            )

            return {
                "task_id": task_id,
                "prompt_id": prompt_id,
                "image_b64": image_b64,
                "status": "completed",
            }

        finally:
            if ws:
                try:
                    ws.close()
                except Exception:  # noqa: BLE001
                    pass

    def _connect_websocket(self, client_id: str) -> websocket.WebSocket:
        ws = None
        last_err: Optional[Exception] = None
        for intento in range(10):
            try:
                ws = websocket.WebSocket()
                ws.settimeout(self.ws_timeout)
                ws.connect(f"{self.ws_url}/ws?clientId={client_id}", timeout=30)
                return ws
            except Exception as exc:
                last_err = exc
                if ws:
                    try:
                        ws.close()
                    except Exception:  # noqa: BLE001
                        pass
                ws = None
                time.sleep(3)
        raise RuntimeError(f"No se pudo conectar al WebSocket de ComfyUI: {last_err}")


# Instancia reutilizable
executor = ComfyUIExecutor()