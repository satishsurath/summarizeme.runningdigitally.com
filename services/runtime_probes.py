"""Runtime qualification probes for SGLang, vLLM, and embedding endpoints.

Validates served identities, reasoning parameters, structured output schemas, and embedding dimension/normalization.
"""

from __future__ import annotations

import logging
import math
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def probe_generation_endpoint(
    base_url: str,
    timeout_seconds: float = 5.0,
) -> dict[str, Any]:
    """Query /v1/models on a generation endpoint to discover available served models."""
    url = f"{base_url.rstrip('/')}/v1/models"
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                return {
                    "healthy": False,
                    "status_code": resp.status_code,
                    "error": f"Endpoint returned status {resp.status_code}: {resp.text[:200]}",
                    "models": [],
                }
            data = resp.json()
            models = [m.get("id") for m in data.get("data", []) if "id" in m]
            return {
                "healthy": True,
                "status_code": 200,
                "models": models,
            }
    except httpx.RequestError as exc:
        logger.warning("Generation probe failed for %s: %s", url, exc)
        return {
            "healthy": False,
            "error": f"Connection error: {exc!s}",
            "models": [],
        }


def probe_model_served_id(
    base_url: str,
    expected_model_id: str = "nemo-qwen3.8-27b-nvfp4",
    timeout_seconds: float = 5.0,
) -> tuple[bool, list[str]]:
    """Check whether expected_model_id is currently served by the endpoint."""
    result = probe_generation_endpoint(base_url, timeout_seconds=timeout_seconds)
    if not result.get("healthy"):
        return False, []
    models = result.get("models", [])
    return expected_model_id in models, models


def probe_reasoning_support(
    base_url: str,
    model_id: str,
    effort: str = "medium",
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    """Test whether endpoint accepts reasoning effort parameter and separates reasoning tokens."""
    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": "Reply with 'OK'."}],
        "max_tokens": 50,
        "temperature": 0.0,
    }
    if effort != "disabled":
        payload["reasoning_effort"] = effort

    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            resp = client.post(url, json=payload)
            if resp.status_code != 200:
                return {
                    "supported": False,
                    "status_code": resp.status_code,
                    "error": f"Reasoning probe returned {resp.status_code}: {resp.text[:200]}",
                }
            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                return {"supported": False, "error": "No choices returned in response"}

            msg = choices[0].get("message", {})
            reasoning_content = msg.get("reasoning_content") or msg.get("reasoning")
            content = msg.get("content", "")
            usage = data.get("usage", {})

            return {
                "supported": True,
                "status_code": 200,
                "has_reasoning_field": reasoning_content is not None,
                "content": content,
                "reasoning_content": reasoning_content,
                "reasoning_tokens": usage.get("completion_tokens_details", {}).get("reasoning_tokens", 0),
            }
    except httpx.RequestError as exc:
        return {
            "supported": False,
            "error": f"Connection error: {exc!s}",
        }


def probe_structured_output_support(
    base_url: str,
    model_id: str,
    json_schema: dict[str, Any] | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    """Test whether SGLang structured output / JSON schema mode is supported."""
    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    schema = json_schema or {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["success", "failed"]},
            "count": {"type": "integer"},
        },
        "required": ["status", "count"],
        "additionalProperties": False,
    }

    payload = {
        "model": model_id,
        "messages": [
            {
                "role": "user",
                "content": "Generate JSON matching schema: status is success, count is 42.",
            }
        ],
        "max_tokens": 100,
        "temperature": 0.0,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "test_schema", "strict": True, "schema": schema},
        },
    }

    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            resp = client.post(url, json=payload)
            if resp.status_code != 200:
                return {
                    "supported": False,
                    "status_code": resp.status_code,
                    "error": f"Structured output probe returned {resp.status_code}: {resp.text[:200]}",
                }
            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                return {"supported": False, "error": "No choices returned"}

            content = choices[0].get("message", {}).get("content", "")
            return {
                "supported": True,
                "status_code": 200,
                "content": content,
            }
    except httpx.RequestError as exc:
        return {
            "supported": False,
            "error": f"Connection error: {exc!s}",
        }


def probe_embedding_endpoint(
    base_url: str,
    model_id: str = "nemo-nomic-embed-text-v1.5",
    test_text: str = "search_document: probe test vector",
    expected_dim: int = 768,
    timeout_seconds: float = 5.0,
) -> dict[str, Any]:
    """Test embedding endpoint for expected dimensions, finite values, and normalization."""
    url = f"{base_url.rstrip('/')}/v1/embeddings"
    payload = {
        "model": model_id,
        "input": test_text,
    }

    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            resp = client.post(url, json=payload)
            if resp.status_code != 200:
                return {
                    "healthy": False,
                    "status_code": resp.status_code,
                    "error": f"Embedding probe returned {resp.status_code}: {resp.text[:200]}",
                }
            data = resp.json()
            embeddings = data.get("data", [])
            if not embeddings or "embedding" not in embeddings[0]:
                return {"healthy": False, "error": "No embedding vector in response"}

            vec: list[float] = embeddings[0]["embedding"]
            dim = len(vec)
            if dim != expected_dim:
                return {
                    "healthy": False,
                    "error": f"Vector dimension mismatch: got {dim}, expected {expected_dim}",
                    "dimension": dim,
                }

            # Check finite values
            if any(math.isnan(x) or math.isinf(x) for x in vec):
                return {"healthy": False, "error": "Vector contains NaN or Inf values"}

            # Check L2 normalization (norm should be close to 1.0)
            norm = math.sqrt(sum(x * x for x in vec))
            is_normalized = abs(norm - 1.0) < 0.05

            return {
                "healthy": True,
                "status_code": 200,
                "dimension": dim,
                "norm": norm,
                "is_normalized": is_normalized,
            }
    except httpx.RequestError as exc:
        return {
            "healthy": False,
            "error": f"Connection error: {exc!s}",
        }
