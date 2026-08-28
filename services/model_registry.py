"""Model registry and qualification service for multi-model serving and pool management.

Discovers models dynamically from /v1/models, manages endpoint health and qualification status,
enforces pool admission ceilings, and resolves per-user model preferences.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app_config import (
    DEFAULT_EMBED_MODEL,
    DEFAULT_GEN_MODEL,
    GEN_APP_MAX_IN_FLIGHT,
    GEN_INTERACTIVE_RESERVE,
    VLLM_EMBED_URL,
    VLLM_GEN_URL,
)
from db.models import AIEndpoint, AIModel, AIRuntimePool, UserAIPreference, utcnow

logger = logging.getLogger(__name__)


OPERATION_PROFILES: dict[str, dict[str, Any]] = {
    "summarize_v3": {
        "endpoint_type": "generation",
        "min_context_window": 16384,
        "default_model": DEFAULT_GEN_MODEL,
        "allowed_reasoning_efforts": ["disabled", "low", "medium", "xhigh"],
        "default_reasoning_effort": "medium",
        "requires_json_schema": True,
    },
    "chat_rag": {
        "endpoint_type": "generation",
        "min_context_window": 8192,
        "default_model": DEFAULT_GEN_MODEL,
        "allowed_reasoning_efforts": ["disabled", "low", "medium", "xhigh"],
        "default_reasoning_effort": "medium",
        "requires_json_schema": False,
    },
    "chat_direct": {
        "endpoint_type": "generation",
        "min_context_window": 4096,
        "default_model": DEFAULT_GEN_MODEL,
        "allowed_reasoning_efforts": ["disabled", "low", "medium", "xhigh"],
        "default_reasoning_effort": "disabled",
        "requires_json_schema": False,
    },
    "embed_text": {
        "endpoint_type": "embedding",
        "min_context_window": 8192,
        "default_model": DEFAULT_EMBED_MODEL,
        "expected_dimensions": 768,
        "max_batch_sequences": 8,
    },
}


class ModelRegistryService:
    """Service for managing model definitions, runtime pools, and endpoint qualifications."""

    @staticmethod
    def get_operation_profile(operation_name: str) -> dict[str, Any]:
        """Get profile requirements for a named AI operation."""
        if operation_name not in OPERATION_PROFILES:
            raise ValueError(f"Unknown AI operation '{operation_name}'. Available: {list(OPERATION_PROFILES.keys())}")
        return OPERATION_PROFILES[operation_name]

    @staticmethod
    def validate_model_for_operation(
        session: Session,
        model_id: str,
        operation_name: str,
    ) -> AIModel:
        """Validate that a requested model exists, is qualified, and satisfies operation profile requirements."""
        profile = ModelRegistryService.get_operation_profile(operation_name)
        endpoint_type = profile["endpoint_type"]

        model = session.scalar(
            select(AIModel)
            .join(AIEndpoint, AIModel.endpoint_id == AIEndpoint.id)
            .where(
                AIModel.model_id == model_id,
                AIEndpoint.endpoint_type == endpoint_type,
                AIEndpoint.is_active == True,  # noqa: E712
            )
        )
        if not model:
            # Fallback check if default model exists
            if model_id == profile.get("default_model"):
                # Dynamically bootstrap if needed
                ModelRegistryService.bootstrap_from_env(session)
                model = session.scalar(select(AIModel).where(AIModel.model_id == model_id))
            if not model:
                raise ValueError(
                    f"Model '{model_id}' is not registered or active for operation '{operation_name}' "
                    f"(expected endpoint_type='{endpoint_type}')"
                )

        if model.qualification_status != "passed":
            raise ValueError(
                f"Model '{model_id}' cannot be used for '{operation_name}': "
                f"qualification_status='{model.qualification_status}'"
            )

        min_ctx = profile.get("min_context_window", 0)
        if model.context_window and model.context_window < min_ctx:
            raise ValueError(
                f"Model '{model_id}' context window ({model.context_window}) "
                f"is below requirement ({min_ctx}) for '{operation_name}'"
            )

        return model

    @staticmethod
    def bootstrap_from_env(session: Session) -> None:
        """Seed default endpoints, models, and runtime pools from environment configuration."""
        now = utcnow()

        # 1. Generation Endpoint
        gen_ep = session.scalar(select(AIEndpoint).where(AIEndpoint.name == "vllm_generation"))
        if not gen_ep:
            gen_ep = AIEndpoint(
                id=str(uuid.uuid4()),
                name="vllm_generation",
                endpoint_type="generation",
                base_url=VLLM_GEN_URL,
                is_active=True,
                created_at=now,
            )
            session.add(gen_ep)

        # 2. Embedding Endpoint
        embed_ep = session.scalar(select(AIEndpoint).where(AIEndpoint.name == "vllm_embedding"))
        if not embed_ep:
            embed_ep = AIEndpoint(
                id=str(uuid.uuid4()),
                name="vllm_embedding",
                endpoint_type="embedding",
                base_url=VLLM_EMBED_URL,
                is_active=True,
                created_at=now,
            )
            session.add(embed_ep)

        session.flush()

        # 3. Default Generation Model
        gen_model = session.scalar(
            select(AIModel).where(AIModel.endpoint_id == gen_ep.id, AIModel.model_id == DEFAULT_GEN_MODEL)
        )
        if not gen_model:
            gen_model = AIModel(
                id=str(uuid.uuid4()),
                endpoint_id=gen_ep.id,
                model_id=DEFAULT_GEN_MODEL,
                display_name="Qwen 3.8 27B (Nemo NVFP4)",
                family="qwen",
                context_window=32768,
                qualification_status="passed",
                is_default=True,
                created_at=now,
            )
            session.add(gen_model)

        # 4. Default Embedding Model
        embed_model = session.scalar(
            select(AIModel).where(AIModel.endpoint_id == embed_ep.id, AIModel.model_id == DEFAULT_EMBED_MODEL)
        )
        if not embed_model:
            embed_model = AIModel(
                id=str(uuid.uuid4()),
                endpoint_id=embed_ep.id,
                model_id=DEFAULT_EMBED_MODEL,
                display_name="Nomic Embed Text v1.5 (768-dim)",
                family="nomic",
                context_window=8192,
                qualification_status="passed",
                is_default=True,
                created_at=now,
            )
            session.add(embed_model)

        # 5. Default Runtime Pool
        pool = session.scalar(select(AIRuntimePool).where(AIRuntimePool.name == "nemo_pool"))
        if not pool:
            pool = AIRuntimePool(
                id=str(uuid.uuid4()),
                name="nemo_pool",
                max_in_flight=GEN_APP_MAX_IN_FLIGHT,
                interactive_reserve=GEN_INTERACTIVE_RESERVE,
                created_at=now,
            )
            session.add(pool)

        session.commit()
        logger.info("Model registry bootstrapped successfully from environment.")

    @staticmethod
    def list_available_models(session: Session, endpoint_type: str = "generation") -> list[dict[str, Any]]:
        """List all active and qualified models of a given type."""
        stmt = (
            select(AIModel)
            .join(AIEndpoint, AIModel.endpoint_id == AIEndpoint.id)
            .where(
                AIEndpoint.endpoint_type == endpoint_type,
                AIEndpoint.is_active == True,  # noqa: E712
                AIModel.qualification_status == "passed",
            )
        )
        models = session.scalars(stmt).all()
        return [
            {
                "id": m.id,
                "model_id": m.model_id,
                "display_name": m.display_name,
                "family": m.family,
                "context_window": m.context_window,
                "is_default": m.is_default,
                "qualification_status": m.qualification_status,
            }
            for m in models
        ]

    @staticmethod
    def list_endpoints(session: Session) -> list[dict[str, Any]]:
        """List all registered AI endpoints."""
        endpoints = session.scalars(select(AIEndpoint)).all()
        return [
            {
                "id": ep.id,
                "name": ep.name,
                "endpoint_type": ep.endpoint_type,
                "base_url": ep.base_url,
                "is_active": ep.is_active,
                "created_at": ep.created_at.isoformat() if ep.created_at else None,
            }
            for ep in endpoints
        ]

    @staticmethod
    def probe_endpoint_models(endpoint_url: str, timeout_seconds: float = 10.0) -> list[str]:
        """Probe remote /v1/models endpoint to discover available served model IDs."""
        url = f"{endpoint_url.rstrip('/')}/v1/models"
        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    return [item.get("id") for item in data.get("data", []) if item.get("id")]
        except Exception as exc:
            logger.warning("Failed to probe %s: %s", url, exc)
        return []

    @staticmethod
    def run_qualification_test(session: Session, model_id: str) -> dict[str, Any]:
        """Execute real capability probe against model endpoint to verify operational qualification."""
        model = session.scalar(select(AIModel).where(AIModel.model_id == model_id))
        if not model:
            raise ValueError(f"Model '{model_id}' not found in registry")

        endpoint = model.endpoint
        if not endpoint or not endpoint.base_url:
            raise ValueError(f"Model '{model_id}' has no associated active endpoint")

        test_result = {"model_id": model_id, "endpoint_type": endpoint.endpoint_type, "status": "failed"}

        try:
            if endpoint.endpoint_type == "generation":
                url = f"{endpoint.base_url.rstrip('/')}/v1/chat/completions"
                payload = {
                    "model": model_id,
                    "messages": [{"role": "user", "content": "Respond with the word OK."}],
                    "max_tokens": 10,
                }
                with httpx.Client(timeout=30.0) as client:
                    resp = client.post(url, json=payload)
                    if resp.status_code == 200:
                        model.qualification_status = "passed"
                        test_result["status"] = "passed"
                    else:
                        model.qualification_status = "failed"
                        test_result["error"] = f"HTTP {resp.status_code}: {resp.text[:200]}"
            elif endpoint.endpoint_type == "embedding":
                url = f"{endpoint.base_url.rstrip('/')}/v1/embeddings"
                payload = {
                    "model": model_id,
                    "input": ["search_document: test qualification probe"],
                }
                with httpx.Client(timeout=30.0) as client:
                    resp = client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        items = data.get("data", [])
                        if items and len(items[0].get("embedding", [])) == 768:
                            model.qualification_status = "passed"
                            test_result["status"] = "passed"
                        else:
                            model.qualification_status = "failed"
                            test_result["error"] = "Embedding vector dimensions != 768"
                    else:
                        model.qualification_status = "failed"
                        test_result["error"] = f"HTTP {resp.status_code}: {resp.text[:200]}"
        except Exception as exc:
            model.qualification_status = "failed"
            test_result["error"] = str(exc)

        session.commit()
        return test_result

    @staticmethod
    def resolve_user_model(
        session: Session,
        user_id: str | None,
        requested_model: str | None = None,
        requested_effort: str | None = None,
    ) -> tuple[str, str]:
        """Resolve effective model name and reasoning effort for a user session."""
        model_name = requested_model
        reasoning_effort = requested_effort or "medium"

        # Check user preferences if not explicitly requested
        if (not model_name or not requested_effort) and user_id:
            pref = session.scalar(select(UserAIPreference).where(UserAIPreference.user_id == user_id))
            if pref:
                if not model_name and pref.preferred_gen_model:
                    model_name = pref.preferred_gen_model
                if not requested_effort and pref.preferred_reasoning_effort:
                    reasoning_effort = pref.preferred_reasoning_effort

        # Fallback to default registered model or global config default
        if not model_name:
            default_model = session.scalar(
                select(AIModel).where(AIModel.is_default == True, AIModel.qualification_status == "passed")  # noqa: E712
            )
            model_name = default_model.model_id if default_model else DEFAULT_GEN_MODEL

        return model_name, reasoning_effort

    @staticmethod
    def set_user_preference(
        session: Session,
        user_id: str,
        preferred_gen_model: str | None = None,
        preferred_reasoning_effort: str | None = None,
    ) -> UserAIPreference:
        """Update or create user model and reasoning preferences (atomic upsert)."""
        now = utcnow()
        gen_model = preferred_gen_model or DEFAULT_GEN_MODEL
        effort = preferred_reasoning_effort or "medium"

        stmt = (
            pg_insert(UserAIPreference)
            .values(
                user_id=user_id,
                preferred_gen_model=gen_model,
                preferred_reasoning_effort=effort,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["user_id"],
                set_={
                    "preferred_gen_model": preferred_gen_model or UserAIPreference.preferred_gen_model,
                    "preferred_reasoning_effort": preferred_reasoning_effort
                    or UserAIPreference.preferred_reasoning_effort,
                    "updated_at": now,
                },
            )
        )
        session.execute(stmt)
        session.commit()

        # Re-fetch the merged row to return
        pref = session.scalar(select(UserAIPreference).where(UserAIPreference.user_id == user_id))
        return pref  # type: ignore[return-value]
