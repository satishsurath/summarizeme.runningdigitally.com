# app.py

from flask import Flask

from app_config import (  # noqa: F401  # test-patched names
    _LLM_EMBED_URL,
    _LLM_GEN_URL,
    OLLAMA_URL,
    VLLM_EMBED_URL,
    VLLM_GEN_URL,
    SessionLocal,
    build_prompts_for_chunk,
    chunk_transcript,
    download_channel_transcripts,
    get_current_user,
    logger,
    md_safe,
    ollama_embed_chunk,
    ollama_generate_chunk,
)

app = Flask(__name__)

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
