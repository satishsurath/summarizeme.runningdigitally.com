"""Redis-backed task store for background job tracking.

Replaces the in-memory dict-based status tracking with a persistent,
Redis-backed store that survives process restarts and works across
multiple gunicorn workers.

Usage:
    from services.task_store import TaskStore

    store = TaskStore()

    # Create a task
    task_id = store.create_task("download", {"channel_url": "https://..."}, total=10)

    # Update progress
    store.update_task(task_id, status="in_progress", processed=5)
    store.update_task(task_id, status="completed", processed=10)

    # Query
    task = store.get_task(task_id)
    active = store.list_tasks(status="in_progress")
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from enum import StrEnum

import redis

logger = logging.getLogger(__name__)


class TaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskInfo:
    """Represents a background task."""

    task_id: str
    task_type: str  # "download" or "summarize"
    status: str  # TaskStatus value
    created_at: float  # Unix timestamp
    updated_at: float  # Unix timestamp
    total: int = 0
    processed: int = 0
    errors: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def progress_percent(self) -> float:
        if self.total <= 0:
            return 0.0
        return (self.processed / self.total) * 100.0

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> TaskInfo:
        return TaskInfo(**data)


class TaskStore:
    """Redis-backed task store.

    Stores tasks as JSON objects in Redis with TTL-based expiration
    for completed/failed tasks.
    """

    # Redis key prefixes
    _TASK_KEY_PREFIX = "task:"
    _ACTIVE_SET = "tasks:active"
    _COMPLETED_SET = "tasks:completed"
    _FAILED_SET = "tasks:failed"

    # TTL for completed/failed tasks (24 hours)
    _COMPLETED_TTL = 86400

    def __init__(self, redis_client: redis.Redis | _InMemoryTaskStore | None = None):
        if redis_client is not None:
            self._client = redis_client
        else:
            env_url = __import__("os").environ.get("REDIS_URL")
            if env_url:
                try:
                    self._client = redis.from_url(env_url, decode_responses=True)
                    self._client.ping()
                    logger.info("TaskStore connected to Redis at %s", env_url)
                except Exception as e:
                    logger.warning(
                        "Redis unavailable at %s (%s); falling back to thread-safe in-memory task store",
                        env_url,
                        e,
                    )
                    self._client = _InMemoryTaskStore()
            else:
                self._client = _InMemoryTaskStore()

    @classmethod
    def in_memory(cls) -> TaskStore:
        """Create a TaskStore backed by the in-memory store (used by tests)."""
        return cls(redis_client=_InMemoryTaskStore())

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def create_task(
        self,
        task_type: str,
        metadata: dict | None = None,
        total: int = 0,
    ) -> str:
        """Create a new task and return its ID."""
        import uuid

        prefix_map = {"download": "dl", "summarize": "su"}
        prefix = prefix_map.get(task_type, task_type[:2])
        task_id = f"{prefix}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
        now = time.time()
        task = TaskInfo(
            task_id=task_id,
            task_type=task_type,
            status=TaskStatus.PENDING.value,
            created_at=now,
            updated_at=now,
            total=total,
            processed=0,
            metadata=metadata or {},
        )
        self._save_task(task)
        self._client.sadd(self._ACTIVE_SET, task_id)
        return task_id

    def get_task(self, task_id: str) -> TaskInfo | None:
        """Get a task by ID, or None if not found."""
        raw = self._client.get(f"{self._TASK_KEY_PREFIX}{task_id}")
        if raw is None:
            return None
        return TaskInfo.from_dict(json.loads(str(raw)))

    def update_task(
        self,
        task_id: str,
        status: str | None = None,
        processed: int | None = None,
        total: int | None = None,
        errors: list | None = None,
        metadata: dict | None = None,
    ) -> bool:
        """Update task fields. Returns True if task exists."""
        task = self.get_task(task_id)
        if task is None:
            return False

        if status is not None:
            task.status = status
            self._client.srem(self._ACTIVE_SET, task_id)
            self._client.srem(self._COMPLETED_SET, task_id)
            self._client.srem(self._FAILED_SET, task_id)
            if status in (TaskStatus.COMPLETED.value, TaskStatus.FAILED.value):
                target_set = self._COMPLETED_SET if status == TaskStatus.COMPLETED.value else self._FAILED_SET
                self._client.sadd(target_set, task_id)
                self._client.expire(f"{self._TASK_KEY_PREFIX}{task_id}", self._COMPLETED_TTL)
            else:
                self._client.sadd(self._ACTIVE_SET, task_id)
                self._client.persist(f"{self._TASK_KEY_PREFIX}{task_id}")

        if processed is not None:
            task.processed = processed
        if total is not None:
            task.total = total
        if errors is not None:
            task.errors = errors
        if metadata is not None:
            task.metadata.update(metadata)

        task.updated_at = time.time()
        self._save_task(task)
        return True

    def delete_task(self, task_id: str) -> bool:
        """Permanently delete a task."""
        task = self.get_task(task_id)
        if task is None:
            return False
        self._client.delete(f"{self._TASK_KEY_PREFIX}{task_id}")
        self._client.srem(self._ACTIVE_SET, task_id)
        self._client.srem(self._COMPLETED_SET, task_id)
        self._client.srem(self._FAILED_SET, task_id)
        return True

    def list_tasks(
        self,
        status: str | None = None,
        task_type: str | None = None,
    ) -> list:
        """List tasks, optionally filtered by status or type."""
        results: list = []

        sets_to_scan: list = []
        if status is None:
            sets_to_scan = [
                self._ACTIVE_SET,
                self._COMPLETED_SET,
                self._FAILED_SET,
            ]
        elif status == TaskStatus.IN_PROGRESS.value:
            sets_to_scan = [self._ACTIVE_SET]
        elif status == TaskStatus.COMPLETED.value:
            sets_to_scan = [self._COMPLETED_SET]
        elif status == TaskStatus.FAILED.value:
            sets_to_scan = [self._FAILED_SET]
        elif status == TaskStatus.PENDING.value:
            sets_to_scan = [self._ACTIVE_SET]

        seen_ids: set = set()
        for set_name in sets_to_scan:
            task_ids = self._client.smembers(set_name)
            for tid in task_ids:
                tid_str = str(tid)
                if tid_str in seen_ids:
                    continue
                seen_ids.add(tid_str)
                task = self.get_task(tid_str)
                if task is None:
                    self._client.srem(set_name, tid_str)
                    continue
                if status is not None and task.status != status:
                    continue
                if task_type is not None and task.task_type != task_type:
                    continue
                results.append(task)

        results.sort(key=lambda t: t.created_at, reverse=True)
        return results

    def get_active_count(self) -> int:
        """Return count of active (pending/in_progress) tasks."""
        val = self._client.scard(self._ACTIVE_SET)
        return int(val) if val else 0

    def get_completed_count(self) -> int:
        """Return count of completed tasks."""
        val = self._client.scard(self._COMPLETED_SET)
        return int(val) if val else 0

    def get_failed_count(self) -> int:
        """Return count of failed tasks."""
        val = self._client.scard(self._FAILED_SET)
        return int(val) if val else 0

    def _save_task(self, task: TaskInfo) -> None:
        """Persist a task to Redis."""
        key = f"{self._TASK_KEY_PREFIX}{task.task_id}"
        if task.status in (TaskStatus.COMPLETED.value, TaskStatus.FAILED.value):
            self._client.set(key, json.dumps(task.to_dict()), ex=self._COMPLETED_TTL)
        else:
            self._client.set(key, json.dumps(task.to_dict()))


class _InMemoryTaskStore:
    """Thread-safe in-memory fallback when Redis is unavailable."""

    def __init__(self):
        import threading

        self._kv: dict[str, str] = {}
        self._ttl: dict[str, float] = {}
        self._sets: dict[str, set[str]] = {}
        self._lock = threading.Lock()

    def _purge_expired(self):
        now = time.time()
        expired = [k for k, exp in self._ttl.items() if exp <= now]
        for k in expired:
            self._kv.pop(k, None)
            self._ttl.pop(k, None)
            tid = k.removeprefix("task:")
            for s in self._sets.values():
                s.discard(tid)

    def get(self, key: str) -> str | None:
        with self._lock:
            self._purge_expired()
            return self._kv.get(key)

    def set(self, key: str, value: str, ex: int | None = None) -> bool:
        with self._lock:
            self._purge_expired()
            self._kv[key] = value
            if ex is not None:
                self._ttl[key] = time.time() + ex
            else:
                self._ttl.pop(key, None)
            return True

    def setex(self, key: str, ttl: int, value: str) -> bool:
        with self._lock:
            self._purge_expired()
            self._kv[key] = value
            self._ttl[key] = time.time() + ttl
            return True

    def delete(self, key: str) -> bool:
        with self._lock:
            self._kv.pop(key, None)
            self._ttl.pop(key, None)
            return True

    def sadd(self, name: str, value: str) -> int:
        with self._lock:
            s = self._sets.setdefault(name, set())
            if value not in s:
                s.add(value)
                return 1
            return 0

    def srem(self, name: str, value: str) -> int:
        with self._lock:
            s = self._sets.get(name)
            if s and value in s:
                s.remove(value)
                return 1
            return 0

    def smembers(self, name: str) -> set[str]:
        with self._lock:
            self._purge_expired()
            return set(self._sets.get(name, set()))

    def scard(self, name: str) -> int:
        with self._lock:
            self._purge_expired()
            return len(self._sets.get(name, set()))

    def expire(self, key: str, ttl: int) -> bool:
        with self._lock:
            if key in self._kv:
                self._ttl[key] = time.time() + ttl
            return True

    def persist(self, key: str) -> bool:
        with self._lock:
            self._ttl.pop(key, None)
            return True

    def ping(self) -> bool:
        return True
