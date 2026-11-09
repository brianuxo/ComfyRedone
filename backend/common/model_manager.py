# model_manager.py - Zero-disk model manager
#!/usr/bin/env python3
"""
Gestor de modelos con offloading inteligente CPU<->GPU
Compatible con Kaggle y Colab
"""

import os
import logging
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from enum import Enum

log = logging.getLogger("model_manager")

from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

log = logging.getLogger("model_manager")


class ModelState(Enum):
    NOT_LOADED = "not_loaded"
    LOADING = "loading"
    IN_VRAM = "in_vram"
    IN_RAM = "in_ram"
    ERROR = "error"


@dataclass
class ModelInfo:
    name: str
    path: str
    size_gb: float
    model_type: str
    state: ModelState = ModelState.NOT_LOADED
    vram_usage_gb: float = 0.0
    ram_usage_gb: float = 0.0
    last_used: float = 0.0
    load_count: int = 0


class ModelManager:
    def __init__(self, config=None):
        self.config = config
        self.models: Dict[str, ModelInfo] = {}
        self.vram_limit_gb = self._get_vram_limit()
        self.ram_limit_gb = self._get_ram_limit()
        self.max_models_in_vram = config.max_models_in_vram if config else 1
        self.enable_offload = config.enable_cpu_offload if config else True
        self.vae_model: Optional[str] = None
        log.info("[ModelManager] Iniciado - VRAM limit: " + str(self.vram_limit_gb) + "GB, " 
                 + "RAM limit: " + str(self.ram_limit_gb) + "GB, " 
                 + "Max models VRAM: " + str(self.max_models_in_vram) + ", " 
                 + "Offload: " + str(self.enable_offload))
    
    def _get_vram_limit(self) -> float:
        if self.config and self.config.gpu_count > 0:
            return self.config.vram_per_gpu_gb * self.config.gpu_count * 0.9
        return 16.0
    
    def _get_ram_limit(self) -> float:
        if self.config:
            return self.config.ram_disk_max_gb * 2
        return 8.0

    def register_model(self, name, path, size_gb, model_type="diffusion") -> ModelInfo:
        if name in self.models:
            return self.models[name]
        model = ModelInfo(
            name=name,
            path=path,
            size_gb=size_gb,
            model_type=model_type,
            vram_usage_gb=size_gb * 1.1,
            ram_usage_gb=size_gb * 1.1,
        )
        self.models[name] = model
        log.info("[ModelManager] Registrado: " + name + " (" + str(size_gb) + "GB, " + model_type + ")")
        return model
    
    def get_vram_usage(self):
        total = 0.0
        for m in self.models.values():
            if m.state == ModelState.IN_VRAM:
                total += m.vram_usage_gb
        return total
    
    def get_ram_usage(self):
        total = 0.0
        for m in self.models.values():
            if m.state == ModelState.IN_RAM:
                total += m.ram_usage_gb
        return total
    
    def can_fit_in_vram(self, model_name):
        model = self.models.get(model_name)
        if not model:
            return False
        current_vram = self.get_vram_usage()
        return (current_vram + model.vram_usage_gb) <= self.vram_limit_gb
    
    def ensure_model_in_vram(self, model_name):
        model = self.models.get(model_name)
        if not model:
            log.error("[ModelManager] Modelo no registrado: " + model_name)
            return False
        
        if model.state == ModelState.IN_VRAM:
            import time
            model.last_used = time.time()
            model.load_count += 1
            return True
        
        if model.state == ModelState.LOADING:
            log.warning("[ModelManager] Modelo " + model_name + " ya cargando")
            return False
        
        if not self.can_fit_in_vram(model_name):
            if not self._make_space_in_vram(model.vram_usage_gb):
                log.error("[ModelManager] No se pudo liberar VRAM para " + model_name)
                return False
        
        model.state = ModelState.LOADING
        try:
            model.state = ModelState.IN_VRAM
            import time
            model.last_used = time.time()
            model.load_count += 1
            log.info("[ModelManager] Cargado a VRAM: " + model_name)
            return True
        except Exception as e:
            model.state = ModelState.ERROR
            log.error("[ModelManager] Error cargando " + model_name + ": " + str(e))
            return False

    def _make_space_in_vram(self, needed_gb):
        if not self.enable_offload:
            return False
        vram_models = [m for m in self.models.values() if m.state == ModelState.IN_VRAM]
        vram_models.sort(key=lambda m: m.last_used)
        freed = 0.0
        for model in vram_models:
            if freed >= needed_gb:
                break
            if model.model_type == "vae" and model.name == self.vae_model:
                continue
            try:
                model.state = ModelState.IN_RAM
                freed += model.vram_usage_gb
                log.info("[ModelManager] Offloaded a RAM: " + model.name + " (+" + str(model.vram_usage_gb) + "GB VRAM)")
            except Exception as e:
                log.error("[ModelManager] Error offloading " + model.name + ": " + str(e))
        return freed >= needed_gb
    
    def offload_unused_models(self, keep=None):
        keep = keep or set()
        if self.vae_model:
            keep.add(self.vae_model)
        offloaded = 0
        for model in self.models.values():
            if model.name in keep:
                continue
            if model.state == ModelState.IN_VRAM:
                try:
                    model.state = ModelState.IN_RAM
                    offloaded += 1
                    log.info("[ModelManager] Offloaded: " + model.name)
                except Exception:
                    pass
        return offloaded
    
    def set_vae_shared(self, vae_name):
        self.vae_model = vae_name
        if vae_name in self.models:
            self.models[vae_name].model_type = "vae"
    
    def get_status(self):
        status = {
            "vram_used_gb": round(self.get_vram_usage(), 2),
            "vram_limit_gb": self.vram_limit_gb,
            "ram_used_gb": round(self.get_ram_usage(), 2),
            "ram_limit_gb": self.ram_limit_gb,
            "models": {}
        }
        for name, m in self.models.items():
            status["models"][name] = {
                "state": m.state.value,
                "size_gb": m.size_gb,
                "type": m.model_type,
                "load_count": m.load_count,
                "last_used": m.last_used
            }
        return status
