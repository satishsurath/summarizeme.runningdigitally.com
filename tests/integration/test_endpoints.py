"""Tests for app.py API endpoints."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest


class TestIndexPage:
    """Tests for the index page."""

    def test_index_page_returns_200(self, client, with_db):
        """Index page should return 200."""
        resp = client.get("/")
        assert resp.status_code == 200

    def test_index_page_shows_channels(self, client, with_db, mock_vllm_response):
        """API should list channels from DB."""
        from app import SessionLocal
        from db.models import VideoFolder

        session = SessionLocal()
        folder = VideoFolder(folder_name="test-channel", original_playlist_id="PL_test")
        session.add(folder)
        session.commit()
        session.close()

        resp = client.get("/api/channels")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert any(f["folder_name"] == "test-channel" for f in data)


class TestChannelApi:
    """Tests for channel CRUD endpoints."""

    def test_list_channels(self, client, with_db, mock_vllm_response):
        """GET /api/channels should return channel list."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from db.models import VideoFolder

        engine = create_engine(os.environ["DATABASE_URL"])
        Session = sessionmaker(bind=engine)
        session = Session()
        folder = VideoFolder(folder_name="channel-1", original_playlist_id="PL_1")
        session.add(folder)
        session.commit()
        session.close()

        resp = client.get("/api/channels")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert isinstance(data, list)

    def test_rename_channel_requires_auth(self, client, mock_vllm_response):
        """Renaming a channel requires admin role."""
        with patch("app.get_current_user", return_value=(None, None)):
            resp = client.post("/api/channels/rename", json={"old_name": "old", "new_name": "new"})
            assert resp.status_code == 403

    def test_rename_channel_validates_input(self, client, mock_vllm_response):
        """Renaming requires both old_name and new_name."""
        with patch("app.get_current_user", return_value=("admin@test.com", "admin")):
            resp = client.post("/api/channels/rename", json={"old_name": "old"})
            assert resp.status_code == 400

    def test_delete_channel_requires_auth(self, client, mock_vllm_response):
        """Deleting a channel requires admin role."""
        with patch("app.get_current_user", return_value=(None, None)):
            resp = client.post("/api/channels/delete", json={"name": "channel"})
            assert resp.status_code == 403

    def test_refresh_channel_requires_auth(self, client, mock_vllm_response):
        """Refreshing a channel requires admin or member role."""
        with patch("app.get_current_user", return_value=("reader@test.com", "reader")):
            resp = client.post("/api/channels/refresh", json={"channel_name": "test"})
            assert resp.status_code == 403


