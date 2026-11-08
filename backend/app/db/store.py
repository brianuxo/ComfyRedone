"""Almacén simple en memoria para tareas y prompts.

Todas las tareas y prompts viven en RAM. Nunca se escriben en disco del worker.
Incluye TTL opcional para limpieza automática de tareas.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class TaskRecord:
    task_id: str
    status: str = "queued"  # queued | running | completed | failed | cancelled
    image_b64: Optional[str] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    prompt: Optional[dict] = None


class TaskStore:
    """Thread-safe almacén de tareas en memoria."""

    def __init__(self, ttl_seconds: int = 3600) -> None:
        self._lock = threading.RLock()
        self._tasks: Dict[str, TaskRecord] = {}
        self.ttl_seconds = ttl_seconds

    def create(self, prompt: dict, task_id: str | None = None) -> str:
        if task_id is None:
            task_id = str(uuid.uuid4())
        record = TaskRecord(task_id=task_id, prompt=prompt)
        with self._lock:
            self._tasks[task_id] = record
        return task_id

    def get(self, task_id: str) -> Optional[TaskRecord]:
        with self._lock:
            return self._tasks.get(task_id)

    def update_status(
        self,
        task_id: str,
        status: str,
        image_b64: Optional[str] = None,
        error: Optional[str] = None,
    ) -> bool:
        with self._lock:
            record = self._tasks.get(task_id)
            if not record:
                return False
            record.status = status
            record.updated_at = time.time()
            if image_b64 is not None:
                record.image_b64 = image_b64
            if error is not None:
                record.error = error
            return True

    def list(self) -> list[TaskRecord]:
        with self._lock:
            now = time.time()
            active: list[TaskRecord] = []
            expired: list[str] = []
            for tid, rec in self._tasks.items():
                if self.ttl_seconds > 0 and now - rec.created_at > self.ttl_seconds:
                    expired.append(tid)
                else:
                    active.append(rec)
            for tid in expired:
                del self._tasks[tid]
            return sorted(active, key=lambda r: r.created_at, reverse=True)

    def delete(self, task_id: str) -> bool:
        with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                return True
            return False

    def count(self) -> int:
        with self._lock:
            return len(self._tasks)


@dataclass
class PromptRecord:
    id: str
    title: str
    prompt: str
    negative_prompt: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class PromptStore:
    """Thread-safe almacén de prompts guardados en memoria."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._prompts: Dict[str, PromptRecord] = {}

    def create(self, title: str, prompt: str, negative_prompt: str = "") -> str:
        prompt_id = str(uuid.uuid4())
        record = PromptRecord(
            id=prompt_id,
            title=title,
            prompt=prompt,
            negative_prompt=negative_prompt,
        )
        with self._lock:
            self._prompts[prompt_id] = record
        return prompt_id

    def get(self, prompt_id: str) -> Optional[PromptRecord]:
        with self._lock:
            return self._prompts.get(prompt_id)

    def list(self) -> List[PromptRecord]:
        with self._lock:
            return sorted(
                self._prompts.values(),
                key=lambda r: r.updated_at,
                reverse=True
            )

    def update(self, prompt_id: str, title: str, prompt: str, negative_prompt: str) -> bool:
        with self._lock:
            record = self._prompts.get(prompt_id)
            if not record:
                return False
            record.title = title
            record.prompt = prompt
            record.negative_prompt = negative_prompt
            record.updated_at = time.time()
            return True

    def delete(self, prompt_id: str) -> bool:
        with self._lock:
            if prompt_id in self._prompts:
                del self._prompts[prompt_id]
                return True
            return False


# Instancia global (se configura desde main.py con los settings)
task_store: Optional[TaskStore] = None
prompt_store: Optional[PromptStore] = None


def init_task_store(ttl_seconds: int = 3600) -> TaskStore:
    global task_store
    task_store = TaskStore(ttl_seconds=ttl_seconds)
    return task_store


def init_prompt_store() -> PromptStore:
    global prompt_store
    prompt_store = PromptStore()
    return prompt_store