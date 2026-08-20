"""Unit tests for services/jwt_auth.py (JWTAuth token generation/validation)."""

import datetime

import pytest
from flask import Flask

from services.jwt_auth import JWTAuth, get_jwt_secret


class TestGetJwtSecret:
    def test_returns_env_secret(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET_KEY", "env-secret")
        assert get_jwt_secret() == "env-secret"

    def test_falls_back_to_flask_secret(self, monkeypatch):
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        monkeypatch.setenv("FLASK_SECRET_KEY", "flask-secret")
        assert get_jwt_secret() == "flask-secret"

    def test_dev_mode_without_secret(self, monkeypatch):
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)
        monkeypatch.setenv("FLASK_ENV", "development")
        assert get_jwt_secret() == "dev-jwt-secret-key-change-in-production"

    def test_production_without_secret_raises(self, monkeypatch):
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)
        monkeypatch.setenv("FLASK_ENV", "production")
        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY or FLASK_SECRET_KEY"):
            get_jwt_secret()


class TestGenerateAndValidate:
    def test_round_trip(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")
        token = JWTAuth.generate_token("user@example.com", role="admin")
        payload = JWTAuth.validate_token(token)
        assert payload is not None
        assert payload.sub == "user@example.com"
        assert payload.role == "admin"
        assert payload.jti
        # exp is ~24h in the future
        assert payload.exp > payload.iat + 23 * 3600

    def test_validate_rejects_garbage(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")
        assert JWTAuth.validate_token("not-a-jwt") is None

    def test_validate_rejects_wrong_secret(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET_KEY", "secret-a")
        token = JWTAuth.generate_token("user@example.com")
        monkeypatch.setenv("JWT_SECRET_KEY", "secret-b")
        assert JWTAuth.validate_token(token) is None

    def test_validate_rejects_expired_token(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")
        import jwt as pyjwt

        now = datetime.datetime.now(datetime.UTC)
        token = pyjwt.encode(
            {
                "sub": "user@example.com",
                "role": "reader",
                "iat": now - datetime.timedelta(hours=2),
                "exp": now - datetime.timedelta(hours=1),
                "jti": "abc123",
            },
            "test-secret",
            algorithm="HS256",
        )
        assert JWTAuth.validate_token(token) is None

    def test_validate_rejects_missing_required_claims(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")
        import jwt as pyjwt

        now = datetime.datetime.now(datetime.UTC)
        # No "role" claim -> must be rejected via options.require
        token = pyjwt.encode(
            {"sub": "user@example.com", "iat": now, "exp": now + datetime.timedelta(hours=1), "jti": "abc"},
            "test-secret",
            algorithm="HS256",
        )
        assert JWTAuth.validate_token(token) is None


class TestGetTokenFromRequest:
    @pytest.fixture
    def app(self):
        app = Flask(__name__)
        return app

    def test_bearer_header_wins(self, app):
        with app.test_request_context(
            headers={"Authorization": "Bearer header-token", "Cookie": "jwt_token=cookie-token"}
        ):
            assert JWTAuth.get_token_from_request() == "header-token"

    def test_cookie_fallback(self, app):
        with app.test_request_context(headers={"Cookie": "jwt_token=cookie-token"}):
            assert JWTAuth.get_token_from_request() == "cookie-token"

    def test_no_token(self, app):
        with app.test_request_context():
            assert JWTAuth.get_token_from_request() is None
