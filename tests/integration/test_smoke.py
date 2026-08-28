"""Durable integration smoke tests.

Validates core Flask routes, dev authentication, model registry responses,
and schema contracts.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch


class TestDurableSmokeSuite:
    """Suite of durable integration smoke checks."""

    def test_health_check_returns_200(self, client):
        """GET /health must return status 200 with status=healthy."""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data.get("status") == "healthy"

    def test_root_index_page_returns_200(self, client, with_db):
        """GET / must render the HTML dashboard."""
        resp = client.get("/", headers={"X-Dev-User": "test@example.com"})
        assert resp.status_code == 200
        assert b"<!DOCTYPE html>" in resp.data or b"<html" in resp.data

    def test_api_channels_returns_list(self, client, with_db):
        """GET /api/channels must return a valid JSON array."""
        resp = client.get("/api/channels", headers={"X-Dev-User": "test@example.com"})
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert isinstance(data, list)

    def test_api_models_returns_registered_models(self, client, with_db):
        """GET /api/models must return active qualified models."""
        resp = client.get("/api/models", headers={"X-Dev-User": "test@example.com"})
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "models" in data
        assert isinstance(data["models"], list)

    def test_api_vllm_models_discovery_returns_catalog(self, client, with_db):
        """GET /api/vllm/models returns discovered models with mock/live fallback."""
        with patch("services.model_registry.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "data": [
                    {"id": "nemo-qwen3.8-27b-nvfp4", "object": "model"},
                    {"id": "nemo-nomic-embed-text-v1.5", "object": "model"},
                ]
            }
            mock_client.__enter__.return_value.get.return_value = mock_response
            mock_client_cls.return_value = mock_client

            resp = client.get("/api/vllm/models", headers={"X-Dev-User": "test@example.com"})
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert "models" in data
            assert isinstance(data["models"], list)

    def test_api_user_preference_get_and_post(self, client, with_db):
        """GET and POST /api/user/preference must persist user AI preferences."""
        # 1. GET initial default
        resp = client.get("/api/user/preference", headers={"X-Dev-User": "test@example.com"})
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "preferred_gen_model" in data
        assert "preferred_reasoning_effort" in data

        # 2. POST update preference
        update_payload = {
            "model_name": "nemo-qwen3.8-27b-nvfp4",
            "reasoning_effort": "high",
        }
        post_resp = client.post(
            "/api/user/preference",
            data=json.dumps(update_payload),
            content_type="application/json",
            headers={"X-Dev-User": "test@example.com"},
        )
        assert post_resp.status_code == 200
        post_data = json.loads(post_resp.data)
        assert post_data.get("preferred_gen_model") == "nemo-qwen3.8-27b-nvfp4"
        assert post_data.get("preferred_reasoning_effort") == "high"

    def test_api_active_and_all_tasks(self, client, with_db):
        """GET /api/active-tasks and /api/all-tasks must return lists without error."""
        resp1 = client.get("/api/active-tasks", headers={"X-Dev-User": "test@example.com"})
        assert resp1.status_code == 200
        assert isinstance(json.loads(resp1.data), list)

        resp2 = client.get("/api/all-tasks", headers={"X-Dev-User": "test@example.com"})
        assert resp2.status_code == 200
        assert isinstance(json.loads(resp2.data), list)

    def test_openapi_schema_endpoint(self, client):
        """GET /openapi/openapi.json returns valid OpenAPI 3 document."""
        resp = client.get("/openapi/openapi.json")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "openapi" in data
        assert data.get("info", {}).get("title") == "SummarizeMe API"
