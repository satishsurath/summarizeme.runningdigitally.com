import os

# app.py
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_openapi3.models.info import Info
from flask_openapi3.models.tag import Tag

# ---------------------------------------------------------------------------
# OpenAPI / Swagger docs — OpenAPI extends Flask
# ---------------------------------------------------------------------------
from flask_openapi3.openapi import OpenAPI

from app_config import (  # noqa: F401  # test-patched names
    VLLM_EMBED_URL,
    VLLM_GEN_URL,
    SessionLocal,
    build_prompts_for_chunk,
    chunk_transcript,
    download_channel_transcripts,
    get_current_user,
    logger,
    md_safe,
    task_store,
    vllm_embed_chunk,
    vllm_generate_chunk,
)

info = Info(title="SummarizeMe API", version="2.0.0", description="YouTube channel summarization API")
app = OpenAPI(__name__, info=info)
app.config["SECRET_KEY"] = os.getenv(
    "FLASK_SECRET_KEY",
    os.urandom(32).hex(),
)
app.jinja_env.globals["ICON_DATA"] = __import__("icon_data").ICON_DATA
app.jinja_env.globals["SIZE_MAP"] = __import__("icon_data").SIZE_MAP

api_tag = Tag(name="api", description="Channel, video, and summarization operations")
task_tag = Tag(name="tasks", description="Background task management")
admin_tag = Tag(name="admin", description="Admin operations")
chat_tag = Tag(name="chat", description="Chat with channel or video content")
health_tag = Tag(name="health", description="Health check endpoints")

# ---------------------------------------------------------------------------
# Rate limiting — in-memory by default (Redis optional via REDIS_URL)
# ---------------------------------------------------------------------------
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["100000 per day", "10000 per hour"] if os.getenv("FLASK_ENV") != "development" else [],
    storage_uri=os.getenv("REDIS_URL", "memory://"),
)
# CORS
# ---------------------------------------------------------------------------
from services.cors_middleware import init_cors  # noqa: E402

init_cors(app)


# ---------------------------------------------------------------------------
# Register blueprints
# ---------------------------------------------------------------------------
from blueprints.admin import admin_bp  # noqa: E402
from blueprints.api import api_bp  # noqa: E402
from blueprints.chat import chat_bp  # noqa: E402
from blueprints.main import main_bp  # noqa: E402

app.register_blueprint(main_bp)
app.register_blueprint(api_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(admin_bp)


if __name__ == "__main__":
    # For local dev
    app.run(debug=True, host="0.0.0.0", port=5000)
