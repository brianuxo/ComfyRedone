#!/usr/bin/env python3
"""
Cliente OCI Object Storage - Zero-disk
"""

import os
import json
import logging
from typing import Any, Dict, List, Optional
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError, BotoCoreError
import boto3

log = logging.getLogger("oci_client")


class OCIClient:
    def __init__(self, config=None):
        self.namespace = os.getenv("OCI_NAMESPACE", "axw2jxhksso4")
        self.bucket = os.getenv("OCI_BUCKET", "comfyuiOut")
        self.region = os.getenv("OCI_REGION", "sa-santiago-1")
        self.access_key = os.getenv("OCI_ACCESS_KEY_ID")
        self.secret_key = os.getenv("OCI_SECRET_ACCESS_KEY")
        self.endpoint = os.getenv("OCI_ENDPOINT")
        
        if not all([self.namespace, self.bucket, self.region, 
                    self.access_key, self.secret_key, self.endpoint]):
            raise RuntimeError("Faltan variables OCI")
        
        if config:
            max_pool = max(5, config.cpu_threads * 2)
            connect_timeout = min(10, config.http_timeout // 6)
            read_timeout = config.http_timeout
        else:
            max_pool = 10
            connect_timeout = 10
            read_timeout = 60
        
        import boto3
        from botocore.config import Config
        self._client = boto3.client(
            "s3", endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                retries={"max_attempts": 5, "mode": "adaptive"},
                connect_timeout=connect_timeout,
                read_timeout=read_timeout,
                max_pool_connections=max_pool
            )
        )
        log.info("[OCI] Conectado: " + self.bucket)

    def put_json(self, key, data):
        try:
            body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self._client.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType="application/json")
            return True
        except (ClientError, NoCredentialsError, BotoCoreError) as e:
            log.error("[OCI] Error subiendo " + key + ": " + str(e))
            return False
    
    def get_json(self, key):
        try:
            resp = self._client.get_object(Bucket=self.bucket, Key=key)
            return json.loads(resp["Body"].read())
        except ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "404", "NotFound"):
                return None
            log.error("[OCI] Error descargando " + key + ": " + str(e))
            return None
        except (NoCredentialsError, BotoCoreError, json.JSONDecodeError) as e:
            log.error("[OCI] Error " + key + ": " + str(e))
            return None

    def put_bytes(self, key, data, content_type="application/octet-stream"):
        try:
            self._client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
            return True
        except (ClientError, NoCredentialsError, BotoCoreError) as e:
            log.error("[OCI] Error subiendo " + key + ": " + str(e))
            return False
    
    def get_bytes(self, key):
        try:
            resp = self._client.get_object(Bucket=self.bucket, Key=key)
            return resp["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "404", "NotFound"):
                return None
            log.error("[OCI] Error descargando " + key + ": " + str(e))
            return None
        except (NoCredentialsError, BotoCoreError) as e:
            log.error("[OCI] Error " + key + ": " + str(e))
            return None

    def list_pending(self):
        try:
            resp = self._client.list_objects_v2(Bucket=self.bucket, Prefix="queue/pending/")
            task_ids = []
            for obj in resp.get("Contents", []):
                key = obj["Key"]
                if key.endswith(".json"):
                    task_id = key.split("/")[-1].replace(".json", "")
                    task_ids.append(task_id)
            return task_ids
        except (ClientError, NoCredentialsError, BotoCoreError) as e:
            log.error("[OCI] Error listando pending: " + str(e))
            return []
    
    def move_pending_to_processing(self, task_id):
        src_key = "queue/pending/" + task_id + ".json"
        dst_key = "queue/processing/" + task_id + ".json"
        try:
            self._client.copy_object(
                Bucket=self.bucket,
                CopySource={"Bucket": self.bucket, "Key": src_key},
                Key=dst_key,
            )
            self._client.delete_object(Bucket=self.bucket, Key=src_key)
            return True
        except (ClientError, NoCredentialsError, BotoCoreError) as e:
            log.error("[OCI] Error moviendo " + task_id + " a processing: " + str(e))
            return False
    
    def delete(self, key):
        try:
            self._client.delete_object(Bucket=self.bucket, Key=key)
            return True
        except (ClientError, NoCredentialsError, BotoCoreError) as e:
            log.error("[OCI] Error eliminando " + key + ": " + str(e))
            return False

    def upload_result(self, task_id, image_bytes, prompt_id, index=0):
        png_key = "results/" + task_id + "/moss_" + str(index).zfill(3) + ".png"
        if not self.put_bytes(png_key, image_bytes, "image/png"):
            return False
        import datetime
        meta = {
            "task_id": task_id,
            "prompt_id": prompt_id,
            "status": "completed",
            "finished_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "size_bytes": len(image_bytes),
            "index": index,
        }
        return self.put_json("results/" + task_id + "/meta.json", meta)
    
    def upload_error(self, task_id, error):
        import datetime
        return self.put_json("errors/" + task_id + ".json", {
            "task_id": task_id,
            "error": error,
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })

    def send_heartbeat(self, comfy_alive, pending, gpu_info=None):
        import datetime
        payload = {
            "online": True,
            "comfy_alive": comfy_alive,
            "pending": pending,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "gpu": gpu_info or {},
        }
        return self.put_json("status/worker.json", payload)
    
    def send_offline(self):
        import datetime
        return self.put_json("status/worker.json", {
            "online": False,
            "comfy_alive": False,
            "pending": 0,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })


def create_oci_client(config=None):
    return OCIClient(config)