class TestSummarizeApi:
    """Tests for the summarize endpoint."""

    def test_summarize_requires_body(self, client, mock_vllm_response):
        """Summarize endpoint should reject missing body."""
        resp = client.post("/api/summarize_v2", json={})
        assert resp.status_code == 400

    def test_summarize_returns_task_id(self, client, with_db, mock_vllm_response):
        """Summarize endpoint should return a task ID."""
        resp = client.post(
            "/api/summarize_v2",
            json={
                "channel_name": "test-channel",
                "video_ids": ["vid1", "vid2"],
                "model": "nemo-qwen3.6-35b-a3b-nvfp4",
            },
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "task_id" in data
        assert data["status"] == "initiated"

    def test_summarize_status(self, client, with_db, mock_vllm_response):
        """Status endpoint should return task status."""
        with patch("app.get_current_user", return_value=("admin@test.com", "admin")):
            resp = client.post(
                "/api/summarize_v2",
                json={"channel_name": "test", "video_ids": ["vid1"]},
            )
            task_id = json.loads(resp.data)["task_id"]
            resp = client.get(f"/api/summarize_v2/status/{task_id}")
            assert resp.status_code == 200


class TestChatApi:
    """Tests for chat endpoints — focusing on the SQL injection fix."""

    def test_chat_channel_requires_body(self, client, mock_vllm_response):
        """Chat-channel should reject empty queries."""
        resp = client.post("/api/chat-channel/test-channel", json={})
        assert resp.status_code == 400

    def test_chat_video_requires_body(self, client, mock_vllm_response):
        """Chat-video should reject empty queries."""
        resp = client.post("/api/chat-video/vid1", json={})
        assert resp.status_code == 400


class TestVllmModels:
    """Tests for the vLLM models endpoint."""

    def test_vllm_models_returns_list(self, client, mock_vllm_response):
        """Should return model list from vLLM (mocked, no live HTTP)."""
        import blueprints.api as api_module

        embed_resp = MagicMock()
        embed_resp.json.return_value = {
            "data": [{"id": "nemo-nomic-embed-text-v1.5", "object": "model", "owned_by": "vllm"}]
        }
        embed_resp.raise_for_status.return_value = None
        gen_resp = MagicMock()
        gen_resp.json.return_value = {
            "data": [{"id": "nemo-qwen3.6-35b-a3b-nvfp4", "object": "model", "owned_by": "vllm"}]
        }
        gen_resp.raise_for_status.return_value = None
        with patch.object(api_module.requests, "get", side_effect=[embed_resp, gen_resp]) as mock_get:
            resp = client.get("/api/vllm/models")
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert isinstance(data["models"], list)
            # Both vLLM instances (embed + gen) are queried and their lists merged.
            assert mock_get.call_count == 2
            assert [m["id"] for m in data["models"]] == [
                "nemo-nomic-embed-text-v1.5",
                "nemo-qwen3.6-35b-a3b-nvfp4",
            ]


class TestAdminRoutes:
    """Tests for admin-only routes."""

    def test_admin_settings_requires_auth(self, client, mock_vllm_response):
        """Admin settings page requires auth."""
        with patch("app.get_current_user", return_value=(None, None)):
            resp = client.get("/admin-settings")
            assert resp.status_code == 403

    def test_admin_update_role_requires_auth(self, client, mock_vllm_response):
        """Admin role update requires auth."""
        with patch("app.get_current_user", return_value=(None, None)):
            resp = client.post("/admin-update-role", data={"user_id": "1", "role": "admin"})
            assert resp.status_code == 403

    def test_admin_add_user_requires_auth(self, client, mock_vllm_response):
        """Admin add user requires auth."""
        with patch("app.get_current_user", return_value=(None, None)):
            resp = client.post("/admin-add-user", data={"new_email": "new@test.com", "new_role": "reader"})
            assert resp.status_code == 403


class TestActiveTasksApi:
    """Tests for the /api/active-tasks notification endpoint."""

    @pytest.fixture(autouse=True)
    def isolate_task_statuses(self, monkeypatch):
        import blueprints.api as api_module
        from services.task_store import TaskStore

        monkeypatch.setattr(api_module, "task_store", TaskStore.in_memory())

    def test_active_tasks_returns_empty_when_no_tasks(self, client, mock_vllm_response):
        """Should return empty list when no active tasks exist."""
        resp = client.get("/api/active-tasks")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert isinstance(data, list)
        assert len(data) == 0

    def test_active_tasks_includes_pending_tasks(self, client, mock_vllm_response):
        """Should include pending tasks in the response."""
        import blueprints.api as api_module

        task_id = api_module.task_store.create_task("download")
        try:
            resp = client.get("/api/active-tasks")
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert any(t["task_id"] == task_id for t in data)
            assert any(t["status"] == "pending" for t in data)
        finally:
            api_module.task_store.delete_task(task_id)

    def test_active_tasks_includes_in_progress_tasks(self, client, mock_vllm_response):
        """Should include in_progress tasks in the response."""
        import blueprints.api as api_module

        store = api_module.task_store
        task_id = store.create_task("summarize", total=5)
        store.update_task(task_id, status="in_progress", processed=2)
        try:
            resp = client.get("/api/active-tasks")
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert any(t["task_id"] == task_id for t in data)
        finally:
            store.delete_task(task_id)

    def test_active_tasks_excludes_completed_tasks(self, client, mock_vllm_response):
        """Should exclude completed/failed tasks from the response."""
        import blueprints.api as api_module

        store = api_module.task_store
        task_id = store.create_task("download", total=5)
        store.update_task(task_id, status="completed", processed=5)
        try:
            resp = client.get("/api/active-tasks")
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert not any(t["task_id"] == task_id for t in data)
        finally:
            store.delete_task(task_id)

    def test_active_tasks_excludes_failed_tasks(self, client, mock_vllm_response):
        """Should exclude failed tasks from the response."""
        import blueprints.api as api_module

        store = api_module.task_store
        task_id = store.create_task("download", total=5)
        store.update_task(task_id, status="failed", errors=["error"])
        try:
            resp = client.get("/api/active-tasks")
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert not any(t["task_id"] == task_id for t in data)
        finally:
            store.delete_task(task_id)

    def test_active_tasks_response_has_required_fields(self, client, mock_vllm_response):
        """Each active task should have task_id, name, status, processed, total."""
        import blueprints.api as api_module

        store = api_module.task_store
        task_id = store.create_task("download", total=10)
        store.update_task(task_id, status="in_progress", processed=3)
        try:
            resp = client.get("/api/active-tasks")
            assert resp.status_code == 200
            data = json.loads(resp.data)
            task = next(t for t in data if t["task_id"] == task_id)
            assert "task_id" in task
            assert "name" in task
            assert "status" in task
            assert "processed" in task
            assert "total" in task
            assert task["name"] == f"Download: {task_id}"
            assert task["processed"] == 3
            assert task["total"] == 10
        finally:
            store.delete_task(task_id)
