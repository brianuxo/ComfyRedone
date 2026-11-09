#!/usr/bin/env python3
"""
DAEMON COLAB - ZERO-DISK PARA GOOGLE COLAB (1x T4, 12GB RAM, 1 CPU/2 hilos)
============================================================================

Optimizado para entorno Google Colab:
- 1x T4 = 16GB VRAM
- 12GB RAM sistema
- 1 core CPU / 2 hilos
- CERO escrituras a disco (todo en /dev/shm + OCI)
- Offloading CPU obligatorio (VRAM limitada)
- Workers secuenciales (solo 1 hilo CPU disponible)

Variables de entorno requeridas:
    OCI_NAMESPACE, OCI_BUCKET, OCI_REGION
    OCI_ACCESS_KEY_ID, OCI_SECRET_ACCESS_KEY, OCI_ENDPOINT
    HF_TOKEN (para descarga modelos HuggingFace)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import boto3
import requests
import websocket
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

# Anadir path a modulos comunes
COMMON_PATH = Path(__file__).parent.parent / "common"
sys.path.insert(0, str(COMMON_PATH))

from hardware_detect import HardwareConfig, build_config_for_environment
from oci_client import OCIClient, create_oci_client
from model_manager import ModelManager, ModelInfo, ModelState
from ws_executor import WSExecutor, ExecutionResult, create_ws_executor

# ============================================================================
# CONFIGURACION COLAB - HARDCODEADA PARA ENTORNO COLAB
# ============================================================================

OCI_NAMESPACE = os.getenv("OCI_NAMESPACE", "axw2jxhksso4")
OCI_BUCKET = os.getenv("OCI_BUCKET", "comfyuiOut")
OCI_REGION = os.getenv("OCI_REGION", "sa-santiago-1")
OCI_ACCESS_KEY = os.getenv("OCI_ACCESS_KEY_ID")
OCI_SECRET_KEY = os.getenv("OCI_SECRET_ACCESS_KEY")
OCI_ENDPOINT = os.getenv("OCI_ENDPOINT")

HF_TOKEN = os.getenv("HF_TOKEN")

COMFY_HOST = "127.0.0.1"
COMFY_PORT = 8188
COMFY_URL = f"http://{COMFY_HOST}:{COMFY_PORT}"
WS_URL = f"ws://{COMFY_HOST}:{COMFY_PORT}"

# Paths en RAM disk (zero disk)
BASE_DIR = Path("/dev/shm")
COMFY_DIR = BASE_DIR / "comfyui"
MODELS_DIR = COMFY_DIR / "models"
COMFY_INPUT_DIR = COMFY_DIR / "input"

# Timeouts y configuracion optimizada para Colab
POLL_INTERVAL = 10          # Menos polling para ahorrar CPU (1 core)
HEARTBEAT_INTERVAL = 30     # Menos heartbeats
WS_TIMEOUT = 180            # Mas tiempo para Colab
HTTP_TIMEOUT = 120
EXECUTION_TIMEOUT = 3600
MAX_WS_RETRIES = 10

# Nodos del workflow FIBO 2.0 Edit
SAVE_IMAGE_WEBSOCKET_NODE = "11"
PNG_HEADER = b"\x89PNG\r\n\x1a\n"

# OCI Prefixes
OCI_PREFIX_MANIFEST = "manifest/models.json"
OCI_PREFIX_QUEUE = "queue/pending"
OCI_PREFIX_RESULTS = "results"
OCI_PREFIX_PROCESSING = "queue/processing"
OCI_PREFIX_INPUTS = "inputs"
OCI_PREFIX_MGR_QUEUE = "manager/queue"
OCI_PREFIX_MGR_DONE = "manager/done"

OCI_NAMESPACE = os.getenv("OCI_NAMESPACE", "axw2jxhksso4")
OCI_BUCKET = os.getenv("OCI_BUCKET", "comfyuiOut")
OCI_REGION = os.getenv("OCI_REGION", "sa-santiago-1")
OCI_ACCESS_KEY = os.getenv("OCI_ACCESS_KEY_ID")
OCI_SECRET_KEY = os.getenv("OCI_SECRET_ACCESS_KEY")
OCI_ENDPOINT = os.getenv("OCI_ENDPOINT")
HF_TOKEN = os.getenv("HF_TOKEN")

COMFY_HOST = "127.0.0.1"
COMFY_PORT = 8188
COMFY_URL = f"http://{COMFY_HOST}:{COMFY_PORT}"
WS_URL = f"ws://{COMFY_HOST}:{COMFY_PORT}"

BASE_DIR = Path("/dev/shm")
COMFY_DIR = BASE_DIR / "comfyui"
MODELS_DIR = COMFY_DIR / "models"
COMFY_INPUT_DIR = COMFY_DIR / "input"

SAVE_IMAGE_WEBSOCKET_NODE = "11"
PNG_HEADER = b"\x89PNG\r\n\x1a\n"

OCI_PREFIX_MANIFEST = "manifest/models.json"
OCI_PREFIX_QUEUE = "queue/pending"
OCI_PREFIX_RESULTS = "results"
OCI_PREFIX_PROCESSING = "queue/processing"
OCI_PREFIX_INPUTS = "inputs"
OCI_PREFIX_MGR_QUEUE = "manager/queue"
OCI_PREFIX_MGR_DONE = "manager/done"

OCI_NAMESPACE = os.getenv("OCI_NAMESPACE", "axw2jxhksso4")
OCI_BUCKET = os.getenv("OCI_BUCKET", "comfyuiOut")
OCI_REGION = os.getenv("OCI_REGION", "sa-santiago-1")
OCI_ACCESS_KEY = os.getenv("OCI_ACCESS_KEY_ID")
OCI_SECRET_KEY = os.getenv("OCI_SECRET_ACCESS_KEY")
OCI_ENDPOINT = os.getenv("OCI_ENDPOINT")
HF_TOKEN = os.getenv("HF_TOKEN")

COMFY_HOST = "127.0.0.1"
COMFY_PORT = 8188
COMFY_URL = f"http://{COMFY_HOST}:{COMFY_PORT}"
WS_URL = f"ws://{COMFY_HOST}:{COMFY_PORT}"

BASE_DIR = Path("/dev/shm")
COMFY_DIR = BASE_DIR / "comfyui"
MODELS_DIR = COMFY_DIR / "models"
COMFY_INPUT_DIR = COMFY_DIR / "input"

SAVE_IMAGE_WEBSOCKET_NODE = "11"
PNG_HEADER = b"\x89PNG\r\n\x1a\n"

OCI_PREFIX_MANIFEST = "manifest/models.json"
OCI_PREFIX_QUEUE = "queue/pending"
OCI_PREFIX_RESULTS = "results"
OCI_PREFIX_PROCESSING = "queue/processing"
OCI_PREFIX_INPUTS = "inputs"
OCI_PREFIX_MGR_QUEUE = "manager/queue"
OCI_PREFIX_MGR_DONE = "manager/done"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True
)
log = logging.getLogger("colab-daemon")

logging.getLogger("boto3").setLevel(logging.WARNING)
logging.getLogger("botocore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("websocket").setLevel(logging.WARNING)

# ============================================================================
# SETUP RAM DISK Y ENTORNO (ZERO DISK)
# ============================================================================

def setup_zero_disk_environment(config: HardwareConfig):
    """Configura todo el entorno en RAM disk (/dev/shm)"""
    # Directorios en RAM
    for path in [COMFY_DIR, MODELS_DIR, COMFY_INPUT_DIR, BASE_DIR / "hf_cache", BASE_DIR / "torch_cache"]:
        path.mkdir(parents=True, exist_ok=True)

    # Variables de entorno para forzar cache a RAM
    os.environ["COMFYUI_TEMP_DIR"] = str(BASE_DIR / "comfyui_temp")
    os.environ["HF_HOME"] = str(BASE_DIR / "hf_cache")
    os.environ["TORCH_HOME"] = str(BASE_DIR / "torch_cache")
    os.environ["HF_HUB_CACHE"] = str(BASE_DIR / "hf_cache" / "hub")
    os.environ["TRANSFORMERS_CACHE"] = str(BASE_DIR / "hf_cache" / "transformers")
    os.environ["XDG_CACHE_HOME"] = str(BASE_DIR / "xdg_cache")

    # ComfyUI extra_model_paths.yaml
    EXTRA_MODEL_PATHS = BASE_DIR / "comfyui_temp" / "extra_model_paths.yaml"
    EXTRA_MODEL_PATHS.parent.mkdir(parents=True, exist_ok=True)
    EXTRA_MODEL_PATHS.write_text(f"models_dir: {MODELS_DIR}\n")
    os.environ["COMFYUI_EXTRA_MODEL_PATHS"] = str(EXTRA_MODEL_PATHS)

    # PyTorch optimizacion
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True,max_split_size_mb:64"
    os.environ["PYTORCH_CUDNN_BENCHMARK"] = "1"

    log.info(f"[Setup] Zero-disk configurado en {BASE_DIR}")
    log.info(f"[Setup] VRAM limit: {config.vram_limit_gb}GB, RAM disk max: {config.ram_disk_max_gb}GB")

# ============================================================================
# DESCARGA MODELOS CON WGET SILENCIOSO
# ============================================================================

HF_FILES = [
    ("vae", "flux2-vae.safetensors", 0.2, "https://huggingface.co/Comfy-Org/Fibo-2.0/resolve/main/vae/flux2-vae.safetensors"),
    ("diffusion_models", "fibo2_edit_turbo_fp8_e4m3fn.safetensors", 6.5, "https://huggingface.co/akhaliq/Fibo-2.0-edit-turbo-ComfyUI/resolve/main/diffusion_models/fibo2_edit_turbo_fp8_e4m3fn.safetensors"),
    ("text_encoders", "qwen3vl_4b_int8_convrot.safetensors", 4.0, "https://huggingface.co/ethanfel/Krea-2-Base-Diffusers/resolve/main/comfyui/text_encoders/qwen3vl_4b_abliterated_fp8_comfy.safetensors"),
]

def wget_download(url: str, dest_dir: Path, filename: str, min_size_gb: float = 0.1, token: str = None) -> Path:
    """Descarga con wget silencioso (-nv) para evitar spam en logs"""
    dest_dir = Path(dest_dir); dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / filename
    min_bytes = int(min_size_gb * 1024**3)

    if target.exists() and target.stat().st_size >= min_bytes:
        log.info(f"[DL] OK (ya existe): {filename}")
        return target

    log.info(f"[DL] Descargando {filename}...")

    cmd = [
        "wget", "-nv",  # non-verbose
        "--tries=5",
        "--continue",
        "--no-check-certificate",
        "-O", str(target)
    ]
    if token:
        cmd.extend(["--header", f"Authorization: Bearer {token}"])
    cmd.append(url)

    res = subprocess.run(cmd)

    if target.exists() and target.stat().st_size >= min_bytes:
        log.info(f"[DL] OK: {filename}")
        return target

    if target.exists(): target.unlink(missing_ok=True)
    raise RuntimeError(f"Fallo critico: No se pudo descargar {filename}")

def download_models(config: HardwareConfig):
    """Descarga modelos HF con wget silencioso"""
    log.info("[Models] Descargando modelos Fibo 2.0 FP8...")
    for folder, fn, min_gb, url in HF_FILES:
        wget_download(url, MODELS_DIR / folder, fn, min_gb, HF_TOKEN)
    log.info("[Models] Modelos descargados exitosamente")

# ============================================================================
# CUSTOM NODES: LOADIMAGE RAM + NO DISK GUARD
# ============================================================================

RAM_LOADER_CODE = """
import io, base64
import numpy as np
import torch
from PIL import Image

