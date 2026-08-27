"""Unit tests for Phase 5 chat and model registry REST endpoints."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from blueprints.api import api_bp
from blueprints.chat import chat_bp
from db.models import Base


@pytest.fixture
def phase5_app():
    """Create Flask test application with api and chat blueprints."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    app.register_blueprint(api_bp)
    app.register_blueprint(chat_bp)

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session() as s:
        from db.models import User

        s.add(User(email="dev@localhost", role="admin"))
        s.commit()

    with (
        patch("app_config.SessionLocal", Session),
        patch("blueprints.api.SessionLocal", Session),
        patch("blueprints.chat.SessionLocal", Session),
    ):
        yield app


class TestPhase5Endpoints:
    """Test suite for Phase 5 REST endpoints."""

    @patch("auth_utils.get_user_email_dev_mode", return_value="dev@localhost")
    def test_api_models_endpoint(self, mock_user, phase5_app):
        client = phase5_app.test_client()
        resp = client.get("/api/models")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "models" in data
        assert len(data["models"]) >= 1
        assert "qwen" in data["models"][0]["family"].lower()

    @patch("auth_utils.get_user_email_dev_mode", return_value="dev@localhost")
    def test_api_user_preference_roundtrip(self, mock_user, phase5_app):
        client = phase5_app.test_client()

        # Set preference
        post_resp = client.post(
            "/api/user/preference",
            json={"model_name": "custom-qwen-35b", "reasoning_effort": "xhigh"},
        )
        assert post_resp.status_code == 200
        post_data = post_resp.get_json()
        assert post_data["preferred_gen_model"] == "custom-qwen-35b"
        assert post_data["preferred_reasoning_effort"] == "xhigh"

        # Get preference
        get_resp = client.get("/api/user/preference")
        assert get_resp.status_code == 200
        get_data = get_resp.get_json()
        assert get_data["preferred_gen_model"] == "custom-qwen-35b"
        assert get_data["preferred_reasoning_effort"] == "xhigh"

    @patch("auth_utils.get_user_email_dev_mode", return_value="dev@localhost")
    def test_api_conversations_create_and_list(self, mock_user, phase5_app):
        client = phase5_app.test_client()

        # Create conversation
        post_resp = client.post(
            "/api/conversations",
            json={"title": "Postgres Q&A", "scope_type": "video", "scope_id": "v123"},
        )
        assert post_resp.status_code == 200
        post_data = post_resp.get_json()
        assert post_data["title"] == "Postgres Q&A"
        assert post_data["scope_type"] == "video"
        assert "id" in post_data

        # List conversations
        list_resp = client.get("/api/conversations")
        assert list_resp.status_code == 200
        list_data = list_resp.get_json()
        assert len(list_data) == 1
        assert list_data[0]["id"] == post_data["id"]
