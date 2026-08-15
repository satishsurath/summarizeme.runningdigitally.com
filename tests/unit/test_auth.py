"""Tests for auth_utils.py — Cloudflare Access JWT authentication."""

import os
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import User


class TestGetUserEmailDevMode:
    """Tests for the dev-mode authentication bypass and production JWT flow."""

    def test_dev_mode_returns_dummy_user(self, client):
        """dev mode should return dev@localhost when DEV_AUTH_ENABLED=true."""
        from auth_utils import get_user_email_dev_mode

        os.environ["DEV_AUTH_ENABLED"] = "true"
        try:
            email = get_user_email_dev_mode()
            assert email == "dev@localhost"
        finally:
            os.environ.pop("DEV_AUTH_ENABLED", None)

    def test_dev_mode_returns_none_when_disabled(self, with_db):
        """When DEV_AUTH_ENABLED is not set, dev mode should not activate."""
        from app import app
        from auth_utils import get_user_email_dev_mode

        os.environ.pop("DEV_AUTH_ENABLED", None)
        os.environ.pop("FLASK_ENV", None)
        with app.test_request_context():
            result = get_user_email_dev_mode()
            assert result != "dev@localhost"

    def test_jwt_flow_fails_without_token(self, with_db):
        """Without a JWT token, should return None."""
        from app import app
        from auth_utils import get_user_email_dev_mode

        os.environ.pop("DEV_AUTH_ENABLED", None)
        os.environ.pop("CLOUDFLARE_JWKS_URL", None)
        with app.test_request_context():
            mock_headers_obj = MagicMock()
            mock_cookies_obj = MagicMock()
            mock_headers_obj.get.return_value = None
            mock_cookies_obj.get.return_value = None
            with patch("auth_utils.request") as mock_request:
                mock_request.headers = mock_headers_obj
                mock_request.cookies = mock_cookies_obj
                result = get_user_email_dev_mode()
                assert result is None


class TestGetCurrentUser:
    """Tests for the full auth flow including user lookup and auto-provisioning."""

    def test_unauthenticated_user_returns_none(self, with_db):
        """No auth header → None, None."""
        from app import app
        from auth_utils import get_current_user

        os.environ.pop("DEV_AUTH_ENABLED", None)
        os.environ.pop("CLOUDFLARE_JWKS_URL", None)
        with app.test_request_context():
            mock_headers_obj = MagicMock()
            mock_cookies_obj = MagicMock()
            mock_headers_obj.get.return_value = None
            mock_cookies_obj.get.return_value = None
            with patch("auth_utils.request") as mock_request:
                mock_request.headers = mock_headers_obj
                mock_request.cookies = mock_cookies_obj
                email, role = get_current_user()
                assert email is None
                assert role is None

    def test_authenticated_user_returns_role(self, with_db, admin_user):
        """Authenticated user with existing DB record returns correct role."""
        from app import app
        from auth_utils import get_current_user

        os.environ.pop("DEV_AUTH_ENABLED", None)
        mock_payload = {"email": "admin@test.com"}

        with (
            app.test_request_context(),
            patch("auth_utils.request") as mock_request,
            patch("auth_utils.jwt.decode", return_value=mock_payload),
            patch("auth_utils.PyJWKClient") as mock_jwks,
        ):
            mock_jwks.return_value.get_signing_key_from_jwt.return_value = MagicMock(key="fake_key")
            mock_headers = MagicMock()
            mock_headers.get.side_effect = lambda key, default=None: {
                "Cf-Access-Jwt-Assertion": "fake_token",
            }.get(key, default)
            mock_request.headers = mock_headers
            mock_request.cookies = MagicMock()
            mock_request.cookies.get.return_value = None

            email, role = get_current_user()
            assert email == "admin@test.com"
            assert role == "admin"

    def test_auto_provisions_new_user_as_reader(self, with_db):
        """New authenticated user should be auto-provisioned as 'reader'."""
        from app import app
        from auth_utils import get_current_user

        os.environ.pop("DEV_AUTH_ENABLED", None)
        mock_payload = {"email": "newuser2@test.com"}

        with (
            app.test_request_context(),
            patch("auth_utils.request") as mock_request,
            patch("auth_utils.jwt.decode", return_value=mock_payload),
            patch("auth_utils.PyJWKClient") as mock_jwks,
        ):
            mock_jwks.return_value.get_signing_key_from_jwt.return_value = MagicMock(key="fake_key")
            mock_headers = MagicMock()
            mock_headers.get.side_effect = lambda key, default=None: {
                "Cf-Access-Jwt-Assertion": "fake_token",
            }.get(key, default)
            mock_request.headers = mock_headers
            mock_request.cookies = MagicMock()
            mock_request.cookies.get.return_value = None

            email, role = get_current_user()
            assert email == "newuser2@test.com"
            assert role == "reader"

    def test_auto_provision_creates_user_in_db(self, with_db):
        """Auto-provisioned user should exist in the database."""
        from app import app
        from auth_utils import get_current_user

        os.environ.pop("DEV_AUTH_ENABLED", None)
        mock_payload = {"email": "freshuser2@test.com"}

        with (
            app.test_request_context(),
            patch("auth_utils.request") as mock_request,
            patch("auth_utils.jwt.decode", return_value=mock_payload),
            patch("auth_utils.PyJWKClient") as mock_jwks,
        ):
            mock_jwks.return_value.get_signing_key_from_jwt.return_value = MagicMock(key="fake_key")
            mock_headers = MagicMock()
            mock_headers.get.side_effect = lambda key, default=None: {
                "Cf-Access-Jwt-Assertion": "fake_token",
            }.get(key, default)
            mock_request.headers = mock_headers
            mock_request.cookies = MagicMock()
            mock_request.cookies.get.return_value = None

            get_current_user()

            engine = create_engine(os.environ["DATABASE_URL"])
            Session = sessionmaker(bind=engine)
            session = Session()
            user = session.query(User).filter_by(email="freshuser2@test.com").first()
            assert user is not None
            assert user.role == "reader"
            session.close()


class TestRoleDecorator:
    """Tests for the require_role decorator."""

    def test_admin_access_allowed(self, client, with_db, mock_vllm_response):
        """Admin user should access admin endpoints."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine(os.environ["DATABASE_URL"])
        Session = sessionmaker(bind=engine)
        session = Session()
        # Use unique email to avoid conflicts
        admin = User(email="admin_decorated@test.com", role="admin")
        session.add(admin)
        session.commit()
        session.close()

        with patch("app.get_current_user", return_value=("admin_decorated@test.com", "admin")):
            resp = client.get("/admin-settings")
            assert resp.status_code == 200

    def test_member_access_denied_to_admin_only(self, client, with_db, mock_vllm_response):
        """Member user should get 403 on admin-only endpoints."""
        with patch("app.get_current_user", return_value=("member@test.com", "member")):
            resp = client.get("/admin-settings")
            assert resp.status_code == 403

    def test_unauthenticated_gets_403(self, client, with_db, mock_vllm_response):
        """Unauthenticated requests should get 403."""
        with patch("app.get_current_user", return_value=(None, None)):
            resp = client.get("/admin-settings")
            assert resp.status_code == 403
