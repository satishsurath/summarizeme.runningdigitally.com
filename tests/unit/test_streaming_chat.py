"""Tests for streaming chat capabilities (vllm_generate_stream and Flask SSE routes)."""

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from blueprints.chat import chat_bp
from summarizer_v2 import vllm_generate_stream


@pytest.fixture
def chat_app():
    """Create a minimal Flask app for testing chat streaming routes."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(chat_bp)
    return app


class TestVllmGenerateStream:
    """Unit tests for vllm_generate_stream generator function."""

    @patch("summarizer_v2._OpenAI")
    @patch("summarizer_v2._HAS_OPENAI", True)
    def test_vllm_generate_stream_openai_success(self, mock_openai_cls):
        """Test streaming chunks via OpenAI SDK when base_url is properly formatted."""
        mock_chunk_1 = MagicMock()
        mock_chunk_1.choices = [MagicMock()]
        mock_chunk_1.choices[0].delta.content = "Hello "
        mock_chunk_1.choices[0].delta.reasoning = None

        mock_chunk_2 = MagicMock()
        mock_chunk_2.choices = [MagicMock()]
        mock_chunk_2.choices[0].delta.content = "world!"
        mock_chunk_2.choices[0].delta.reasoning = None

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = [mock_chunk_1, mock_chunk_2]
        mock_openai_cls.return_value = mock_client

        chunks = list(vllm_generate_stream("test-model", "test prompt"))

        # Verify OpenAI client was initialized with /v1 URL
        mock_openai_cls.assert_called_once()
        _, kwargs = mock_openai_cls.call_args
        assert kwargs["base_url"].endswith("/v1")

        # Verify chunks returned (delta, is_done)
        assert len(chunks) == 3
        assert chunks[0] == ("Hello ", False)
        assert chunks[1] == ("world!", False)
        assert chunks[2] == ("", True)

    @patch("summarizer_v2._HAS_OPENAI", False)
    def test_vllm_generate_stream_no_openai(self):
        """Test behavior when OpenAI SDK is not installed."""
        chunks = list(vllm_generate_stream("test-model", "test prompt"))
        assert chunks == [("", True)]


class TestChatStreamingRoutes:
    """Unit tests for Flask SSE streaming chat routes."""

    def test_chat_channel_stream_missing_query(self, chat_app):
        """Test channel stream route with missing user query."""
        client = chat_app.test_client()
        resp = client.post(
            "/api/chat-channel/test-channel/stream",
            json={"query": ""},
        )
        assert resp.status_code == 200
        assert resp.content_type == "text/event-stream"
        assert resp.headers["Cache-Control"] == "no-cache, no-transform"
        assert resp.headers["X-Accel-Buffering"] == "no"
        data = resp.get_data(as_text=True)
        assert "event: loading" in data
        assert "event: error" in data
        assert "No query provided" in data

    def test_chat_video_stream_missing_query(self, chat_app):
        """Test video stream route with missing user query."""
        client = chat_app.test_client()
        resp = client.post(
            "/api/chat-video/test-video-123/stream",
            json={"query": ""},
        )
        assert resp.status_code == 200
        assert resp.content_type == "text/event-stream"
        assert resp.headers["Cache-Control"] == "no-cache, no-transform"
        assert resp.headers["X-Accel-Buffering"] == "no"
        data = resp.get_data(as_text=True)
        assert "event: loading" in data
        assert "event: error" in data
        assert "No query provided" in data
