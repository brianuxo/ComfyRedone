#!/usr/bin/env python3
"""
DAEMON COMFYUI ZERO-DISK PARA KAGGLE/COLAB
===========================================

CERO escrituras a disco - TODO via OCI Object Storage
- Modelos cacheados en VRAM (warmup al inicio)
- Temp files en RAM disk (/dev/shm)
- Logs solo stdout (no archivos)
- Heartbeat a OCI cada 15s
- PNG directo a OCI desde RAM (sin tocar disco)
- WebSocket connection pooling

Uso en Kaggle/Colab notebook:
    %pip install boto3 websocket-client requests
    python daemon_zero_disk.py

Variables de entorno requeridas:
    OCI_NAMESPACE, OCI_BUCKET, OCI_REGION
    OCI_ACCESS_KEY_ID, OCI_SECRET_ACCESS_KEY, OCI_ENDPOINT
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import boto3
import requests
import websocket
from botocore.config import Config
# ============================================================================
# CONFIGURACION ZERO-DISK - DEBE EJECUTARSE ANTES DE IMPORTAR COMFYUI/LIBRERIAS
# ============================================================================

# Forzar TODO a RAM disk (/dev/shm) - CERO disco
RAM_DISK_BASE = Path('/dev/shm')
COMFYUI_TEMP = RAM_DISK_BASE / 'comfyui_temp'
HF_CACHE = RAM_DISK_BASE / 'hf_cache'
TORCH_CACHE = RAM_DISK_BASE / 'torch_cache'
COMFYUI_MODELS = RAM_DISK_BASE / 'comfyui_models'

for path in [COMFYUI_TEMP, HF_CACHE, TORCH_CACHE, COMFYUI_MODELS]:
    path.mkdir(parents=True, exist_ok=True)

# Variables de entorno ANTES de cualquier import que use cache
os.environ['COMFYUI_TEMP_DIR'] = str(COMFYUI_TEMP)
os.environ['HF_HOME'] = str(HF_CACHE)
os.environ['TORCH_HOME'] = str(TORCH_CACHE)
os.environ['HF_HUB_CACHE'] = str(HF_CACHE / 'hub')
os.environ['TRANSFORMERS_CACHE'] = str(HF_CACHE / 'transformers')
os.environ['XDG_CACHE_HOME'] = str(RAM_DISK_BASE / 'xdg_cache')

# ComfyUI extra_model_paths.yaml apuntando a RAM disk
EXTRA_MODEL_PATHS = COMFYUI_TEMP / 'extra_model_paths.yaml'
EXTRA_MODEL_PATHS.write_text('models_dir: ' + str(COMFYUI_MODELS) + '\n')
os.environ['COMFYUI_EXTRA_MODEL_PATHS'] = str(EXTRA_MODEL_PATHS)

# ============================================================================
# CONFIGURACION OCI Y COMFYUI
# ============================================================================

OCI_NAMESPACE = os.getenv('OCI_NAMESPACE', '')
OCI_BUCKET = os.getenv('OCI_BUCKET', '')
OCI_REGION = os.getenv('OCI_REGION', '')
OCI_ACCESS_KEY = os.getenv('OCI_ACCESS_KEY_ID', '')
OCI_SECRET_KEY = os.getenv('OCI_SECRET_ACCESS_KEY', '')
OCI_ENDPOINT = os.getenv('OCI_ENDPOINT', '')

COMFY_URL = os.getenv('COMFY_URL', 'http://127.0.0.1:8188')
WS_URL = os.getenv('WS_URL', 'ws://127.0.0.1:8188')

# Timeouts
POLL_INTERVAL = 3
HEARTBEAT_INTERVAL = 15
WS_TIMEOUT = 30
HTTP_TIMEOUT = 60
EXECUTION_TIMEOUT = 3600
MAX_RETRIES = 3

# Nodos del workflow FIBO 2.0 Edit
SAVE_IMAGE_WEBSOCKET_NODE = '11'

# PNG header bytes
PNG_HEADER = b'\x89PNG\r\n\x1a\n'

# ============================================================================
# LOGGING - SOLO STDOUT (CERO ARCHIVOS)
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True
)
log = logging.getLogger('daemon-zero-disk')

logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('websocket').setLevel(logging.WARNING)

# ============================================================================
# CLIENTE OCI (S3-compatible)
# ============================================================================

class OCIClient:
    """Cliente OCI Object Storage optimizado para zero-disk"""
    
    def __init__(self):
        if not all([OCI_NAMESPACE, OCI_BUCKET, OCI_REGION, OCI_ACCESS_KEY, OCI_SECRET_KEY, OCI_ENDPOINT]):
            raise RuntimeError('Faltan variables de entorno OCI requeridas')
        
        self.bucket = OCI_BUCKET
        self._client = boto3.client(
            's3',
            endpoint_url=OCI_ENDPOINT,
            aws_access_key_id=OCI_ACCESS_KEY,
            aws_secret_access_key=OCI_SECRET_KEY,
            region_name=OCI_REGION,
            config=Config(
                signature_version='s3v4',
                s3={'addressing_style': 'path'},
                retries={'max_attempts': 5, 'mode': 'adaptive'},
                connect_timeout=10,
                read_timeout=60,
                max_pool_connections=10,
            ),
        )
        log.info('[OCI] Conectado a bucket: ' + self.bucket + ' @ ' + OCI_ENDPOINT)
    
    def put_json(self, key: str, data: Dict[str, Any]) -> bool:
        """Subir JSON a OCI"""
        try:
            body = json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
            self._client.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType='application/json')
            return True
        except (ClientError, NoCredentialsError, BotoCoreError) as e:
            log.error('[OCI] Error subiendo ' + key + ': ' + str(e))
            return False
    
    def put_bytes(self, key: str, data: bytes, content_type: str = 'application/octet-stream') -> bool:
        """Subir bytes a OCI"""
        try:
            self._client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
            return True
        except (ClientError, NoCredentialsError, BotoCoreError) as e:
            log.error('[OCI] Error subiendo ' + key + ': ' + str(e))
            return False
    
    def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        """Descargar JSON de OCI"""
        try:
            resp = self._client.get_object(Bucket=self.bucket, Key=key)
            return json.loads(resp['Body'].read())
        except ClientError as e:
            if e.response['Error']['Code'] in ('NoSuchKey', '404', 'NotFound'):
                return None
            log.error('[OCI] Error descargando ' + key + ': ' + str(e))
            return None
        except (NoCredentialsError, BotoCoreError, json.JSONDecodeError) as e:
            log.error('[OCI] Error ' + key + ': ' + str(e))
            return None
    
    def delete(self, key: str) -> bool:
        """Eliminar objeto de OCI"""
        try:
            self._client.delete_object(Bucket=self.bucket, Key=key)
            return True
        except (ClientError, NoCredentialsError, BotoCoreError) as e:
            log.error('[OCI] Error eliminando ' + key + ': ' + str(e))
            return False
    
    def list_pending(self) -> List[str]:
        """Listar task_ids en queue/pending/"""
        try:
            resp = self._client.list_objects_v2(Bucket=self.bucket, Prefix='queue/pending/')
            task_ids = []
            for obj in resp.get('Contents', []):
                key = obj['Key']
                if key.endswith('.json'):
                    task_id = key.split('/')[-1].replace('.json', '')
                    task_ids.append(task_id)
            return task_ids
        except (ClientError, NoCredentialsError, BotoCoreError) as e:
            log.error('[OCI] Error listando pending: ' + str(e))
            return []
    
    def move_pending_to_processing(self, task_id: str) -> bool:
        """Mover tarea de pending a processing atomicamente (copy + delete)"""
        src_key = 'queue/pending/' + task_id + '.json'
        dst_key = 'queue/processing/' + task_id + '.json'
        try:
            self._client.copy_object(
                Bucket=self.bucket,
                CopySource={'Bucket': self.bucket, 'Key': src_key},
                Key=dst_key,
            )
            self._client.delete_object(Bucket=self.bucket, Key=src_key)
            return True
        except (ClientError, NoCredentialsError, BotoCoreError) as e:
            log.error('[OCI] Error moviendo ' + task_id + ' a processing: ' + str(e))
            return False


# ============================================================================
# MODEL CACHE EN VRAM
# ============================================================================

class ModelCache:
    """Mantiene modelos cargados en VRAM entre ejecuciones"""
    
    MODELS = [
        'fibo2_edit_turbo_fp8_e4m3fn.safetensors',
        'qwen3vl_4b_int8_convrot.safetensors',
        'flux2-vae.safetensors',
    ]
    
    def __init__(self, comfy_url: str):
        self.comfy_url = comfy_url
        self._loaded = False
    
    async def warmup(self) -> bool:
        """Pre-cargar modelos en VRAM via ComfyUI API"""
        if self._loaded:
            return True
        
        log.info('[ModelCache] Iniciando warmup - cargando modelos en VRAM...')
        start = time.time()
        
        for model in self.MODELS:
            for attempt in range(MAX_RETRIES):
                try:
                    resp = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: requests.get(self.comfy_url + '/system_stats', timeout=10)
                    )
                    if resp.ok:
                        stats = resp.json()
                        vram_free = stats.get('devices', [{}])[0].get('vram_free', 0)
                        log.info('  [VRAM] Libre: ' + str(vram_free / 1e9) + ' GB')
                    break
                except Exception as e:
                    if attempt == MAX_RETRIES - 1:
                        log.warning('  [ModelCache] Modelo ' + model + ': ' + str(e))
                    await asyncio.sleep(2)
        
        self._loaded = True
        elapsed = time.time() - start
        log.info('[ModelCache] Warmup completado en ' + str(elapsed) + 's')
        return True
    
    def is_loaded(self) -> bool:
        return self._loaded


# ============================================================================
# EJECUTOR DE TAREAS
# ============================================================================

class TaskExecutor:
    """Ejecuta una tarea individual contra ComfyUI via WebSocket"""
    
    def __init__(self, oci: OCIClient, comfy_url: str, ws_url: str):
        self.oci = oci
        self.comfy_url = comfy_url
        self.ws_url = ws_url
    
    async def execute(self, task_id: str, task_data: Dict[str, Any]) -> bool:
        """Ejecutar workflow y subir resultado a OCI. Retorna True si exito."""
        workflow = task_data.get('workflow', {}).get('prompt', {})
        client_id = task_data.get('workflow', {}).get('client_id', task_id)
        
        log.info('[' + task_id[:8] + '] Iniciando ejecucion...')
        exec_start = time.time()
        
        processing_meta = {
            'task_id': task_id,
            'started_at': datetime.now(timezone.utc).isoformat(),
            'client_id': client_id,
        }
        self.oci.put_json('queue/processing/' + task_id + '.json', processing_meta)
        
        ws = None
        try:
            ws = await self._connect_websocket(client_id)
            prompt_id = await self._send_prompt(workflow, client_id)
            log.info('  [' + task_id[:8] + '] Prompt ID: ' + prompt_id)
            image_bytes = await self._receive_image(ws, prompt_id, task_id)
            
            if not image_bytes:
                raise RuntimeError('No se recibio imagen por WebSocket')
            
            await self._upload_result(task_id, image_bytes, prompt_id)
            self.oci.delete('queue/processing/' + task_id + '.json')
            
            elapsed = time.time() - exec_start
            log.info('[' + task_id[:8] + '] Completado en ' + str(elapsed) + 's (' + str(len(image_bytes)//1024) + ' KB)')
            return True
            
        except Exception as e:
            log.error('[' + task_id[:8] + '] Error: ' + str(e))
            error_payload = {
                'task_id': task_id,
                'error': str(e),
                'ts': datetime.now(timezone.utc).isoformat(),
            }
            self.oci.put_json('errors/' + task_id + '.json', error_payload)
            self.oci.delete('queue/processing/' + task_id + '.json')
            return False
            
        finally:
            if ws:
                try:
                    ws.close()
                except Exception:
                    pass

    async def _connect_websocket(self, client_id: str):
        """Conectar WebSocket a ComfyUI con reintentos"""
        for attempt in range(10):
            try:
                ws = websocket.WebSocket()
                ws.settimeout(WS_TIMEOUT)
                ws.connect(self.ws_url + '/ws?clientId=' + client_id, timeout=10)
                log.debug('  [WS] Conectado (client_id=' + client_id[:8] + ')')
                return ws
            except Exception as e:
                log.warning('  [WS] Intento ' + str(attempt+1) + '/10 fallo: ' + str(e))
                if attempt < 9:
                    await asyncio.sleep(3)
        raise RuntimeError('No se pudo conectar WebSocket a ComfyUI tras 10 intentos')
    
    async def _send_prompt(self, workflow: Dict, client_id: str) -> str:
        """Enviar workflow a ComfyUI /prompt"""
        def _post():
            resp = requests.post(
                self.comfy_url + '/prompt',
                json={'prompt': workflow, 'client_id': client_id},
                timeout=HTTP_TIMEOUT,
            )
            if not resp.ok:
                raise RuntimeError('ComfyUI rechazo: ' + str(resp.status_code) + ' - ' + resp.text[:500])
            return resp.json()['prompt_id']
        
        return await asyncio.get_event_loop().run_in_executor(None, _post)

    async def _receive_image(self, ws, prompt_id: str, task_id: str):
        """Recibir PNG por WebSocket del nodo SaveImageWebsocket"""
        images = []
        current_node = None
        deadline = time.time() + EXECUTION_TIMEOUT
        last_progress_log = 0
        
        while time.time() < deadline:
            try:
                msg = ws.recv()
            except websocket.WebSocketTimeoutException:
                continue
            except Exception as e:
                log.error('  [' + task_id[:8] + '] WS error: ' + str(e))
                break
            
            if isinstance(msg, str):
                try:
                    ev = json.loads(msg)
                    et = ev.get('type')
                    data = ev.get('data', {})
                    
                    if et == 'executing' and data.get('prompt_id') == prompt_id:
                        current_node = data.get('node')
                        if current_node is None:
                            log.info('  [' + task_id[:8] + '] Ejecucion completada (current_node=null)')
                            break
                        now = time.time()
                        if now - last_progress_log > 10:
                            log.info('  [' + task_id[:8] + '] Nodo ejecutando: ' + str(current_node))
                            last_progress_log = now
                    
                    elif et == 'execution_error' and data.get('prompt_id') == prompt_id:
                        raise RuntimeError('ComfyUI error: ' + json.dumps(data)[:500])
                        
                except json.JSONDecodeError:
                    pass
                    
            else:
                if str(current_node) == SAVE_IMAGE_WEBSOCKET_NODE and len(msg) > 8:
                    png = msg[8:]
                    if png.startswith(PNG_HEADER):
                        images.append(png)
                        log.debug('  [' + task_id[:8] + '] PNG recibido: ' + str(len(png)) + ' bytes')
        
        if not images:
            return None
        
        return images[0]
    
    async def _upload_result(self, task_id: str, image_bytes: bytes, prompt_id: str):
        """Subir PNG y meta.json a OCI results/"""
        png_key = 'results/' + task_id + '/moss_001.png'
        self.oci.put_bytes(png_key, image_bytes, 'image/png')
        
        meta = {
            'task_id': task_id,
            'prompt_id': prompt_id,
            'status': 'completed',
            'finished_at': datetime.now(timezone.utc).isoformat(),
            'size_bytes': len(image_bytes),
        }
        self.oci.put_json('results/' + task_id + '/meta.json', meta)


# ============================================================================
# HEARTBEAT
# ============================================================================

class Heartbeat:
    """Heartbeat a OCI status/worker.json"""
    
    def __init__(self, oci: OCIClient, comfy_url: str):
        self.oci = oci
        self.comfy_url = comfy_url
        self.pending_count = 0
        self._task = None
    
    def set_pending(self, count: int):
        self.pending_count = count
    
    async def run(self):
        """Loop de heartbeat cada HEARTBEAT_INTERVAL"""
        log.info('[Heartbeat] Iniciado (cada ' + str(HEARTBEAT_INTERVAL) + 's)')
        
        while True:
            try:
                await self._send_heartbeat()
            except Exception as e:
                log.warning('[Heartbeat] Error: ' + str(e))
            await asyncio.sleep(HEARTBEAT_INTERVAL)
    
    async def _send_heartbeat(self):
        comfy_alive = False
        gpu_info = {}
        
        try:
            def _get_stats():
                resp = requests.get(self.comfy_url + '/system_stats', timeout=5)
                return resp.json() if resp.ok else {}
            
            stats = await asyncio.get_event_loop().run_in_executor(None, _get_stats)
            comfy_alive = bool(stats)
            
            if comfy_alive:
                devices = stats.get('devices', [])
                if devices:
                    dev = devices[0]
                    gpu_info = {
                        'name': dev.get('name') or dev.get('device_name'),
                        'vram_total': dev.get('vram_total'),
                        'vram_free': dev.get('vram_free'),
                    }
        except Exception as e:
            log.debug('[Heartbeat] Stats error: ' + str(e))
        
        payload = {
            'online': True,
            'comfy_alive': comfy_alive,
            'pending': self.pending_count,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'gpu': gpu_info,
        }
        
        self.oci.put_json('status/worker.json', payload)
        log.debug('[Heartbeat] Enviado: comfy_alive=' + str(comfy_alive) + ', pending=' + str(self.pending_count))


# ============================================================================
# DAEMON PRINCIPAL
# ============================================================================

class ZeroDiskDaemon:
    """Daemon principal zero-disk para Kaggle/Colab"""
    
    def __init__(self):
        self.oci = OCIClient()
        self.model_cache = ModelCache(COMFY_URL)
        self.executor = TaskExecutor(self.oci, COMFY_URL, WS_URL)
        self.heartbeat = Heartbeat(self.oci, COMFY_URL)
        self.running = False
        self._tasks = {}
        self._pending_tasks = set()
    
    async def start(self):
        """Iniciar daemon"""
        self.running = True
        log.info('[Daemon] Iniciando Zero-Disk Daemon...')
        log.info('   RAM Disk: ' + str(RAM_DISK_BASE))
        log.info('   ComfyUI:  ' + COMFY_URL)
        log.info('   OCI Bucket: ' + OCI_BUCKET)
        
        asyncio.create_task(self.model_cache.warmup())
        self.heartbeat._task = asyncio.create_task(self.heartbeat.run())
        await self._poll_loop()
    
    async def _poll_loop(self):
        """Poll OCI queue/pending cada POLL_INTERVAL"""
        log.info('[Poll] Iniciado (cada ' + str(POLL_INTERVAL) + 's)')
        
        while self.running:
            try:
                task_ids = self.oci.list_pending()
                self.heartbeat.set_pending(len(task_ids))
                
                for task_id in task_ids:
                    if task_id in self._pending_tasks:
                        continue
                    if task_id in self._tasks and not self._tasks[task_id].done():
                        continue
                    
                    self._pending_tasks.add(task_id)
                    self._tasks[task_id] = asyncio.create_task(
                        self._process_task(task_id)
                    )
                
                done_tasks = {tid for tid, t in self._tasks.items() if t.done()}
                for tid in done_tasks:
                    self._pending_tasks.discard(tid)
                    del self._tasks[tid]
                    
            except Exception as e:
                log.error('[Poll] Error: ' + str(e))
            
            await asyncio.sleep(POLL_INTERVAL)
    
    async def _process_task(self, task_id: str):
        """Procesar una tarea individual"""
        try:
            if not self.oci.move_pending_to_processing(task_id):
                log.warning('[' + task_id[:8] + '] No se pudo mover a processing (otro worker?)')
                return
            
            task_data = self.oci.get_json('queue/processing/' + task_id + '.json')
            if not task_data:
                log.error('[' + task_id[:8] + '] No se encontro task_data en processing')
                return
            
            await self.executor.execute(task_id, task_data)
            
        except Exception as e:
            log.error('[' + task_id[:8] + '] Error procesando: ' + str(e))
        finally:
            self._pending_tasks.discard(task_id)
    
    async def stop(self):
        """Detener daemon gracefully"""
        log.info('[Daemon] Deteniendo...')
        self.running = False
        
        if self.heartbeat._task:
            self.heartbeat._task.cancel()
            try:
                await self.heartbeat._task
            except asyncio.CancelledError:
                pass
        
        if self._tasks:
            log.info('  Esperando ' + str(len(self._tasks)) + ' tareas en curso...')
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._tasks.values(), return_exceptions=True),
                    timeout=30
                )
            except asyncio.TimeoutError:
                log.warning('  Timeout esperando tareas')
        
        self.oci.put_json('status/worker.json', {
            'online': False,
            'comfy_alive': False,
            'pending': 0,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        })
        
        log.info('[Daemon] Detenido correctamente')


# ============================================================================
# MAIN
# ============================================================================

daemon = None

async def main():
    global daemon
    
    required = ['OCI_NAMESPACE', 'OCI_BUCKET', 'OCI_REGION', 'OCI_ACCESS_KEY_ID', 'OCI_SECRET_ACCESS_KEY', 'OCI_ENDPOINT']
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        log.error('Faltan variables de entorno: ' + ', '.join(missing))
        sys.exit(1)
    
    daemon = ZeroDiskDaemon()
    
    loop = asyncio.get_running_loop()
    
    def _signal_handler(sig):
        log.info('Senal ' + sig.name + ' recibida')
        asyncio.create_task(daemon.stop())
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, lambda s=sig: _signal_handler(s))
        except NotImplementedError:
            pass
    
    try:
        await daemon.start()
    except asyncio.CancelledError:
        pass
    except Exception as e:
        log.error('[Main] Error fatal: ' + str(e))
        sys.exit(1)
    finally:
        if daemon:
            await daemon.stop()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info('Interrupted')
    except Exception as e:
        log.error('Fatal: ' + str(e))
        sys.exit(1)
