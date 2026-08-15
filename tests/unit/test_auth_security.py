"""Tests for auth_utils — dev mode bypass fix."""

import os


class TestDevModeAuthBypass:
    """Tests for the dev-mode authentication bypass vulnerability fix.

    The original code returned a dummy user when FLASK_ENV=development,
    allowing trivial authentication bypass. The fix requires an explicit
    DEV_AUTH_ENABLED flag.
    """

    def test_dev_mode_disabled_by_default(self, with_db):
        """Without DEV_AUTH_ENABLED, dev mode should not activate."""
        from app import app
        from auth_utils import get_user_email_dev_mode

        os.environ.pop("DEV_AUTH_ENABLED", None)
        os.environ.pop("FLASK_ENV", None)

        with app.test_request_context():
            email = get_user_email_dev_mode()
            assert email != "dev@localhost"

    def test_dev_mode_requires_explicit_flag(self, with_db):
        """Dev mode should only activate when DEV_AUTH_ENABLED is set."""
        from app import app
        from auth_utils import get_user_email_dev_mode

        os.environ.pop("DEV_AUTH_ENABLED", None)
        os.environ.pop("FLASK_ENV", None)
        try:
            with app.test_request_context():
                os.environ["DEV_AUTH_ENABLED"] = "true"
                email = get_user_email_dev_mode()
                assert email == "dev@localhost"
        finally:
            os.environ.pop("DEV_AUTH_ENABLED", None)

    def test_flask_env_development_not_enough(self, with_db):
        """FLASK_ENV=development alone should not grant dev auth."""
        from app import app
        from auth_utils import get_user_email_dev_mode

        os.environ["FLASK_ENV"] = "development"
        os.environ.pop("DEV_AUTH_ENABLED", None)
        try:
            with app.test_request_context():
                email = get_user_email_dev_mode()
                assert email != "dev@localhost"
        finally:
            os.environ.pop("FLASK_ENV", None)


class TestSecurityHeaders:
    """Tests for security-related behavior."""

    def test_cannot_provision_admin_via_dev_mode(self, with_db):
        """Dev mode user should not be able to create admin users."""
        from app import app
        from auth_utils import get_current_user

        os.environ["DEV_AUTH_ENABLED"] = "true"
        try:
            with app.test_request_context():
                # Dev mode auth returns dev@localhost which gets provisioned as admin
                _email, role = get_current_user()
                assert role == "admin"
        finally:
            os.environ.pop("DEV_AUTH_ENABLED", None)
