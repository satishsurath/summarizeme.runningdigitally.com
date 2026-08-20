"""Unit tests for services/task_store.py (TaskStore, in-memory and Redis-backed)."""

import json

import pytest

from services.task_store import TaskInfo, TaskStore, _InMemoryTaskStore


class FakeRedis:
    """Minimal in-process stand-in for redis.Redis covering the TaskStore API."""

    def __init__(self):
        self.kv: dict[str, str] = {}
        self.ttls: dict[str, int] = {}
        self.sets: dict[str, set[str]] = {}
        self.persisted: list[str] = []
        self.expired: list[str] = []

    def ping(self):
        return True

    def get(self, key):
        return self.kv.get(key)

    def set(self, key, value, ex=None):
        self.kv[key] = value
        if ex is not None:
            self.ttls[key] = ex
        return True

    def delete(self, key):
        existed = key in self.kv
        self.kv.pop(key, None)
        self.ttls.pop(key, None)
        return existed

    def sadd(self, name, value):
        s = self.sets.setdefault(name, set())
        added = value not in s
        s.add(value)
        return int(added)

    def srem(self, name, value):
        s = self.sets.get(name, set())
        removed = value in s
        s.discard(value)
        return int(removed)

    def smembers(self, name):
        return set(self.sets.get(name, set()))

    def scard(self, name):
        return len(self.sets.get(name, set()))

    def expire(self, key, ttl):
        self.expired.append(key)
        self.ttls[key] = ttl
        return True

    def persist(self, key):
        self.persisted.append(key)
        self.ttls.pop(key, None)
        return True


class TestTaskInfo:
    def test_progress_percent(self):
        t = TaskInfo(
            task_id="x", task_type="download", status="pending", created_at=0, updated_at=0, total=4, processed=1
        )
        assert t.progress_percent == 25.0

    def test_progress_percent_zero_total(self):
        t = TaskInfo(task_id="x", task_type="download", status="pending", created_at=0, updated_at=0)
        assert t.progress_percent == 0.0

    def test_dict_round_trip(self):
        t = TaskInfo(
            task_id="x",
            task_type="summarize",
            status="in_progress",
            created_at=1.0,
            updated_at=2.0,
            total=3,
            processed=1,
            errors=["e1"],
            metadata={"a": 1},
        )
        assert TaskInfo.from_dict(t.to_dict()) == t


class TestTaskStoreInMemory:
    @pytest.fixture
    def store(self):
        return TaskStore.in_memory()

    def test_create_and_get(self, store):
        task_id = store.create_task("download", {"channel_url": "https://x"}, total=5)
        assert task_id.startswith("dl_")
        task = store.get_task(task_id)
        assert task is not None
        assert task.task_type == "download"
        assert task.status == "pending"
        assert task.total == 5
        assert task.metadata == {"channel_url": "https://x"}

    def test_get_unknown_task(self, store):
        assert store.get_task("nope") is None

    def test_update_status_moves_between_sets(self, store):
        task_id = store.create_task("summarize")
        assert store.get_task(task_id).status == "pending"
        assert store.update_task(task_id, status="in_progress") is True
        assert store.get_task(task_id).status == "in_progress"
        assert store.update_task(task_id, status="completed", processed=1) is True
        task = store.get_task(task_id)
        assert task.status == "completed"
        assert task.processed == 1
        # Completed tasks no longer listed as active
        assert all(t.task_id != task_id for t in store.list_tasks(status="in_progress"))
        assert any(t.task_id == task_id for t in store.list_tasks(status="completed"))

    def test_update_unknown_task_returns_false(self, store):
        assert store.update_task("missing", status="completed") is False

    def test_list_tasks_filters_by_type(self, store):
        dl = store.create_task("download")
        su = store.create_task("summarize")
        downloads = store.list_tasks(task_type="download")
        assert [t.task_id for t in downloads] == [dl]
        assert [t.task_id for t in store.list_tasks(task_type="summarize")] == [su]

    def test_delete_task(self, store):
        task_id = store.create_task("download")
        assert store.delete_task(task_id) is True
        assert store.get_task(task_id) is None
        assert store.delete_task(task_id) is False

    def test_counts(self, store):
        a = store.create_task("download")
        b = store.create_task("summarize")
        store.update_task(a, status="completed")
        store.update_task(b, status="failed", errors=["boom"])
        assert store.get_completed_count() == 1
        assert store.get_failed_count() == 1
        assert store.get_active_count() == 0

    def test_errors_replaced_not_appended(self, store):
        task_id = store.create_task("download")
        store.update_task(task_id, errors=["e1"])
        store.update_task(task_id, errors=["e2"])
        assert store.get_task(task_id).errors == ["e2"]


class TestTaskStoreRedis:
    @pytest.fixture
    def fake(self):
        return FakeRedis()

    @pytest.fixture
    def store(self, fake):
        return TaskStore(redis_client=fake)

    def test_create_writes_task_key_and_active_set(self, store, fake):
        task_id = store.create_task("download", total=2)
        key = f"task:{task_id}"
        assert key in fake.kv
        assert task_id in fake.sets["tasks:active"]
        stored = json.loads(fake.kv[key])
        assert stored["task_type"] == "download"
        assert stored["total"] == 2

    def test_completed_task_gets_ttl_and_moves_sets(self, store, fake):
        task_id = store.create_task("summarize")
        store.update_task(task_id, status="completed")
        key = f"task:{task_id}"
        assert task_id not in fake.sets["tasks:active"]
        assert task_id in fake.sets["tasks:completed"]
        assert key in fake.expired
        assert fake.ttls[key] == TaskStore._COMPLETED_TTL

    def test_reactivating_task_persists_and_returns_to_active(self, store, fake):
        task_id = store.create_task("download")
        store.update_task(task_id, status="completed")
        store.update_task(task_id, status="in_progress")
        key = f"task:{task_id}"
        assert task_id in fake.sets["tasks:active"]
        assert task_id not in fake.sets["tasks:completed"]
        assert key in fake.persisted

    def test_delete_task_removes_from_all_sets(self, store, fake):
        task_id = store.create_task("download")
        store.update_task(task_id, status="failed")
        store.delete_task(task_id)
        assert f"task:{task_id}" not in fake.kv
        for name in ("tasks:active", "tasks:completed", "tasks:failed"):
            assert task_id not in fake.sets.get(name, set())


class TestInMemoryTtl:
    def test_expired_key_is_purged(self, monkeypatch):
        import time

        real_time = time.time
        backend = _InMemoryTaskStore()
        backend.set("task:t1", "x", ex=1)
        backend.sadd("tasks:active", "t1")
        # Fast-forward past the TTL (offset from the real clock, no recursion)
        monkeypatch.setattr(time, "time", lambda: real_time() + 10)
        assert backend.get("task:t1") is None
        assert "t1" not in backend.smembers("tasks:active")

    def test_persist_removes_ttl(self, monkeypatch):
        import time

        real_time = time.time
        backend = _InMemoryTaskStore()
        backend.set("task:t1", "x", ex=1)
        backend.persist("task:t1")
        monkeypatch.setattr(time, "time", lambda: real_time() + 10)
        assert backend.get("task:t1") == "x"
