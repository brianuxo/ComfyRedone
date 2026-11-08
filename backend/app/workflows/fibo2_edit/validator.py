"""Validador del workflow FIBO 2.0 Edit.

Rechaza nodos de escritura a disco (SaveImage, PreviewImage) y valida que
el workflow tenga la estructura mínima requerida.
"""

from __future__ import annotations

from typing import Any, Dict, List

# Nodos que escriben a disco y están prohibidos.
# SaveImageWebsocket NO está aquí porque captura la imagen en memoria (RAM)
# y la envía por WebSocket al backend, que luego la sube a OCI. No toca disco.
DISK_WRITE_NODES = {"SaveImage", "PreviewImage"}

# Nodos obligatorios del workflow FIBO 2.0 Edit
REQUIRED_NODES = {
    "1": "Fibo2DiffusionModelLoader",
    "3": "Fibo2EditConditioning",
    "4": "EmptyFlux2LatentImage",
    "5": "Fibo2Scheduler",
    "6": "BasicGuider",
    "7": "RandomNoise",
    "8": "KSamplerSelect",
    "9": "SamplerCustomAdvanced",
    "10": "VAEDecode",
    "11": "SaveImageWebsocket",
    "15": "Fibo2TextEncoderLoader",
    "16": "VAELoader",
}


def validate_no_disk_writes(workflow: Dict[str, Any]) -> None:
    """Lanza RuntimeError si el workflow contiene nodos prohibidos de escritura a disco."""
    bad: List[str] = []
    for nid, node in workflow.items():
        if not isinstance(node, dict):
            continue
        ct = node.get("class_type", "")
        if ct in DISK_WRITE_NODES:
            bad.append(f"{ct} (nodo {nid})")
    if bad:
        raise RuntimeError(
            "Workflow rechazado: contiene nodos de escritura a disco: " + ", ".join(bad)
        )


def validate_structure(workflow: Dict[str, Any]) -> None:
    """Valida que el workflow tenga los nodos obligatorios de FIBO 2.0 Edit."""
    missing: List[str] = []
    for nid, expected_ct in REQUIRED_NODES.items():
        node = workflow.get(nid)
        if not isinstance(node, dict):
            missing.append(f"{nid} ({expected_ct})")
            continue
        if node.get("class_type") != expected_ct:
            missing.append(f"{nid} (esperado {expected_ct}, encontrado {node.get('class_type')})")
    if missing:
        raise RuntimeError(
            "Workflow inválido: faltan nodos obligatorios: " + ", ".join(missing)
        )


def validate(workflow: Dict[str, Any]) -> None:
    """Ejecuta todas las validaciones del workflow."""
    validate_no_disk_writes(workflow)
    validate_structure(workflow)