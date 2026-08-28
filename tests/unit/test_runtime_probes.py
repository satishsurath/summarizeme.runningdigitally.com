"""Unit tests for services/runtime_probes.py qualification probes."""

from __future__ import annotations

import math
from unittest.mock import MagicMock, patch

import httpx

from services.runtime_probes import (
    probe_embedding_endpoint,
    probe_generation_endpoint,
    probe_model_served_id,
    probe_reasoning_support,
    probe_structured_output_support,
)


class TestRuntimeProbes:
    """Test runtime probing functions against mocked HTTP responses."""

    @patch("httpx.Client.get")
    def test_probe_generation_endpoint_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"id": "nemo-qwen3.8-27b-nvfp4"},
                {"id": "nemo-nomic-embed-text-v1.5"},
            ]
        }
        mock_get.return_value = mock_response

        result = probe_generation_endpoint("http://localhost:8000")
        assert result["healthy"] is True
        assert result["status_code"] == 200
        assert "nemo-qwen3.8-27b-nvfp4" in result["models"]

    @patch("httpx.Client.get")
    def test_probe_generation_endpoint_connection_failure(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("Connection refused")

        result = probe_generation_endpoint("http://localhost:8000")
        assert result["healthy"] is False
        assert "Connection error" in result["error"]

    @patch("httpx.Client.get")
    def test_probe_model_served_id_match(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"id": "nemo-qwen3.8-27b-nvfp4"}]}
        mock_get.return_value = mock_response

        matched, models = probe_model_served_id("http://localhost:8000", "nemo-qwen3.8-27b-nvfp4")
        assert matched is True
        assert models == ["nemo-qwen3.8-27b-nvfp4"]

    @patch("httpx.Client.get")
    def test_probe_model_served_id_drift_detected(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"id": "nemo-qwen3.6-35b-a3b-nvfp4"}]}
        mock_get.return_value = mock_response

        matched, models = probe_model_served_id("http://localhost:8000", "nemo-qwen3.8-27b-nvfp4")
        assert matched is False
        assert "nemo-qwen3.6-35b-a3b-nvfp4" in models

    @patch("httpx.Client.post")
    def test_probe_reasoning_support_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "OK",
                        "reasoning_content": "Analyzing input request...",
                    }
                }
            ],
            "usage": {
                "completion_tokens_details": {
                    "reasoning_tokens": 12,
                }
            },
        }
        mock_post.return_value = mock_response

        result = probe_reasoning_support("http://localhost:8000", "nemo-qwen3.8-27b-nvfp4", effort="medium")
        assert result["supported"] is True
        assert result["has_reasoning_field"] is True
        assert result["reasoning_tokens"] == 12

    @patch("httpx.Client.post")
    def test_probe_structured_output_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": [{"message": {"content": '{"status": "success", "count": 42}'}}]}
        mock_post.return_value = mock_response

        result = probe_structured_output_support("http://localhost:8000", "nemo-qwen3.8-27b-nvfp4")
        assert result["supported"] is True
        assert "42" in result["content"]

    @patch("httpx.Client.post")
    def test_probe_embedding_endpoint_success(self, mock_post):
        # Create a normalized 768-dim mock vector
        dim = 768
        raw_val = 1.0 / math.sqrt(dim)
        mock_vec = [raw_val] * dim

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"embedding": mock_vec}]}
        mock_post.return_value = mock_response

        result = probe_embedding_endpoint("http://localhost:8001", expected_dim=768)
        assert result["healthy"] is True
        assert result["dimension"] == 768
        assert result["is_normalized"] is True

    @patch("httpx.Client.post")
    def test_probe_embedding_dimension_mismatch(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"embedding": [0.1, 0.2, 0.3]}]}
        mock_post.return_value = mock_response

        result = probe_embedding_endpoint("http://localhost:8001", expected_dim=768)
        assert result["healthy"] is False
        assert "dimension mismatch" in result["error"]
