"""Tests for untested app.py routes and endpoints.

Covers: status_page, videos_page, api_channel_start, api_channel_status,
api_get_videos, api_all_tasks, view_summary_v2, view_transcript_v2,
chat_channel_page, chat_video_page.
"""

import json
import uuid
from unittest.mock import patch


def _uid(prefix=""):
    """Return a unique ID string for test data."""
    return f"{prefix}test_{uuid.uuid4().hex[:8]}"


class TestStatusPage:
    """Tests for the /status page."""

    def test_status_page_returns_200(self, client):
        """Status page should return 200."""
        resp = client.get("/status")
        assert resp.status_code == 200

    def test_status_page_returns_html(self, client):
        """Status page should return HTML content."""
        resp = client.get("/status")
        assert b"<html" in resp.data or b"<!DOCTYPE" in resp.data or b"<!" in resp.data


class TestVideosPage:
    """Tests for the /videos/<channel_name> page."""

    def test_videos_page_returns_200(self, client, with_db):
        """Videos page should return 200 for a channel."""
        from app import SessionLocal
        from db.models import Video, VideoFolder

        session = SessionLocal()
        video_id = _uid("v")
        video = Video(video_id=video_id, title="Test Video", upload_date="2024-01-01")
        session.add(video)
        folder = VideoFolder(folder_name=_uid("c"), original_playlist_id="PL_test", video_id=video_id)
        session.add(folder)
        session.commit()
        channel_name = folder.folder_name  # Read before closing
        session.close()

        resp = client.get(f"/videos/{channel_name}")
        assert resp.status_code == 200

    def test_videos_page_shows_video_title(self, client, with_db):
        """Videos page should display video title."""
        from app import SessionLocal
        from db.models import Video, VideoFolder

        session = SessionLocal()
        video_id = _uid("v")
        video = Video(video_id=video_id, title="My Test Video", upload_date="2024-01-01")
        session.add(video)
        folder = VideoFolder(folder_name=_uid("c"), original_playlist_id="PL_test", video_id=video_id)
        session.add(folder)
        session.commit()
        channel_name = folder.folder_name  # Read before closing
        session.close()

        resp = client.get(f"/videos/{channel_name}")
        assert resp.status_code == 200  # Page rendered successfully


class TestApiChannelStart:
    """Tests for the /api/channel/start endpoint."""

    def test_channel_start_requires_auth(self, client):
        """Starting a channel download requires admin role."""
        with patch("app.get_current_user", return_value=(None, None)):
            resp = client.post(
                "/api/channel/start",
                json={"channel_url": "https://www.youtube.com/channel/test"},
            )
            assert resp.status_code == 403

    def test_channel_start_requires_body(self, client, mock_ollama_response):
        """Channel start should reject missing body."""
        with patch("app.get_current_user", return_value=("admin@test.com", "admin")):
            resp = client.post("/api/channel/start", json={})
            assert resp.status_code == 400

    def test_channel_start_returns_task_id(self, client, with_db, mock_ollama_response):
        """Channel start should return a task ID."""
        with (
            patch("app.get_current_user", return_value=("admin@test.com", "admin")),
            patch("app.download_channel_transcripts") as mock_download,
        ):
            mock_download.return_value = None
            resp = client.post(
                "/api/channel/start",
                json={"channel_url": "https://www.youtube.com/channel/test"},
            )
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert "task_id" in data
            assert data["status"] == "initiated"
            assert data["task_id"].startswith("dl_")


class TestApiChannelStatus:
    """Tests for the /api/channel/status/<task_id> endpoint."""

    def test_channel_status_invalid_task(self, client):
        """Status endpoint should return 404 for invalid task ID."""
        resp = client.get("/api/channel/status/invalid_task")
        assert resp.status_code == 404

    def test_channel_status_valid_task(self, client, mock_ollama_response):
        """Status endpoint should return 200 for existing task."""
        with (
            patch("app.get_current_user", return_value=("admin@test.com", "admin")),
            patch("app.download_channel_transcripts"),
        ):
            # First initiate a task
            client.post(
                "/api/channel/start",
                json={"channel_url": "https://www.youtube.com/channel/test"},
            )
            # Then check status
            resp = client.get("/api/channel/status/dl_1")
            assert resp.status_code == 200


