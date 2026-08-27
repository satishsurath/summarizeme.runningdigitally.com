"""Cross-process resource admission, concurrency lease management, and rate pacing.

Authoritative for Nemo generation leases (batch vs interactive reserve),
Nomic embedding batch limits, and YouTube start pacing / circuit breaking.
"""

from __future__ import annotations

import datetime
import logging
import random
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app_config import (
    EMBED_IN_FLIGHT_BATCHES,
    GEN_APP_MAX_IN_FLIGHT,
    GEN_BATCH_CONCURRENCY,
    YT_MAX_IN_FLIGHT,
)
from db.models import ExternalRateLimit, ResourceLease, ResourceLimit, ensure_utc, utcnow

logger = logging.getLogger(__name__)

# Default hardcoded fallback limits if not yet seeded in database
DEFAULT_LIMITS: dict[str, int] = {
    "generation": GEN_APP_MAX_IN_FLIGHT,  # 3 total (2 batch + 1 interactive)
    "generation_batch": GEN_BATCH_CONCURRENCY,  # 2 batch max
    "embedding": EMBED_IN_FLIGHT_BATCHES,  # 1 in-flight batch
    "youtube": YT_MAX_IN_FLIGHT,  # 2 in-flight subprocesses
    "control": 1,
}


class ResourceAdmission:
    """Manages cross-process resource capacity and rate limits in PostgreSQL."""

    @staticmethod
    def ensure_default_limits(session: Session) -> None:
        """Seed default resource limits into database if not present."""
        now = utcnow()
        for r_class, max_in_flight in DEFAULT_LIMITS.items():
            existing = session.get(ResourceLimit, r_class)
            if not existing:
                session.add(
                    ResourceLimit(
                        resource_class=r_class,
                        max_in_flight=max_in_flight,
                        created_at=now,
                        updated_at=now,
                    )
                )
        session.commit()

    @staticmethod
    def acquire_lease(
        session: Session,
        resource_class: str,
        owner: str,
        lease_seconds: int = 300,
    ) -> str | None:
        """Attempt to acquire a concurrency lease for a resource class.

        Returns lease_id if acquired, or None if the resource is at capacity.
        """
        now = utcnow()

        # 1. Clean up expired leases first
        session.execute(
            delete(ResourceLease).where(
                ResourceLease.resource_class == resource_class,
                ResourceLease.expires_at <= now,
            )
        )

        # 2. Check configured max_in_flight limit (lock row to serialize concurrent checks)
        limit_row = session.scalar(
            select(ResourceLimit).where(ResourceLimit.resource_class == resource_class).with_for_update()
        )
        if limit_row and hasattr(limit_row, "max_in_flight") and isinstance(limit_row.max_in_flight, int):
            max_in_flight = limit_row.max_in_flight
        else:
            max_in_flight = DEFAULT_LIMITS.get(resource_class, 1)

        # 3. Count active leases
        raw_count = (
            session.scalar(
                select(func.count(ResourceLease.id)).where(
                    ResourceLease.resource_class == resource_class,
                    ResourceLease.expires_at > now,
                )
            )
            or 0
        )
        try:
            active_count = int(raw_count)
        except (TypeError, ValueError):
            active_count = 0

        try:
            max_limit = int(max_in_flight)
        except (TypeError, ValueError):
            max_limit = 1

        if active_count >= max_limit:
            logger.debug(
                "Capacity reached for %s (active=%d, limit=%d). Lease denied for %s",
                resource_class,
                active_count,
                max_limit,
                owner,
            )
            session.commit()
            return None

        # 4. Insert new lease
        lease_id = str(uuid.uuid4())
        lease = ResourceLease(
            id=lease_id,
            resource_class=resource_class,
            owner=owner,
            expires_at=now + datetime.timedelta(seconds=lease_seconds),
            created_at=now,
        )
        session.add(lease)
        session.commit()

        logger.info(
            "Acquired lease %s on %s for %s (active now=%d/%d)",
            lease_id,
            resource_class,
            owner,
            active_count + 1,
            max_in_flight,
        )
        return lease_id

    @staticmethod
    def release_lease(
        session: Session,
        lease_id: str,
        owner: str | None = None,
    ) -> bool:
        """Release an active resource lease."""
        stmt = delete(ResourceLease).where(ResourceLease.id == lease_id)
        if owner:
            stmt = stmt.where(ResourceLease.owner == owner)

        result = session.execute(stmt)
        session.commit()
        released = (result.rowcount or 0) > 0
        if released:
            logger.debug("Released lease %s (owner=%s)", lease_id, owner)
        return released

    @staticmethod
    def reserve_external_start(
        session: Session,
        provider_key: str = "youtube",
        min_interval_seconds: int = 12,
        jitter_seconds: int = 3,
    ) -> datetime.datetime:
        """Reserve a future start time slot for an external provider adhering to global pacing.

        Returns the scheduled datetime when the caller is permitted to start.
        """
        now = utcnow()
        rate_limit = session.get(ExternalRateLimit, provider_key)
        if not rate_limit:
            rate_limit = ExternalRateLimit(
                provider_key=provider_key,
                next_allowed_at=now,
                failure_count=0,
                updated_at=now,
            )
            session.add(rate_limit)

        # Check circuit breaker backoff
        base_time = now
        backoff_until = ensure_utc(rate_limit.backoff_until)
        if backoff_until and backoff_until > now:
            base_time = backoff_until

        next_allowed = ensure_utc(rate_limit.next_allowed_at)
        if next_allowed and next_allowed > base_time:
            base_time = next_allowed

        # Add jitter
        jitter = random.uniform(0, jitter_seconds) if jitter_seconds > 0 else 0
        scheduled_start = base_time + datetime.timedelta(seconds=jitter)

        # Update next allowed time in database
        rate_limit.next_allowed_at = scheduled_start + datetime.timedelta(seconds=min_interval_seconds)
        rate_limit.updated_at = now
        session.commit()

        logger.debug(
            "Reserved start slot for %s at %s (next_allowed=%s)",
            provider_key,
            scheduled_start.isoformat(),
            rate_limit.next_allowed_at.isoformat(),
        )
        return scheduled_start

    @staticmethod
    def open_circuit(
        session: Session,
        provider_key: str,
        backoff_seconds: int = 60,
        error_code: str | None = None,
    ) -> None:
        """Trip circuit breaker on 429/throttling error and apply exponential backoff."""
        now = utcnow()
        rate_limit = session.get(ExternalRateLimit, provider_key)
        if not rate_limit:
            rate_limit = ExternalRateLimit(
                provider_key=provider_key,
                next_allowed_at=now,
                failure_count=0,
                updated_at=now,
            )
            session.add(rate_limit)

        rate_limit.failure_count += 1
        # Exponential backoff multiplier: backoff_seconds * (2 ** (failure_count - 1))
        multiplier = 2 ** min(rate_limit.failure_count - 1, 4)  # cap multiplier at 16x
        effective_backoff = backoff_seconds * multiplier

        backoff_dt = now + datetime.timedelta(seconds=effective_backoff)
        rate_limit.backoff_until = backoff_dt
        rate_limit.next_allowed_at = backoff_dt
        rate_limit.last_error_code = error_code
        rate_limit.updated_at = now
        session.commit()

        logger.warning(
            "Circuit opened for %s (failure #%d): backing off for %ds until %s [code=%s]",
            provider_key,
            rate_limit.failure_count,
            effective_backoff,
            backoff_dt.isoformat(),
            error_code,
        )

    @staticmethod
    def record_external_success(
        session: Session,
        provider_key: str,
    ) -> None:
        """Reset failure count on successful external call."""
        rate_limit = session.get(ExternalRateLimit, provider_key)
        if rate_limit and (rate_limit.failure_count > 0 or rate_limit.backoff_until is not None):
            rate_limit.failure_count = 0
            rate_limit.backoff_until = None
            rate_limit.last_error_code = None
            rate_limit.updated_at = utcnow()
            session.commit()
            logger.info("Circuit closed/reset for %s following successful request", provider_key)
