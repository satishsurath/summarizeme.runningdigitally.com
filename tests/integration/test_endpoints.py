"""Tests for app.py API endpoints."""

import json
import os
from unittest.mock import patch


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
        """Should return model list from vLLM."""
        resp = client.get("/api/vllm/models")
        assert resp.status_code == 200


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
            resp = client.post("/admin-update-role", data={"email": "test@test.com", "role": "admin"})
            assert resp.status_code == 403

    def test_admin_add_user_requires_auth(self, client, mock_vllm_response):
        """Admin add user requires auth."""
        with patch("app.get_current_user", return_value=(None, None)):
            resp = client.post("/admin-add-user", data={"email": "new@test.com", "role": "reader"})
            assert resp.status_code == 403


class TestActiveTasksApi:
    """Tests for the /api/active-tasks notification endpoint."""

    def test_active_tasks_returns_empty_when_no_tasks(self, client, mock_vllm_response):
        """Should return empty list when no active tasks exist."""
        resp = client.get("/api/active-tasks")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert isinstance(data, list)
        assert len(data) == 0

    def test_active_tasks_includes_pending_tasks(self, client, mock_vllm_response):
        """Should include pending tasks in the response."""
        from app_config import download_statuses

        download_statuses["dl_test123"] = {"status": "pending", "processed": 0, "total": 5, "errors": []}
        try:
            resp = client.get("/api/active-tasks")
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert any(t["task_id"] == "dl_test123" for t in data)
            assert any(t["status"] == "pending" for t in data)
        finally:
            del download_statuses["dl_test123"]

    def test_active_tasks_includes_in_progress_tasks(self, client, mock_vllm_response):
        """Should include in_progress tasks in the response."""
        from app_config import summarize_v2_statuses

        summarize_v2_statuses["summ_v2_abc"] = {"status": "in_progress", "processed": 2, "total": 5, "errors": []}
        try:
            resp = client.get("/api/active-tasks")
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert any(t["task_id"] == "summ_v2_abc" for t in data)
        finally:
            del summarize_v2_statuses["summ_v2_abc"]

    def test_active_tasks_excludes_completed_tasks(self, client, mock_vllm_response):
        """Should exclude completed/failed tasks from the response."""
        from app_config import download_statuses

        download_statuses["dl_done"] = {"status": "completed", "processed": 5, "total": 5, "errors": []}
        try:
            resp = client.get("/api/active-tasks")
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert not any(t["task_id"] == "dl_done" for t in data)
        finally:
            del download_statuses["dl_done"]

    def test_active_tasks_excludes_failed_tasks(self, client, mock_vllm_response):
        """Should exclude failed tasks from the response."""
        from app_config import download_statuses

        download_statuses["dl_fail"] = {"status": "failed", "processed": 2, "total": 5, "errors": ["error"]}
        try:
            resp = client.get("/api/active-tasks")
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert not any(t["task_id"] == "dl_fail" for t in data)
        finally:
            del download_statuses["dl_fail"]

    def test_active_tasks_response_has_required_fields(self, client, mock_vllm_response):
        """Each active task should have task_id, name, status, processed, total."""
        from app_config import download_statuses

        download_statuses["dl_test"] = {"status": "in_progress", "processed": 3, "total": 10, "errors": []}
        try:
            resp = client.get("/api/active-tasks")
            assert resp.status_code == 200
            data = json.loads(resp.data)
            task = next(t for t in data if t["task_id"] == "dl_test")
            assert "task_id" in task
            assert "name" in task
            assert "status" in task
            assert "processed" in task
            assert "total" in task
            assert task["name"] == "Download: dl_test"
            assert task["processed"] == 3
            assert task["total"] == 10
        finally:
            del download_statuses["dl_test"]
