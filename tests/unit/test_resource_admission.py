"""Unit tests for services/resource_admission.py."""

from __future__ import annotations

import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Base, ExternalRateLimit, ResourceLease, ResourceLimit, ensure_utc, utcnow
from services.resource_admission import ResourceAdmission


def create_in_memory_session():
    """Helper to create a fresh in-memory SQLite session with all models."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


class TestResourceAdmission:
    """Test suite for ResourceAdmission lease control and external pacing."""

    def test_ensure_default_limits_seeds_table(self):
        session = create_in_memory_session()
        ResourceAdmission.ensure_default_limits(session)

        gen_limit = session.get(ResourceLimit, "generation")
        assert gen_limit is not None
        assert gen_limit.max_in_flight >= 2

        yt_limit = session.get(ResourceLimit, "youtube")
        assert yt_limit is not None
        assert yt_limit.max_in_flight == 2

    def test_acquire_lease_within_limit(self):
        session = create_in_memory_session()
        # Seed limits
        session.add(
            ResourceLimit(
                resource_class="generation_batch",
                max_in_flight=2,
                created_at=utcnow(),
                updated_at=utcnow(),
            )
        )
        session.commit()

        # Acquire lease 1
        lease1 = ResourceAdmission.acquire_lease(
            session, resource_class="generation_batch", owner="worker-1", lease_seconds=300
        )
        assert lease1 is not None

        # Acquire lease 2
        lease2 = ResourceAdmission.acquire_lease(
            session, resource_class="generation_batch", owner="worker-2", lease_seconds=300
        )
        assert lease2 is not None

        # Acquire lease 3 -> denied (limit is 2)
        lease3 = ResourceAdmission.acquire_lease(
            session, resource_class="generation_batch", owner="worker-3", lease_seconds=300
        )
        assert lease3 is None

    def test_acquire_lease_cleans_up_expired_leases(self):
        session = create_in_memory_session()
        session.add(
            ResourceLimit(
                resource_class="embedding",
                max_in_flight=1,
                created_at=utcnow(),
                updated_at=utcnow(),
            )
        )
        session.commit()

        # Add expired lease
        session.add(
            ResourceLease(
                id="old-lease",
                resource_class="embedding",
                owner="dead-worker",
                expires_at=utcnow() - datetime.timedelta(seconds=10),
                created_at=utcnow(),
            )
        )
        session.commit()

        # New acquire should clean up old lease and succeed
        lease = ResourceAdmission.acquire_lease(session, resource_class="embedding", owner="live-worker")
        assert lease is not None
        assert session.get(ResourceLease, "old-lease") is None

    def test_release_lease(self):
        session = create_in_memory_session()
        session.add(
            ResourceLimit(
                resource_class="youtube",
                max_in_flight=1,
                created_at=utcnow(),
                updated_at=utcnow(),
            )
        )
        session.commit()

        lease_id = ResourceAdmission.acquire_lease(session, resource_class="youtube", owner="yt-worker")
        assert lease_id is not None

        # Capacity full
        assert ResourceAdmission.acquire_lease(session, resource_class="youtube", owner="yt-worker-2") is None

        # Release lease
        released = ResourceAdmission.release_lease(session, lease_id=lease_id, owner="yt-worker")
        assert released is True

        # Capacity available again
        lease_id_new = ResourceAdmission.acquire_lease(session, resource_class="youtube", owner="yt-worker-2")
        assert lease_id_new is not None

    def test_reserve_external_start_pacing_and_jitter(self):
        session = create_in_memory_session()
        # Reserve first slot
        start1 = ResourceAdmission.reserve_external_start(
            session, provider_key="youtube", min_interval_seconds=12, jitter_seconds=0
        )
        # Next allowed is start1 + 12s
        rate_limit = session.get(ExternalRateLimit, "youtube")
        assert rate_limit is not None
        next_allowed = ensure_utc(rate_limit.next_allowed_at)
        assert next_allowed is not None
        assert next_allowed >= start1 + datetime.timedelta(seconds=12)

        # Reserve second slot immediately -> scheduled at or after next_allowed_at
        start2 = ResourceAdmission.reserve_external_start(
            session, provider_key="youtube", min_interval_seconds=12, jitter_seconds=0
        )
        assert start2 >= start1 + datetime.timedelta(seconds=12)

    def test_open_circuit_exponential_backoff_and_recovery(self):
        session = create_in_memory_session()

        # Trip circuit 1
        ResourceAdmission.open_circuit(session, provider_key="youtube", backoff_seconds=60, error_code="HTTP_429")
        rl1 = session.get(ExternalRateLimit, "youtube")
        assert rl1 is not None
        assert rl1.failure_count == 1
        assert rl1.last_error_code == "HTTP_429"
        assert rl1.backoff_until is not None

        # Trip circuit 2 -> exponential backoff (2x)
        ResourceAdmission.open_circuit(session, provider_key="youtube", backoff_seconds=60, error_code="HTTP_429")
        rl2 = session.get(ExternalRateLimit, "youtube")
        assert rl2 is not None
        assert rl2.failure_count == 2

        # Record success -> closes circuit
        ResourceAdmission.record_external_success(session, provider_key="youtube")
        rl_success = session.get(ExternalRateLimit, "youtube")
        assert rl_success is not None
        assert rl_success.failure_count == 0
        assert rl_success.backoff_until is None
