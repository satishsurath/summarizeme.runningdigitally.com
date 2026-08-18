"""CORS middleware for Flask backend.

Allows the Next.js frontend to make cross-origin requests.
"""

from __future__ import annotations

import os

from flask import Flask, Response, request

DEFAULT_ALLOWED = ["http://localhost:3000", "http://localhost:3001"]

raw_urls = [url.strip() for url in os.getenv("NEXT_API_URL", "").split(",") if url.strip()]
ALLOWED_ORIGINS = list(dict.fromkeys(raw_urls + DEFAULT_ALLOWED))  # dedupe, preserve order


def init_cors(app: Flask) -> None:
    """Initialize CORS on the Flask app."""

    @app.after_request
    def after_request(response: Response) -> Response:
        origin = request.headers.get("Origin")
        if origin and origin in ALLOWED_ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Max-Age"] = "86400"
        return response

    @app.route("/", methods=["OPTIONS"])
    @app.route("/<path:path>", methods=["OPTIONS"])
    def options_handler(path=None):
        return "", 204
