#!/usr/bin/env python3
"""
Ejecutor WebSocket común para ComfyUI
Zero-disk, reutilizable entre Kaggle y Colab
"""

import asyncio
import json
import logging
import uuid
import websocket
import requests
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum

log = logging.getLogger("ws_executor")

class WSState(Enum):
    CONNECTING = "connecting"
    CONNECTED = "connected"
    EXECUTING = "executing"
    COMPLETED = "completed"
    ERROR = "error"
    CLOSED = "closed"


@dataclass
class ExecutionResult:
    success: bool
    prompt_id: Optional[str] = None
    images: list = None
    error: Optional[str] = None
    execution_time: float = 0.0


class WSExecutor:
    def __init__(self, comfy_url: str, ws_url: str, config=None):
        self.comfy_url = comfy_url
        self.ws_url = ws_url
        self.config = config
        
        self.ws_timeout = config.ws_timeout if config else 30
        self.http_timeout = config.http_timeout if config else 60
        self.execution_timeout = config.execution_timeout if config else 3600
        self.max_ws_retries = 10
        
        self.save_image_ws_node = "11"
        self.png_header = b'\x89PNG\r\n\x1a\n'
        
        self.state = WSState.CLOSED
        self._ws = None
        self._client_id = None
    
    async def connect(self, client_id: str = None):
        self._client_id = client_id or str(uuid.uuid4())
        for attempt in range(self.max_ws_retries):
            try:
                self._ws = websocket.WebSocket()
                self._ws.settimeout(self.ws_timeout)
                self._ws.connect(self.ws_url + "/ws?clientId=" + self._client_id, timeout=10)
                log.info("[WSExecutor] Conectado (client_id=" + self._client_id[:8] + ")")
                return True
            except Exception as e:
                log.warning("[WSExecutor] Intento " + str(attempt+1) + "/" + str(self.max_ws_retries) + " fallo: " + str(e))
                if attempt < self.max_ws_retries - 1:
                    await asyncio.sleep(3)
        log.error("[WSExecutor] No se pudo conectar WebSocket")
        return False

    async def execute(self, workflow: Dict, client_id: str = None):
        start_time = __import__("time").time()
        
        if not await self.connect(client_id):
            return ExecutionResult(success=False, error="No se pudo conectar WebSocket")
        
        try:
            prompt_id = await self._send_prompt(workflow)
            log.info("[WSExecutor] Prompt ID: " + prompt_id)
            
            images = await self._receive_images(prompt_id)
            
            if not images:
                return ExecutionResult(
                    success=False, 
                    prompt_id=prompt_id, 
                    error="No se recibio imagen por WebSocket"
                )
            
            elapsed = __import__("time").time() - start_time
            return ExecutionResult(
                success=True,
                prompt_id=prompt_id,
                images=images,
                execution_time=elapsed
            )
            
        except Exception as e:
            elapsed = __import__("time").time() - start_time
            log.error("[WSExecutor] Error: " + str(e))
            return ExecutionResult(
                success=False,
                error=str(e),
                execution_time=elapsed
            )
        finally:
            await self.close()
    
    async def _send_prompt(self, workflow: Dict):
        def _post():
            resp = requests.post(
                self.comfy_url + '/prompt',
                json={'prompt': workflow, 'client_id': self._client_id},
                timeout=self.http_timeout,
            )
            if not resp.ok:
                raise RuntimeError("ComfyUI rechazo: " + str(resp.status_code) + " - " + resp.text[:500])
            return resp.json()['prompt_id']
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _post)

    async def _receive_images(self, prompt_id):
        images = []
        current_node = None
        deadline = __import__("time").time() + self.execution_timeout
        last_progress_log = 0
        
        while __import__("time").time() < deadline:
            try:
                msg = self._ws.recv()
            except websocket.WebSocketTimeoutException:
                continue
            except Exception as e:
                log.error("[WSExecutor] WS error: " + str(e))
                break
            
            if isinstance(msg, str):
                try:
                    ev = json.loads(msg)
                    et = ev.get('type')
                    data = ev.get('data', {})
                    
                    if et == 'executing' and data.get('prompt_id') == prompt_id:
                        current_node = data.get('node')
                        if current_node is None:
                            log.info("[WSExecutor] Ejecucion completada")
                            break
                        now = __import__("time").time()
                        if now - last_progress_log > 10:
                            log.info("[WSExecutor] Nodo ejecutando: " + str(current_node))
                            last_progress_log = now
                    
                    elif et == 'execution_error' and data.get('prompt_id') == prompt_id:
                        raise RuntimeError("ComfyUI error: " + json.dumps(data)[:500])
                        
                except json.JSONDecodeError:
                    pass
                    
            else:
                if str(current_node) == "11" and len(msg) > 8:
                    png = msg[8:]
                    if png.startswith(b'\x89PNG\r\n\x1a\n'):
                        images.append(png)
                        log.debug("[WSExecutor] PNG recibido: " + str(len(png)) + " bytes")
        
        return images
    
    async def close(self):
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None
        self.state = WSState.CLOSED


def create_ws_executor(comfy_url: str, ws_url: str, config=None):
    return WSExecutor(comfy_url, ws_url, config)