class LoadImageRAM:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image_b64": ("STRING", {"multiline": True, "default": "", "tooltip": "base64 de la imagen"})}}
    RETURN_TYPES = ("IMAGE", "MASK")
    FUNCTION = "load"
    CATEGORY = "image/ram"
    OUTPUT_NODE = False

    def load(self, image_b64):
        if not image_b64: raise ValueError("image_b64 vacio")
        raw = base64.b64decode(image_b64)
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        arr = np.array(img).astype(np.float32) / 255.0
        image = torch.from_numpy(arr)[None, ...]
        mask = torch.zeros((1, img.height, img.width), dtype=torch.float32)
        return (image, mask)

NODE_CLASS_MAPPINGS = {"LoadImageRAM": LoadImageRAM}
NODE_DISPLAY_NAME_MAPPINGS = {"LoadImageRAM": "Load Image (RAM, sin disco)"}
"""

NO_DISK_CODE = """
import comfy.samplers
def _no_disk(*args, **kwargs):
    raise RuntimeError("Nodo de escritura a disco deshabilitado. Usa SaveImageWebsocket.")
class _NoDiskNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"images": ("IMAGE",)}}
    RETURN_TYPES = ()
    FUNCTION = "run"
    CATEGORY = "disabled"
    OUTPUT_NODE = True
    def run(self, images): _no_disk()
