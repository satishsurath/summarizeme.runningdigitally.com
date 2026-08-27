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


class ModelRegistryService:
    """Service for managing model definitions, runtime pools, and endpoint qualifications."""

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
                "model_id": m.model_id,
                "display_name": m.display_name,
                "family": m.family,
                "context_window": m.context_window,
                "is_default": m.is_default,
            }
            for m in models
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
