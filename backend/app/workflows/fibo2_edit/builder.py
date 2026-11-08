"""
Constructor del JSON "prompt" de ComfyUI para FIBO 2.0 Edit.

Recibe los parámetros del usuario y devuelve el diccionario de nodos listo
para enviar a ComfyUI vía /prompt. No toca el disco del worker.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List

from app.workflows.fibo2_edit.validator import validate


def _fix_seed(workflow: Dict[str, Any]) -> Dict[str, Any]:
    """Asigna seed aleatorio si no viene o es negativo (igual que el script original)."""
    for nid, node in workflow.items():
        if isinstance(node, dict) and node.get("class_type") == "RandomNoise":
            inp = node.setdefault("inputs", {})
            key = "noise_seed"
            s = inp.get(key)
            if s is None or (isinstance(s, int) and s < 0):
                inp[key] = random.randint(0, 2**63 - 1)
    return workflow


def build_workflow(params: dict) -> Dict[str, Any]:
    """Construye el workflow JSON de FIBO 2.0 Edit.

    Parámetros esperados en `params`:
      - prompt: str
      - image_b64: Optional[str]
      - loras: List[str]
      - seed: Optional[int]
      - steps: int
      - scheduler: str
      - guidance: float
      - width: int
      - height: int

    Returns:
        Diccionario de nodos de ComfyUI listo para /prompt.
    """
    prompt: str = params["prompt"]
    image_b64: str | None = params.get("image_b64")
    loras: List[str] = params.get("loras", []) or []
    seed: int | None = params.get("seed")
    steps: int = params.get("steps", 20)
    scheduler: str = params.get("scheduler", "euler")
    guidance: float = params.get("guidance", 3.5)
    width: int = params.get("width", 1024)
    height: int = params.get("height", 1024)

    workflow: Dict[str, Any] = {}

    # Nodo 1: Carga el modelo base FIBO 2.0 Edit Turbo
    workflow["1"] = {
        "class_type": "Fibo2DiffusionModelLoader",
        "inputs": {
            "model_name": "fibo2_edit_turbo_fp8_e4m3fn.safetensors",
            "dtype": "default",
        },
    }

    # Nodos LoRAs (30, 31, ...) encadenados imitando AusBoss
    lora_node_id = 30
    prev_model_ref = ["1", 0]  # salida del nodo 1
    for lora_name in loras:
        workflow[str(lora_node_id)] = {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": prev_model_ref,
                "lora_name": lora_name,
            },
        }
        prev_model_ref = [str(lora_node_id), 0]
        lora_node_id += 1

    # Nodo de imagen principal (Node 2) - LoadImageRAM desde base64
    # Solo se crea el nodo 2; nodos 2b/2c/2d se omiten (solo 1 imagen por ahora)
    workflow["2"] = {
        "class_type": "LoadImageRAM",
        "inputs": {"image_b64": image_b64 if image_b64 else ""},
    }

    # Nodo 15: Text encoder FIBO (Qwen3-VL) - debe cargarse antes del conditioning
    workflow["15"] = {
        "class_type": "Fibo2TextEncoderLoader",
        "inputs": {
            "clip_name": "qwen3vl_4b_int8_convrot.safetensors",
            "dtype": "default",
        },
    }

    # Nodo 16: VAELoader FLUX.2 - debe cargarse antes del conditioning
    workflow["16"] = {
        "class_type": "VAELoader",
        "inputs": {
            "vae_name": "flux2-vae.safetensors",
        },
    }

    # Nodo 3: Condicionamiento con instrucción + imágenes + CLIP + VAE
    # Fibo2EditConditioning usa io.Autogrow.Input("images", prefix="image")
    # En la API v3, los inputs Autogrow se envían como claves planas: "images.image0", "images.image1", ...
    # NO acepta input "model" (corrección: eliminado)
    workflow["3"] = {
        "class_type": "Fibo2EditConditioning",
        "inputs": {
            "prompt": prompt,
            "clip": ["15", 0],
            "vae": ["16", 0],
            "images.image0": ["2", 0],
            "render_text_images": False,
            "width": width,
            "height": height,
        },
    }

    # Nodo 4: Latent vacío FLUX.2
    workflow["4"] = {
        "class_type": "EmptyFlux2LatentImage",
        "inputs": {
            "batch_size": 1,
            "width": width,
            "height": height,
        },
    }

    # Nodo 5: Scheduler propio de FIBO
    workflow["5"] = {
        "class_type": "Fibo2Scheduler",
        "inputs": {
            "scheduler": scheduler,
            "steps": steps,
            "latent": ["4", 0],
        },
    }

    # Nodo 6: Guider con modelo (post-LoRA) y conditioning
    workflow["6"] = {
        "class_type": "BasicGuider",
        "inputs": {
            "model": prev_model_ref,
            "conditioning": ["3", 0],
            "guidance": guidance,
        },
    }

    # Nodo 7: Ruido aleatorio con seed
    workflow["7"] = {
        "class_type": "RandomNoise",
        "inputs": {
            "noise_seed": seed if seed is not None else random.randint(0, 2**63 - 1),
        },
    }

    # Nodo 8: Selecciona euler
    workflow["8"] = {
        "class_type": "KSamplerSelect",
        "inputs": {
            "sampler_name": "euler",
        },
    }

    # Nodo 9: Sampler avanzado personalizado
    # SamplerCustomAdvanced NO tiene input "model" (el modelo va dentro del guider)
    # Inputs: noise, guider, sampler, sigmas, latent_image
    workflow["9"] = {
        "class_type": "SamplerCustomAdvanced",
        "inputs": {
            "noise": ["7", 0],
            "guider": ["6", 0],
            "sampler": ["8", 0],
            "sigmas": ["5", 0],
            "latent_image": ["4", 0],
        },
    }

    # Nodo 10: VAE Decode
    workflow["10"] = {
        "class_type": "VAEDecode",
        "inputs": {
            "samples": ["9", 0],
            "vae": ["16", 0],
        },
    }

    # Nodo 11: Guardar por WebSocket (captura en RAM → OCI, sin disco)
    workflow["11"] = {
        "class_type": "SaveImageWebsocket",
        "inputs": {
            "images": ["10", 0],
        },
    }

    # Validar estructura y anti-disco
    validate(workflow)

    # Fix de seed (igual que el script original)
    _fix_seed(workflow)

    return workflow