NODE_CLASS_MAPPINGS = {"SaveImage": _NoDiskNode, "PreviewImage": _NoDiskNode}
"""

def inject_custom_nodes():
    """Inyecta nodos personalizados en ComfyUI"""
    # LoadImageRAM (base64 -> tensor en RAM)
    d = COMFY_DIR / "custom_nodes" / "zz_ram_loader"
    d.mkdir(parents=True, exist_ok=True)
    (d / "__init__.py").write_text(RAM_LOADER_CODE, encoding="utf-8")

    # Guard deshabilita SaveImage/PreviewImage
    d = COMFY_DIR / "custom_nodes" / "zz_no_disk_writes"
    d.mkdir(parents=True, exist_ok=True)
    (d / "__init__.py").write_text(NO_DISK_CODE, encoding="utf-8")

    log.info("[CustomNodes] Inyectados: LoadImageRAM + NoDiskGuard")

DISK_WRITE_NODES = {"SaveImage", "PreviewImage"}

def validate_no_disk_writes(workflow):
    """Valida que el workflow no tenga nodos de escritura a disco"""
    bad = []
    for nid, node in workflow.items():
        if isinstance(node, dict):
            ct = node.get("class_type", "")
            if ct in DISK_WRITE_NODES:
                bad.append(f"{ct} (nodo {nid})")
    if bad:
        raise RuntimeError("Workflow rechazado: contiene nodos de escritura a disco: " + ", ".join(bad))

# ============================================================================
# COMFYUI PROCESS MANAGEMENT
# ============================================================================

comfy_proc = None

def start_comfyui():
    """Inicia ComfyUI en background"""
    global comfy_proc
    log_path = str(BASE_DIR / "comfyui_server.log")
    log_handle = open(log_path, "w", encoding="utf-8")
    env = os.environ.copy()
    env["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True,max_split_size_mb:64"

    comfy_proc = subprocess.Popen([
        sys.executable, "main.py",
        "--listen", COMFY_HOST,
        "--port", str(COMFY_PORT),
        "--preview-method", "none",
        "--disable-metadata",
        "--force-fp16"
    ], cwd=str(COMFY_DIR), env=env, stdout=log_handle, stderr=subprocess.STDOUT)

    deadline = time.time() + 300  # Colab puede tardar mas
    while time.time() < deadline:
        if comfy_proc.poll() is not None:
            raise RuntimeError("ComfyUI fallo. Revisa comfyui_server.log")
        try:
            if requests.get(f"{COMFY_URL}/system_stats", timeout=3).ok:
                log.info(f"[ComfyUI] Listo en {COMFY_URL}")
                return True
        except: pass
        time.sleep(3)
    raise TimeoutError("ComfyUI no respondio a tiempo")

def restart_comfyui():
    """Reinicia ComfyUI (util tras instalar custom nodes)"""
    global comfy_proc
    if comfy_proc and comfy_proc.poll() is None:
        comfy_proc.terminate()
        try: comfy_proc.wait(timeout=15)
        except: comfy_proc.kill()
    start_comfyui()

# ============================================================================
# WORKFLOW HELPERS
# ============================================================================

def fix_seed(workflow):
    """Fija seeds aleatorios en KSampler/RandomNoise"""
    import random
    for nid, node in workflow.items():
        if isinstance(node, dict) and node.get("class_type") in ("KSampler", "KSamplerAdvanced", "RandomNoise"):
            inp = node.setdefault("inputs", {})
            key = "noise_seed" if node.get("class_type") == "RandomNoise" else "seed"
            s = inp.get(key)
            if s is None or (isinstance(s, int) and s < 0):
                inp[key] = random.randint(0, 2**63 - 1)
    return workflow

def find_input_images(workflow):
    """Encuentra imagenes referenciadas por LoadImage"""
    names = []
    for nid, node in workflow.items():
        if not isinstance(node, dict): continue
        ct = node.get("class_type", "")
        if "LoadImageRAM" in ct: continue
        if ct in ("LoadImage", "LoadImageMask", "LoadImageOutput"):
            img = node.get("inputs", {}).get("image")
            if isinstance(img, str) and img: names.append(img)
    return names

def sync_inputs_from_oci(workflow, s3_client):
    """Sincroniza imagenes de entrada desde OCI"""
    COMFY_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in find_input_images(workflow):
        local = COMFY_INPUT_DIR / name
        if local.exists(): continue
        try:
            data = s3_client.get_object(Bucket=OCI_BUCKET, Key=f"{OCI_PREFIX_INPUTS}/{name}")["Body"].read()
            local.write_bytes(data)
        except Exception:
            pass

def is_cancelled(task_id, s3_client):
    """Verifica si tarea fue cancelada via OCI"""
    try:
        objs = s3_client.list_objects_v2(Bucket=OCI_BUCKET, Prefix=f"queue/cancelled/{task_id}.json")
        return len(objs.get("Contents", [])) > 0
    except Exception:
        return False

def cancel_in_comfyui():
    """Envia senal de interrupcion a ComfyUI"""
    try: requests.post(f"{COMFY_URL}/interrupt", timeout=5)
    except Exception: pass

# ============================================================================
# EJECUCION WORKFLOW VIA WEBSOCKET
# ============================================================================

async def execute_and_upload(workflow_payload, task_id, s3_client, ws_executor, model_manager, config):
    """Ejecuta workflow y sube resultado a OCI"""
    if is_cancelled(task_id, s3_client):
        raise RuntimeError(f"Tarea {task_id} cancelada antes de ejecutar")

    workflow = workflow_payload["prompt"] if isinstance(workflow_payload, dict) and "prompt" in workflow_payload else workflow_payload
    workflow = fix_seed(workflow)
    validate_no_disk_writes(workflow)

    try:
        sync_inputs_from_oci(workflow, s3_client)
    except Exception:
        pass

    # Ejecutar via WebSocket executor
    result = await ws_executor.execute(workflow, task_id)

    if not result.success:
        raise RuntimeError(result.error or "Error desconocido en ejecucion")

    if not result.images:
        raise RuntimeError("No se recibio imagen por WebSocket")

    # Subir resultados a OCI
    for i, png_bytes in enumerate(result.images):
        png_key = f"{OCI_PREFIX_RESULTS}/{task_id}/moss_{i:03d}.png"
        s3_client.put_object(Bucket=OCI_BUCKET, Key=png_key, Body=png_bytes, ContentType="image/png")

    meta = {
        "task_id": task_id,
        "prompt_id": result.prompt_id,
        "status": "completed",
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "execution_time": result.execution_time,
        "images_count": len(result.images),
    }
    s3_client.put_object(Bucket=OCI_BUCKET, Key=f"results/{task_id}/meta.json",
                         Body=json.dumps(meta, ensure_ascii=False).encode("utf-8"),
                         ContentType="application/json")

    log.info(f"[{task_id[:8]}] Completado en {result.execution_time:.1f}s ({len(result.images)} imgs)")
    return result.prompt_id

# ============================================================================
# MANAGER QUEUE (instalacion custom nodes dinamicos)
# ============================================================================

def scan_models():
    """Escanea modelos locales para manifiesto"""
    res = {"checkpoints": [], "vaes": [], "loras": [], "text_encoders": []}
    dirs = [
        (MODELS_DIR / "diffusion_models", "checkpoints", (".safetensors", ".ckpt", ".pth")),
        (MODELS_DIR / "vae", "vaes", (".safetensors", ".ckpt", ".pth")),
        (MODELS_DIR / "loras", "loras", (".safetensors", ".ckpt")),
        (MODELS_DIR / "text_encoders", "text_encoders", (".safetensors", ".pth")),
    ]
    for d, cat, ex in dirs:
        if d.exists(): res[cat] = sorted([f.name for f in d.iterdir() if f.is_file() and f.suffix.lower() in ex])
    return res

def upload_manifest(s3_client):
    """Sube manifiesto de modelos a OCI"""
    import ast
    def scan_custom_nodes_ast():
        found = []
        CUSTOM_NODES_DIR = COMFY_DIR / "custom_nodes"
        if not CUSTOM_NODES_DIR.exists(): return found
        for pkg_dir in CUSTOM_NODES_DIR.iterdir():
            if not pkg_dir.is_dir() or pkg_dir.name.endswith(".disabled"): continue
            for py in pkg_dir.rglob("*.py"):
                try:
                    tree = ast.parse(py.read_text(encoding="utf-8", errors="ignore"))
                except Exception: continue
                for node in ast.walk(tree):
                    if isinstance(node, ast.Assign):
                        for t in node.targets:
                            if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and t.value.id == "NODE_CLASS_MAPPINGS":
                                if isinstance(t.slice, ast.Constant) and isinstance(t.slice.value, str):
                                    found.append({"type": t.slice.value, "package": pkg_dir.name})
        seen = set(); out = []
        for n in found:
            if n["type"] not in seen:
                seen.add(n["type"]); out.append(n)
        return sorted(out, key=lambda x: x["type"])

    manifest = {
        "provider": "colab_runtime",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "models": scan_models(),
        "summary": {k: len(v) for k, v in scan_models().items()},
        "custom_nodes": scan_custom_nodes_ast(),
    }
    s3_client.put_object(
        Bucket=OCI_BUCKET, Key=OCI_PREFIX_MANIFEST,
        Body=json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json"
    )
    return manifest

def install_custom_package(item, s3_client):
    """Instala custom node desde git"""
    pkg = item["package"]
    url = item["git_url"]
    dest = COMFY_DIR / "custom_nodes" / pkg
    if dest.exists():
        subprocess.run(["git", "-C", str(dest), "pull", "--ff-only"], capture_output=True)
    else:
        COMFY_DIR.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(["git", "clone", "--depth", "1", url, str(dest)], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"git clone fallo: {r.stderr[:500]}")
    req = dest / "requirements.txt"
    if req.exists():
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-cache-dir", "-r", str(req)], check=False)
    restart_comfyui()
    upload_manifest(s3_client)

def process_manager_queue(s3_client):
    """Procesa cola de instalacion de custom nodes"""
    try:
        objs = s3_client.list_objects_v2(Bucket=OCI_BUCKET, Prefix=OCI_PREFIX_MGR_QUEUE + "/")
    except Exception:
        return
    for obj in objs.get("Contents", []):
        key = obj["Key"]
        if key.endswith("/"): continue
        try:
            item = json.loads(s3_client.get_object(Bucket=OCI_BUCKET, Key=key)["Body"].read().decode("utf-8"))
            item["status"] = "installing"
            s3_client.put_object(Bucket=OCI_BUCKET, Key=key, Body=json.dumps(item, ensure_ascii=False).encode("utf-8"), ContentType="application/json")
            install_custom_package(item, s3_client)
            item["status"] = "done"
            item["finished_at"] = datetime.now(timezone.utc).isoformat()
            s3_client.put_object(Bucket=OCI_BUCKET, Key=f"{OCI_PREFIX_MGR_DONE}/{item['id']}.json", Body=json.dumps(item, ensure_ascii=False, indent=2).encode("utf-8"), ContentType="application/json")
            s3_client.delete_object(Bucket=OCI_BUCKET, Key=key)
        except Exception as e:
            try:
                item["status"] = "error"; item["error"] = str(e)[:500]
                s3_client.put_object(Bucket=OCI_BUCKET, Key=f"{OCI_PREFIX_MGR_DONE}/{item.get('id','x')}.json", Body=json.dumps(item, ensure_ascii=False).encode("utf-8"), ContentType="application/json")
                s3_client.delete_object(Bucket=OCI_BUCKET, Key=key)
            except Exception: pass

# ============================================================================
# HEARTBEAT
# ============================================================================

async def heartbeat_loop(s3_client, config):
    """Loop de heartbeat a OCI status/worker.json"""
    start_time = time.time()
    while True:
        try:
            comfy_ok = False
            try: comfy_ok = requests.get(f"{COMFY_URL}/system_stats", timeout=3).ok
            except Exception: pass

            n_pend = len(s3_client.list_objects_v2(Bucket=OCI_BUCKET, Prefix=OCI_PREFIX_QUEUE + "/").get("Contents", []))

            payload = {
                "online": True,
                "age_seconds": int(time.time() - start_time),
                "ts": datetime.now(timezone.utc).isoformat(),
                "comfy_alive": comfy_ok,
                "pending": n_pend,
                "environment": "colab",
                "gpu_count": 1,
                "vram_total_gb": 16,
            }
            s3_client.put_object(Bucket=OCI_BUCKET, Key="status/worker.json",
                                 Body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                                 ContentType="application/json")
        except Exception as e:
            log.warning(f"[Heartbeat] Error: {e}")
        await asyncio.sleep(HEARTBEAT_INTERVAL)

# ============================================================================
# MAIN POLLING LOOP (SECUENCIAL PARA COLAB)
# ============================================================================

purge_counter = 0

async def polling_loop(s3_client, ws_executor, model_manager, config):
    """Loop principal: poll OCI queue -> execute workflows (SECUENCIAL para Colab)"""
    log.info("[Polling] Iniciado (intervalo: 10s, workers secuenciales)")
    while True:
        try:
            process_manager_queue(s3_client)

            objs = s3_client.list_objects_v2(Bucket=OCI_BUCKET, Prefix=OCI_PREFIX_QUEUE + "/")
            for obj in objs.get("Contents", []):
                key = obj["Key"]
                if key.endswith("/"): continue

                task_id = Path(key).stem

                try:
                    # Leer task
                    try:
                        resp = s3_client.get_object(Bucket=OCI_BUCKET, Key=key)
                    except ClientError as ce:
                        if ce.response["Error"]["Code"] in ("NoSuchKey", "404"): continue
                        raise

                    task_data = json.loads(resp["Body"].read().decode("utf-8"))
                    task_id = task_data.get("task_id", task_id)
                    wf_in = task_data.get("workflow")

                    # Mover a processing atomicamente
                    processing_key = f"{OCI_PREFIX_PROCESSING}/{task_id}.json"
                    try:
                        s3_client.copy_object(Bucket=OCI_BUCKET, Key=processing_key,
                                             CopySource={"Bucket": OCI_BUCKET, "Key": key})
                        s3_client.delete_object(Bucket=OCI_BUCKET, Key=key)
                    except ClientError as ce:
                        if ce.response["Error"]["Code"] in ("NoSuchKey", "404"): continue
                        raise

                    # Ejecutar workflow (SECUENCIAL - solo 1 worker en Colab)
                    await execute_and_upload(wf_in, task_id, s3_client, ws_executor, model_manager, config)

                except Exception as e:
                    # Subir error a OCI
                    try:
                        boto3.client("s3", endpoint_url=OCI_ENDPOINT,
                            aws_access_key_id=OCI_ACCESS_KEY,
                            aws_secret_access_key=OCI_SECRET_KEY,
                            region_name=OCI_REGION,
                            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}, retries={"max_attempts": 5})
                        ).put_object(Bucket=OCI_BUCKET, Key=f"errors/{task_id}.json", Body=json.dumps({"task_id": task_id, "error": str(e)[:2000], "ts": datetime.now(timezone.utc).isoformat()}, ensure_ascii=False).encode("utf-8"), ContentType="application/json")
                    except Exception: pass
                finally:
                    # Limpiar processing
                    try:
                        boto3.client("s3", endpoint_url=OCI_ENDPOINT,
                            aws_access_key_id=OCI_ACCESS_KEY,
                            aws_secret_access_key=OCI_SECRET_KEY,
                            region_name=OCI_REGION,
                            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}, retries={"max_attempts": 5})
                        ).delete_object(Bucket=OCI_BUCKET, Key=processing_key)
                    except Exception: pass
        except Exception as e:
            log.error(f"[Polling] Error: {e}")

        # Purga periodica directorios disco
        global purge_counter
        purge_counter += 1
        if purge_counter % 12 == 0:
            try:
                for sub in ("input", "output", "temp"):
                    d = COMFY_DIR / sub
                    if d.exists():
                        for f in d.iterdir():
                            try:
                                if f.is_file() or f.is_symlink(): f.unlink()
                                elif f.is_dir(): shutil.rmtree(f, ignore_errors=True)
                            except Exception: pass
            except Exception: pass

        await asyncio.sleep(POLL_INTERVAL)

# ============================================================================
# MAIN
# ============================================================================

async def main():
    # Verificar entorno Colab
    if not (os.getenv("COLAB_RELEASE_TAG") or os.path.exists("/content")):
        raise RuntimeError("Ejecutar dentro de Google Colab.")

    # Verificar variables OCI
    required = ["OCI_NAMESPACE", "OCI_BUCKET", "OCI_REGION", "OCI_ACCESS_KEY_ID", "OCI_SECRET_ACCESS_KEY", "OCI_ENDPOINT"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        log.error(f"Faltan variables de entorno: {', '.join(missing)}")
        sys.exit(1)

    # Configuracion hardware Colab
    config = build_config_for_environment("colab")
    log.info(f"[Config] Entorno: Colab ({config.gpu_count}x {config.gpu_names[0]} = {config.vram_per_gpu_gb * config.gpu_count}GB VRAM)")
    log.info(f"[Config] RAM: {config.system_ram_gb}GB, RAM disk max: {config.ram_disk_max_gb}GB")
    log.info(f"[Config] Max modelos VRAM: {config.max_models_in_vram}, Workers: SECUENCIAL (1)")
    log.info(f"[Config] CPU offload: {config.enable_cpu_offload}")

    # Setup zero-disk
    setup_zero_disk_environment(config)

    # Instalar dependencias base
    subprocess.run(["bash", "-lc", "apt-get update -qq && apt-get install -y -qq git wget"], check=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-cache-dir", "boto3", "botocore", "requests", "websocket-client"], check=True)

    # Verificar GPU
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("Activa GPU en Runtime > Change runtime type > GPU.")
    log.info(f"[GPU] {torch.cuda.get_device_name(0)} ({torch.cuda.device_count()} GPUs)")

    # Clonar ComfyUI
    if not COMFY_DIR.exists():
        subprocess.run(["git", "clone", "--depth", "1", "https://github.com/comfyanonymous/ComfyUI", str(COMFY_DIR)], check=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-cache-dir", "-r", str(COMFY_DIR / "requirements.txt")], check=True)

    # Custom nodes Fibo2
    FIBO2_DIR = COMFY_DIR / "custom_nodes" / "ComfyUI-Fibo2"
    if not FIBO2_DIR.exists():
        subprocess.run(["git", "clone", "--depth", "1", "https://github.com/drphero/ComfyUI-Fibo2.git", str(FIBO2_DIR)], check=True)
        log.info("[CustomNodes] ComfyUI-Fibo2 clonado")

    # Descargar modelos
    download_models(config)

    # Inyectar custom nodes (LoadImageRAM + NoDiskGuard)
    inject_custom_nodes()

    # Cliente OCI
    s3_client = boto3.client("s3", endpoint_url=OCI_ENDPOINT,
        aws_access_key_id=OCI_ACCESS_KEY,
        aws_secret_access_key=OCI_SECRET_KEY,
        region_name=OCI_REGION,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"},
                      retries={"max_attempts": 5, "mode": "adaptive"},
                      connect_timeout=20, read_timeout=180, max_pool_connections=10))
    s3_client.head_bucket(Bucket=OCI_BUCKET)
    log.info(f"[OCI] Conectado a bucket: {OCI_BUCKET}")

    # Subir manifiesto inicial
    upload_manifest(s3_client)

    # Iniciar ComfyUI
    start_comfyui()

    # Inicializar componentes
    oci_client = create_oci_client(config)
    model_manager = ModelManager(config)

    # Registrar modelos en ModelManager
    model_manager.register_model("fibo2_edit_turbo", str(MODELS_DIR / "diffusion_models" / "fibo2_edit_turbo_fp8_e4m3fn.safetensors"), 6.5, "diffusion")
    model_manager.register_model("flux2_vae", str(MODELS_DIR / "vae" / "flux2-vae.safetensors"), 0.2, "vae")
    model_manager.register_model("qwen3vl_4b", str(MODELS_DIR / "text_encoders" / "qwen3vl_4b_int8_convrot.safetensors"), 4.0, "text_encoder")
    model_manager.set_vae_shared("flux2_vae")

    # WebSocket executor
    ws_executor = create_ws_executor(COMFY_URL, WS_URL, config)

    # Heartbeat task
    heartbeat_task = asyncio.create_task(heartbeat_loop(s3_client, config))

    # Polling loop principal
    await polling_loop(s3_client, ws_executor, model_manager, config)

    # Cleanup
    heartbeat_task.cancel()
    try: await heartbeat_task
    except asyncio.CancelledError: pass

    # Offline heartbeat
    s3_client.put_object(Bucket=OCI_BUCKET, Key="status/worker.json",
                         Body=json.dumps({"online": False, "ts": datetime.now(timezone.utc).isoformat()}, ensure_ascii=False).encode("utf-8"),
                         ContentType="application/json")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Interrupted")
    except Exception as e:
        log.error(f"Fatal: {e}")
        sys.exit(1)
