#!/usr/bin/env python3
"""
Detección automática de entorno de ejecución: Kaggle vs Colab vs Local
Configuración óptima de hardware por entorno
"""

import os
import sys
import torch
from dataclasses import dataclass
from typing import Optional


@dataclass
class HardwareConfig:
    """Configuración de hardware optimizada por entorno"""
    environment: str
    gpu_count: int
    vram_per_gpu_gb: int
    gpu_names: list[str]
    cpu_cores: int
    cpu_threads: int
    system_ram_gb: int
    ram_disk_max_gb: int
    poll_interval_seconds: int
    heartbeat_interval_seconds: int
    max_models_in_vram: int
    max_parallel_workers: int
    enable_cpu_offload: bool
    comfyui_startup_timeout: int
    ws_timeout: int
    http_timeout: int
def build_config_for_environment(env: Optional[str] = None) -> HardwareConfig:
    """Construye configuración óptima para el entorno detectado."""
    if env is None:
        env = detect_environment()
    gpu_count, vram_per_gpu, gpu_names = get_gpu_info()
    cpu_physical, cpu_logical = get_cpu_info()
    system_ram_gb = get_ram_info()
    if env == "kaggle":
        return HardwareConfig(
            environment="kaggle",
            gpu_count=gpu_count or 1,
            vram_per_gpu_gb=vram_per_gpu or 16,
            gpu_names=gpu_names or ["Tesla T4"],
            cpu_cores=cpu_physical or 4,
            cpu_threads=cpu_logical or 4,
            system_ram_gb=system_ram_gb or 30,
            ram_disk_max_gb=8,
            poll_interval_seconds=3,
            heartbeat_interval_seconds=15,
            max_models_in_vram=2,
            max_parallel_workers=2,
            enable_cpu_offload=False,
            comfyui_startup_timeout=240,
            ws_timeout=120,
            http_timeout=60,
        )
    elif env == "colab":
        return HardwareConfig(
            environment="colab",
            gpu_count=gpu_count or 1,
            vram_per_gpu_gb=vram_per_gpu or 16,
            gpu_names=gpu_names or ["Tesla T4"],
            cpu_cores=cpu_physical or 1,
            cpu_threads=cpu_logical or 2,
            system_ram_gb=system_ram_gb or 12,
            ram_disk_max_gb=3,
            poll_interval_seconds=10,
            heartbeat_interval_seconds=30,
            max_models_in_vram=1,
            max_parallel_workers=1,
            enable_cpu_offload=True,
            comfyui_startup_timeout=300,
            ws_timeout=180,
            http_timeout=120,
        )
    else:
        return HardwareConfig(
            environment="local",
            gpu_count=gpu_count or 1,
            vram_per_gpu_gb=vram_per_gpu or 8,
            gpu_names=gpu_names or ["Unknown GPU"],
            cpu_cores=cpu_physical or 4,
            cpu_threads=cpu_logical or 8,
            system_ram_gb=system_ram_gb or 16,
            ram_disk_max_gb=6,
            poll_interval_seconds=5,
            heartbeat_interval_seconds=20,
            max_models_in_vram=1,
            max_parallel_workers=1,
            enable_cpu_offload=False,
            comfyui_startup_timeout=180,
            ws_timeout=60,
            http_timeout=60,
        )


CONFIG = None


def get_config() -> HardwareConfig:
    """Obtiene la configuración global (inicializa si es necesario)"""
    global CONFIG
    if CONFIG is None:
        CONFIG = build_config_for_environment()
    return CONFIG


def print_config(config: HardwareConfig):
    """Imprime configuración de forma legible"""
    print(f"\n{'='*60}")
    print(f"HARDWARE CONFIG: {config.environment.upper()}")
    print(f"{'='*60}")
    print(f"GPU: {config.gpu_count}x {config.gpu_names[0] if config.gpu_names else 'Unknown'} ({config.vram_per_gpu_gb}GB VRAM c/u)")
    print(f"CPU: {config.cpu_cores} cores / {config.cpu_threads} threads")
    print(f"RAM: {config.system_ram_gb}GB (RAM disk max: {config.ram_disk_max_gb}GB)")
    print(f"Poll interval: {config.poll_interval_seconds}s")
    print(f"Heartbeat: {config.heartbeat_interval_seconds}s")
    print(f"Max models in VRAM: {config.max_models_in_vram}")
    print(f"Parallel workers: {config.max_parallel_workers}")
    print(f"CPU offload: {'ENABLED' if config.enable_cpu_offload else 'DISABLED'}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    env = detect_environment()
    print(f"Entorno detectado: {env}")
    config = build_config_for_environment(env)
    print_config(config)
def detect_environment() -> str:
    """Detecta el entorno de ejecución actual."""
    if os.path.exists("/kaggle") or os.getenv("KAGGLE_KERNEL_RUN_TYPE"):
        return "kaggle"
    if os.getenv("COLAB_RELEASE_TAG") or os.path.exists("/content"):
        return "colab"
    if os.getenv("JUPYTER_SERVER_ROOT") or os.getenv("NOTEBOOK_DIR"):
        try:
            import psutil
            ram_gb = psutil.virtual_memory().total / (1024**3)
            cpu_count = psutil.cpu_count(logical=True)
            if ram_gb < 16 and cpu_count <= 2:
                return "colab"
        except Exception:
            pass
    return "local"


def get_gpu_info():
    """Obtiene información de GPUs disponibles"""
    if not torch.cuda.is_available():
        return 0, 0, []
    gpu_count = torch.cuda.device_count()
    gpu_names = []
    vram_per_gpu = 0
    for i in range(gpu_count):
        props = torch.cuda.get_device_properties(i)
        gpu_names.append(props.name)
        vram_gb = props.total_memory / (1024**3)
        if vram_per_gpu == 0:
            vram_per_gpu = int(vram_gb)
    return gpu_count, vram_per_gpu, gpu_names


def get_cpu_info():
    """Obtiene información de CPU"""
    try:
        import psutil
        physical = psutil.cpu_count(logical=False) or 1
        logical = psutil.cpu_count(logical=True) or 1
        return physical, logical
    except Exception:
        physical = int(os.getenv("CPU_CORES", os.getenv("NUM_CPUS", "1")))
        logical = int(os.getenv("CPU_THREADS", os.getenv("NUM_THREADS", str(physical * 2))))
        return physical, logical


def get_ram_info() -> int:
    """Obtiene RAM total en GB"""
    try:
        import psutil
        return int(psutil.virtual_memory().total / (1024**3))
    except Exception:
        return int(os.getenv("SYSTEM_RAM_GB", "8"))