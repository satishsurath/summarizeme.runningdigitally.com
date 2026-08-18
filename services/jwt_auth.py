"""JWT token authentication support.

Provides JWT token generation and validation alongside Cloudflare Access JWT.
Supports both dev mode and production mode.
"""

from __future__ import annotations

import datetime
import os
from dataclasses import dataclass

import jwt
from flask import request


# JWT configuration
def get_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET_KEY") or os.getenv("FLASK_SECRET_KEY")
    if not secret:
        if os.getenv("FLASK_ENV") != "development":
            raise RuntimeError("JWT_SECRET_KEY or FLASK_SECRET_KEY must be set in production.")
        return "dev-jwt-secret-key-change-in-production"
    return secret


JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24


@dataclass
class TokenPayload:
    """Decoded JWT payload."""

    sub: str  # user identifier (email)
    role: str  # user role
    exp: float  # expiration timestamp
    iat: float  # issued at timestamp
    jti: str  # unique token ID


class JWTAuth:
    """JWT token generation and validation."""

    @staticmethod
    def generate_token(email: str, role: str = "reader") -> str:
        """Generate a JWT token for the given user."""
        now = datetime.datetime.now(datetime.UTC)
        payload = {
            "sub": email,
            "role": role,
            "iat": now,
            "exp": now + datetime.timedelta(hours=JWT_EXPIRATION_HOURS),
            "jti": os.urandom(16).hex(),
        }
        return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)

    @staticmethod
    def validate_token(token: str) -> TokenPayload | None:
        """Validate a JWT token and return the payload, or None if invalid."""
        try:
            payload = jwt.decode(
                token,
                get_jwt_secret(),
                algorithms=[JWT_ALGORITHM],
                options={"require": ["sub", "role", "exp", "iat", "jti"]},
            )
            return TokenPayload(
                sub=payload["sub"],
                role=payload["role"],
                exp=payload["exp"],
                iat=payload["iat"],
                jti=payload["jti"],
            )
        except (jwt.PyJWTError, KeyError, TypeError):
            return None

    @staticmethod
    def get_token_from_request() -> str | None:
        """Extract JWT token from request headers or cookies."""
        # Check Authorization header first (Bearer token)
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]

        # Check for a JWT cookie
        return request.cookies.get("jwt_token")
