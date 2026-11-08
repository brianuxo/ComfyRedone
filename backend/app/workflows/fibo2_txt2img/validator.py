"""
Validador estricto del workflow FIBO 2.0 Txt2Img.

Garantiza que la estructura cumple las reglas:
- No hay nodos de disco (SaveImage, LoadImage, etc.)
- Solo nodos permitidos en lista blanca
- No hay inputs de imagen en conditioning (txt2img puro)
- La estructura de nodos es coherente
"""

from __future__ import annotations

from typing import Any, Dict

# Lista blanca de class_type permitidos (anti-disco)
ALLOWED_NODE_TYPES = {
    "Fibo2DiffusionModelLoader",
    "LoraLoaderModelOnly",
    "Fibo2TextEncoderLoader",
    "VAELoader",
    "Fibo2Txt2ImgConditioning",  # Diferente de Fibo2EditConditioning
    "EmptyFlux2LatentImage",
    "Fibo2Scheduler",
    "BasicGuider",
    "RandomNoise",
    "KSamplerSelect",
    "SamplerCustomAdvanced",
    "VAEDecode",
    "SaveImageWebsocket",
}

# Nodos prohibidos (acceso a disco)
FORBIDDEN_NODE_TYPES = {
    "SaveImage",
    "LoadImage",
    "LoadImageMask",
    "LoadImageFromPath",
    "SaveImageAs",
    "PreviewImage",
    "LoadImageRAM",  # No se usa en txt2img
}

# Nodos que NO deben tener input "model" (usar prev_model_ref encadenado)
NODES_WITHOUT_MODEL_INPUT = {
    "BasicGuider",
    "SamplerCustomAdvanced",
    "KSamplerSelect",
    "VAEDecode",
    "EmptyFlux2LatentImage",
    "Fibo2Scheduler",
    "RandomNoise",
    "KSamplerSelect",
    "SaveImageWebsocket",
}

# Nodos que NO deben tener input "images" en conditioning (txt2img)
NODES_WITHOUT_IMAGES_INPUT = {
    "Fibo2Txt2ImgConditioning",
}


def validate(workflow: Dict[str, Any]) -> None:
    """
    Valida la estructura del workflow FIBO 2.0 Txt2Img.
    Lanza ValueError si encuentra violaciones.
    """
    if not isinstance(workflow, dict):
        raise ValueError("Workflow debe ser un diccionario")

    if not workflow:
        raise ValueError("Workflow vacío")

    for nid, node in workflow.items():
        if not isinstance(node, dict):
            raise ValueError(f"Nodo {nid}: debe ser un diccionario")

        class_type = node.get("class_type")
        if not class_type:
            raise ValueError(f"Nodo {nid}: falta class_type")

        # Verificar lista blanca
        if class_type not in ALLOWED_NODE_TYPES:
            raise ValueError(f"Nodo {nid}: class_type '{class_type}' no permitido")

        # Verificar lista negra
        if class_type in FORBIDDEN_NODE_TYPES:
            raise ValueError(f"Nodo {nid}: class_type '{class_type}' PROHIBIDO (acceso a disco)")

        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            raise ValueError(f"Nodo {nid}: inputs debe ser un diccionario")

        # Verificar nodos que no deben tener input "model"
        if class_type in NODES_WITHOUT_MODEL_INPUT and "model" in inputs:
            raise ValueError(
                f"Nodo {nid} ({class_type}): NO debe tener input 'model' "
                f"(usar encadenamiento prev_model_ref)"
            )

        # Verificar nodos que no deben tener input "images" (txt2img)
        if class_type in NODES_WITHOUT_IMAGES_INPUT and "images" in inputs:
            raise ValueError(
                f"Nodo {nid} ({class_type}): NO debe tener input 'images' "
                f"(txt2img puro sin imagen de entrada)"
            )

        # Validar estructura de referencias (formato [node_id, output_index])
        for key, value in inputs.items():
            if isinstance(value, list) and len(value) == 2:
                ref_nid, ref_idx = value
                if not isinstance(ref_nid, str) or not isinstance(ref_idx, int):
                    raise ValueError(
                        f"Nodo {nid}: referencia inválida en '{key}': {value}"
                    )
                # Verificar que el nodo referenciado existe
                if ref_nid not in workflow:
                    raise ValueError(
                        f"Nodo {nid}: referencia a nodo inexistente '{ref_nid}' en '{key}'"
                    )