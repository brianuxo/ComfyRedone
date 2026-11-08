"""
Cliente OCI / S3-compatible para Oracle Cloud Object Storage.

Se usa como intermediario entre el backend y el daemon de ComfyUI en Kaggle/Colab.
El backend nunca se conecta directamente a ComfyUI; todo fluye a través de OCI.

Prefixes utilizados en el bucket:
  - queue/pending/   : tareas enviadas por el backend (JSON con workflow + parámetros)
  - queue/processing/: tareas siendo ejecutadas por el daemon ComfyUI
  - results/{task_id}/: imágenes PNG resultantes (subidas por el daemon)
  - errors/{task_id}.json: errores de ejecución
  - status/worker.json: heartbeat del daemon (online, comfy_alive, pending, timestamp)
  - manifest/models.json: manifiesto de modelos y custom nodes
"""

from __future__ import annotations

import io
import json
import logging
from typing import Any, Dict, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from app.core.config import settings

logger = logging.getLogger(__name__)


class OCIClient:
    """Cliente para interactuar con OCI Object Storage (S3-compatible)."""

    def __init__(self) -> None:
        self.namespace = settings.OCI_NAMESPACE
        self.bucket = settings.OCI_BUCKET
        self.region = settings.OCI_REGION
        self.endpoint = settings.OCI_ENDPOINT
        self.access_key = settings.OCI_ACCESS_KEY_ID
        self.secret_key = settings.OCI_SECRET_ACCESS_KEY

        self._client: Optional[Any] = None

    @property
    def client(self) -> Any:
        """Devuelve el cliente boto3 (lazy initialization)."""
        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
                config=Config(
                    signature_version="s3v4",
                    s3={"addressing_style": "path"},
                    retries={"max_attempts": 5, "mode": "standard"},
                    connect_timeout=20,
                    read_timeout=180,
                ),
            )
        return self._client

    def is_configured(self) -> bool:
        """Devuelve True si las credenciales OCI están configuradas."""
        return bool(
            self.namespace
            and self.bucket
            and self.access_key
            and self.secret_key
            and self.endpoint
        )

    def bucket_exists(self) -> bool:
        """Verifica si el bucket existe y es accesible."""
        if not self.is_configured():
            return False
        try:
            self.client.head_bucket(Bucket=self.bucket)
            return True
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            logger.warning("Bucket OCI no accesible (code=%s): %s", code, exc)
            return False
        except (NoCredentialsError, BotoCoreError) as exc:
            logger.warning("Bucket OCI error de conexión: %s", exc)
            return False
        except Exception as exc:
            logger.warning("Bucket OCI error inesperado: %s", exc)
            return False

    def put_object(self, key: str, body: bytes, content_type: str = "application/json") -> bool:
        """Sube un objeto a OCI."""
        if not self.is_configured():
            logger.warning("OCI no configurado, omitiendo put_object: %s", key)
            return False
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=body,
                ContentType=content_type,
            )
            return True
        except (ClientError, NoCredentialsError, BotoCoreError) as exc:
            logger.error("Error subiendo a OCI %s: %s", key, exc)
            return False

    def put_object_json(self, key: str, data: Dict[str, Any]) -> bool:
        """Sube un objeto JSON a OCI."""
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        # DEBUG: escribir body a archivo
        try:
            with open(r"C:\Users\brian\Desktop\ALL\Proyectos\RustComfyCrear\debug_oci_body.log", "w") as f:
                f.write(body.decode("utf-8"))
        except Exception:
            pass
        return self.put_object(key, body, "application/json")

    def get_object(self, key: str) -> Optional[bytes]:
        """Descarga un objeto de OCI como bytes."""
        if not self.is_configured():
            logger.warning("OCI no configurado, omitiendo get_object: %s", key)
            return None
        try:
            resp = self.client.get_object(Bucket=self.bucket, Key=key)
            return resp["Body"].read()
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("NoSuchKey", "404", "NotFound"):
                return None
            logger.error("Error descargando de OCI %s: %s", key, exc)
            return None
        except (NoCredentialsError, BotoCoreError) as exc:
            logger.error("Error de credenciales OCI %s: %s", key, exc)
            return None

    def get_object_json(self, key: str) -> Optional[Dict[str, Any]]:
        """Descarga un objeto JSON de OCI."""
        body = self.get_object(key)
        if body is None:
            return None
        try:
            return json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.error("Error decodando JSON de OCI %s: %s", key, exc)
            return None

    def list_objects(self, prefix: str) -> list[str]:
        """Lista las claves de objetos bajo un prefijo."""
        if not self.is_configured():
            logger.warning("OCI no configurado, omitiendo list_objects: %s", prefix)
            return []
        try:
            resp = self.client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
            contents = resp.get("Contents", [])
            return [obj["Key"] for obj in contents if not obj["Key"].endswith("/")]
        except (ClientError, NoCredentialsError, BotoCoreError) as exc:
            logger.error("Error listando objetos OCI %s: %s", prefix, exc)
            return []

    def delete_object(self, key: str) -> bool:
        """Elimina un objeto de OCI."""
        if not self.is_configured():
            return False
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
            return True
        except (ClientError, NoCredentialsError, BotoCoreError) as exc:
            logger.error("Error eliminando de OCI %s: %s", key, exc)
            return False

    def put_json(self, key: str, data: Dict[str, Any]) -> bool:
        """Alias para put_object_json."""
        return self.put_object_json(key, data)

    def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        """Alias para get_object_json."""
        return self.get_object_json(key)


# Instancia reutilizable
oci_client = OCIClient()