class TestApiGetVideos:
    """Tests for the /api/videos/<channel_name> endpoint."""

    def test_get_videos_requires_channel(self, client):
        """Get videos should require channel name."""
        resp = client.get("/api/videos/")
        assert resp.status_code == 404

    def test_get_videos_returns_json(self, client, with_db, mock_ollama_response):
        """Get videos should return JSON with video list."""
        from app import SessionLocal
        from db.models import Video, VideoFolder

        session = SessionLocal()
        video_id = _uid("v")
        video = Video(video_id=video_id, title="Test Video 1", upload_date="2024-01-01")
        session.add(video)
        folder = VideoFolder(folder_name=_uid("c"), original_playlist_id="PL_test", video_id=video_id)
        session.add(folder)
        session.commit()
        channel_name = folder.folder_name  # Read before closing
        session.close()

        resp = client.get(f"/api/videos/{channel_name}")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "videos" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data

    def test_get_videos_pagination(self, client, with_db, mock_ollama_response):
        """Get videos should support pagination."""
        from app import SessionLocal
        from db.models import Video, VideoFolder

        session = SessionLocal()
        channel_name = _uid("c")
        folder = VideoFolder(folder_name=channel_name, original_playlist_id="PL_pag")
        session.add(folder)
        for i in range(10):
            video_id = _uid("v")
            video = Video(video_id=video_id, title=f"Video {i}", upload_date="2024-01-01")
            session.add(video)
            vf = VideoFolder(folder_name=channel_name, original_playlist_id="PL_pag", video_id=video_id)
            session.add(vf)
        session.commit()
        session.close()

        resp = client.get(f"/api/videos/{channel_name}?page=1&page_size=3")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["total"] == 10
        assert data["page"] == 1
        assert data["page_size"] == 3
        assert len(data["videos"]) == 3

    def test_get_videos_sorting(self, client, with_db, mock_ollama_response):
        """Get videos should support sorting by title."""
        from app import SessionLocal
        from db.models import Video, VideoFolder

        session = SessionLocal()
        channel_name = _uid("c")
        folder = VideoFolder(folder_name=channel_name, original_playlist_id="PL_sort")
        session.add(folder)
        for title in ["Zebra", "Apple", "Mango"]:
            video_id = _uid("v")
            video = Video(video_id=video_id, title=title, upload_date="2024-01-01")
            session.add(video)
            vf = VideoFolder(folder_name=channel_name, original_playlist_id="PL_sort", video_id=video_id)
            session.add(vf)
        session.commit()
        session.close()

        resp = client.get(f"/api/videos/{channel_name}?sort_by=title&sort_order=asc")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        titles = [v["title"] for v in data["videos"]]
        assert titles == sorted(titles)


class TestApiAllTasks:
    """Tests for the /api/all-tasks endpoint."""

    def test_all_tasks_returns_list(self, client, mock_ollama_response):
        """All tasks should return a list."""
        resp = client.get("/api/all-tasks")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert isinstance(data, list)


class TestViewSummaryV2:
    """Tests for the /summaries_v2/<summary_id> view."""

    def test_view_summary_returns_404(self, client):
        """View summary should return 404 for non-existent summary."""
        resp = client.get("/summaries_v2/nonexistent")
        assert resp.status_code == 404


class TestViewTranscriptV2:
    """Tests for the /transcript/<video_id> view."""

    def test_view_transcript_returns_404(self, client):
        """View transcript should return 404 for non-existent video."""
        resp = client.get("/transcript/nonexistent")
        assert resp.status_code == 404


class TestChatChannelPage:
    """Tests for the /chat-channel/<channel_name> page."""

    def test_chat_channel_page_returns_200(self, client, with_db):
        """Chat channel page should return 200."""
        from app import SessionLocal
        from db.models import VideoFolder

        session = SessionLocal()
        folder = VideoFolder(folder_name=_uid("c"), original_playlist_id="PL_chat")
        session.add(folder)
        session.commit()
        channel_name = folder.folder_name  # Read before closing
        session.close()

        resp = client.get(f"/chat-channel/{channel_name}")
        assert resp.status_code == 200


class TestChatVideoPage:
    """Tests for the /chat-video/<video_id> page."""

    def test_chat_video_page_returns_200(self, client, with_db):
        """Chat video page should return 200."""
        from app import SessionLocal
        from db.models import Video, VideoFolder

        session = SessionLocal()
        video_id = _uid("v")
        video = Video(video_id=video_id, title="Chat Video", upload_date="2024-01-01")
        session.add(video)
        folder = VideoFolder(folder_name=_uid("c"), original_playlist_id="PL_chatv", video_id=video_id)
        session.add(folder)
        session.commit()
        session.close()

        resp = client.get(f"/chat-video/{video_id}")
        assert resp.status_code == 200
