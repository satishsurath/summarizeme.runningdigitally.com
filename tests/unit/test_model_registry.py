"""Unit tests for services/model_registry.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import AIEndpoint, AIModel, AIRuntimePool, Base
from services.model_registry import ModelRegistryService


def create_in_memory_session():
    """Helper to create a fresh in-memory SQLite session with all models."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


class TestModelRegistryService:
    """Test suite for ModelRegistryService."""

    def test_bootstrap_from_env(self):
        session = create_in_memory_session()
        ModelRegistryService.bootstrap_from_env(session)

        # Verify endpoints created
        endpoints = session.query(AIEndpoint).all()
        assert len(endpoints) == 2
        names = [ep.name for ep in endpoints]
        assert "vllm_generation" in names
        assert "vllm_embedding" in names

        # Verify default models
        models = session.query(AIModel).all()
        assert len(models) == 2

        # Verify runtime pool
        pool = session.query(AIRuntimePool).first()
        assert pool is not None
        assert pool.name == "nemo_pool"
        assert pool.max_in_flight == 3
        assert pool.interactive_reserve == 1

    def test_list_available_models(self):
        session = create_in_memory_session()
        ModelRegistryService.bootstrap_from_env(session)

        gen_models = ModelRegistryService.list_available_models(session, endpoint_type="generation")
        assert len(gen_models) >= 1
        assert gen_models[0]["family"] == "qwen"

    def test_resolve_and_set_user_preferences(self):
        session = create_in_memory_session()
        ModelRegistryService.bootstrap_from_env(session)

        # Default resolution
        model, effort = ModelRegistryService.resolve_user_model(session, user_id="alice@example.com")
        assert "qwen" in model.lower()
        assert effort == "medium"

        # Explicit preference
        ModelRegistryService.set_user_preference(
            session=session,
            user_id="alice@example.com",
            preferred_gen_model="custom-qwen-model",
            preferred_reasoning_effort="xhigh",
        )

        model, effort = ModelRegistryService.resolve_user_model(session, user_id="alice@example.com")
        assert model == "custom-qwen-model"
        assert effort == "xhigh"

    @patch("httpx.Client.get")
    def test_probe_endpoint_models(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {"id": "nemo-qwen3.8-27b-nvfp4"},
                {"id": "nemo-qwen3.6-35b"},
            ]
        }
        mock_get.return_value = mock_resp

        models = ModelRegistryService.probe_endpoint_models("http://localhost:8000")
        assert len(models) == 2
        assert "nemo-qwen3.8-27b-nvfp4" in models

    def test_validate_model_for_operation(self):
        session = create_in_memory_session()
        ModelRegistryService.bootstrap_from_env(session)

        # Valid model for summarize_v3
        model = ModelRegistryService.validate_model_for_operation(
            session=session,
            model_id="nemo-qwen3.8-27b-nvfp4",
            operation_name="summarize_v3",
        )
        assert model.model_id == "nemo-qwen3.8-27b-nvfp4"

        # Invalid operation
        import pytest

        with pytest.raises(ValueError, match="Unknown AI operation"):
            ModelRegistryService.validate_model_for_operation(
                session=session,
                model_id="nemo-qwen3.8-27b-nvfp4",
                operation_name="unknown_op",
            )
