# auth_utils.py
import logging
import os

import jwt
from dotenv import load_dotenv
from flask import request
from jwt import PyJWKClient

from db.models import User
from services.jwt_auth import JWTAuth

logger = logging.getLogger(__name__)

# Load these from your .env file or other secure location
load_dotenv()
CLOUDFLARE_JWKS_URL = os.getenv("CLOUDFLARE_JWKS_URL")
CLOUDFLARE_ISSUER = os.getenv("CLOUDFLARE_ISSUER")
CLOUDFLARE_AUD_TAG = os.getenv("CLOUDFLARE_AUD_TAG")

_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient | None:
    global _jwks_client
    if not CLOUDFLARE_JWKS_URL:
        return None
    if _jwks_client is None:
        _jwks_client = PyJWKClient(CLOUDFLARE_JWKS_URL, cache_keys=True)
    return _jwks_client


def _get_user_email_from_cf_jwt() -> str | None:
    """Validate a Cloudflare Access JWT and return the email."""
    token = request.headers.get("Cf-Access-Jwt-Assertion") or request.cookies.get("CF_Authorization")
    if not token:
        return None

    try:
        jwks_url = os.getenv("CLOUDFLARE_JWKS_URL", CLOUDFLARE_JWKS_URL)
        jwks_client = PyJWKClient(jwks_url)
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=os.getenv("CLOUDFLARE_AUD_TAG", CLOUDFLARE_AUD_TAG),
            issuer=os.getenv("CLOUDFLARE_ISSUER", CLOUDFLARE_ISSUER),
        )
        return payload.get("email")
    except (jwt.PyJWTError, Exception) as e:
        logger.warning("Invalid CF Access token: %s", e)
        return None


def _get_user_email_from_jwt_token() -> str | None:
    """Validate a regular JWT token and return the email."""
    token = JWTAuth.get_token_from_request()
    if not token:
        return None

    payload = JWTAuth.validate_token(token)
    if payload is None:
        return None

    return payload.sub


def get_user_email_dev_mode():
    """
    Returns a dev-mode email only when DEV_AUTH_ENABLED=true is set.
    Otherwise attempts Cloudflare Access JWT validation, then falls back to
    regular JWT token auth.
    """
    # Dev mode requires explicit opt-in, NOT just FLASK_ENV
    if os.getenv("DEV_AUTH_ENABLED") == "true":
        return "dev@localhost"

    # Production: Try Cloudflare Access JWT first, then regular JWT
    email = _get_user_email_from_cf_jwt()
    if email:
        return email

    # Fallback to regular JWT token auth
    return _get_user_email_from_jwt_token()


def get_current_user():
    """
    Returns a tuple: (email, role) or (None, None) if unauthenticated.
    """
    from app_config import SessionLocal

    email = get_user_email_dev_mode()
    if not email:
        return None, None

    session = SessionLocal()
    try:
        user_obj = session.query(User).filter_by(email=email).first()
        if user_obj:
            return (user_obj.email, user_obj.role)

        role = "admin" if os.getenv("DEV_AUTH_ENABLED") == "true" else "reader"
        new_user = User(email=email, role=role)
        session.add(new_user)
        try:
            session.commit()
            return (new_user.email, new_user.role)
        except Exception:
            session.rollback()
            existing = session.query(User).filter_by(email=email).first()
            if existing:
                return (existing.email, existing.role)
            raise
    finally:
        session.close()
