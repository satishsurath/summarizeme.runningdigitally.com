"""Unit test verifying worker SIGTERM signal handling, graceful drain, and lease cleanup."""

from __future__ import annotations

import signal
from unittest.mock import MagicMock, patch

import workers.main as worker_module
from services.job_queue import JobQueue
from services.resource_admission import ResourceAdmission
from workers.main import _signal_handler, run_worker_loop


class TestWorkerDrain:
    """Test suite for worker graceful shutdown and active lease safety."""

    def test_handle_sigterm_sets_shutdown_flag(self):
        """SIGTERM handler must toggle shutdown event flag without sudden crash."""
        worker_module._SHUTDOWN_EVENT.clear()
        assert not worker_module._SHUTDOWN_EVENT.is_set()

        # Simulate SIGTERM signal dispatch
        _signal_handler(signal.SIGTERM, None)
        assert worker_module._SHUTDOWN_EVENT.is_set()

        # Reset for other tests
        worker_module._SHUTDOWN_EVENT.clear()

    @patch("workers.main.SessionLocal")
    def test_run_worker_loop_exits_cleanly_on_shutdown(self, mock_session_factory):
        """Worker loop must terminate cleanly when shutdown is requested."""
        mock_session = MagicMock()
        mock_session_factory.return_value.__enter__.return_value = mock_session

        worker_module._SHUTDOWN_EVENT.set()
        run_worker_loop(
            resource_classes=["control"],
            worker_id="test-worker",
            poll_interval_seconds=0.01,
            idle_exit_seconds=10,
        )
        # Exited without error

        # Reset for other tests
        worker_module._SHUTDOWN_EVENT.clear()

    def test_active_lease_cleanup_on_drain(self):
        """Verify expired or orphaned leases can be reaped after worker termination."""
        mock_session = MagicMock()
        mock_session.execute.return_value.rowcount = 1

        released = ResourceAdmission.release_lease(session=mock_session, lease_id="test-lease-id")
        assert released is True

    def test_abandoned_running_work_items_recovered(self):
        """Verify timed-out work items can be recovered by JobQueue."""
        mock_session = MagicMock()
        mock_session.execute.return_value.rowcount = 1

        recovered = JobQueue.recover_expired_leases(session=mock_session)
        assert isinstance(recovered, int)
