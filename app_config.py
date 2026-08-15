"""Shared configuration for the application.

Imported by both app.py and blueprint modules to avoid circular imports.
"""

import logging
import os
from functools import wraps

import markdown
from dotenv import load_dotenv
from flask import abort
from markupsafe import escape as _html_escape
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError  # noqa: F401  # re-exported for blueprints
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import text

from auth_utils import get_current_user

# If you store your models and sync code in separate modules:
from db.models import SummariesV2, User, Video, VideoFolder  # noqa: F401  # re-exported for blueprints
from summarizer_v2 import (  # noqa: F401  # re-exported for blueprints
    build_prompts_for_chunk,
    chunk_transcript,
    ollama_embed_chunk,
    ollama_generate_chunk,
)
from youtube_utils import download_channel_transcripts  # noqa: F401  # re-exported for blueprints


def md_safe(s):
    """Render markdown to HTML, escaping raw HTML first to prevent XSS.

    markupsafe.escape converts <, >, &, ", ' to entities before markdown
    processes the string, so injected script/HTML tags are neutralised.
    Note: Markdown 3.x dropped safe_mode; pre-escaping the input is the
    correct replacement.
    """
    return markdown.markdown(str(_html_escape(s))) if s else ""


load_dotenv()

DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    raise RuntimeError("DATABASE_URL is not set. Create a .env file or export DATABASE_URL before starting the app.")
engine = create_engine(DB_URL, echo=False, pool_pre_ping=True, pool_recycle=1800)  # 30 minutes
SessionLocal = sessionmaker(bind=engine)


# Configure structured logging
_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
_handler = logging.StreamHandler()
_handler.setFormatter(_formatter)
_logger = logging.getLogger(__name__)
_logger.setLevel(logging.INFO)
if not _logger.handlers:
    _logger.addHandler(_handler)

# Read the env file
load_dotenv()

# vLLM instance for embeddings (nomic-embed-text)
_VLLM_EMBED_HOST = os.getenv("VLLM_EMBED_HOST", "localhost")
_VLLM_EMBED_PORT = os.getenv("VLLM_EMBED_PORT", "8001")
VLLM_EMBED_URL = f"http://{_VLLM_EMBED_HOST}:{_VLLM_EMBED_PORT}"

# vLLM instance for generation (Llama, etc.)
_VLLM_GEN_HOST = os.getenv("VLLM_GEN_HOST", "localhost")
_VLLM_GEN_PORT = os.getenv("VLLM_GEN_PORT", "8000")
VLLM_GEN_URL = f"http://{_VLLM_GEN_HOST}:{_VLLM_GEN_PORT}"

# Ollama fallback (legacy)
_REMOTE_OLLAMA_HOST = os.getenv("REMOTE_OLLAMA_HOST", "localhost")
OLLAMA_URL = f"http://{_REMOTE_OLLAMA_HOST}:11434"

# Use vLLM if configured, otherwise fall back to Ollama
if os.getenv("VLLM_GEN_HOST"):
    _LLM_GEN_URL = VLLM_GEN_URL
    _LLM_EMBED_URL = VLLM_EMBED_URL
    _logger.info("[Embed LLM] Using vLLM: %s", _LLM_EMBED_URL)
    _logger.info("[Gen LLM]   Using vLLM: %s", _LLM_GEN_URL)
else:
    _LLM_GEN_URL = OLLAMA_URL
    _LLM_EMBED_URL = OLLAMA_URL
    _logger.info("[Embed LLM] Using Ollama: %s", _LLM_EMBED_URL)
    _logger.info("[Gen LLM]   Using Ollama: %s", _LLM_GEN_URL)


# In-memory storage for statuses (for demo).
# For production, use a database or a caching layer (Redis).
download_statuses = {}
summarize_v2_statuses = {}


# Define a decorator to require a specific role
def require_role(allowed_roles):
    """
    Decorator that requires the current user to have one of allowed_roles.
    Example usage:
        @app.route("/admin")
        @require_role(["admin"])
        def admin_dashboard():
            ...
    """

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Lazy lookup to allow test patching of app.get_current_user
            import app as app_module

            get_current_user_func = getattr(app_module, "get_current_user", get_current_user)
            email, role = get_current_user_func()
            if not email:
                # not authenticated
                return abort(403, "Unauthorized")
            if role not in allowed_roles:
                return abort(403, f"User {email} (role={role}) not allowed.")
            return f(*args, **kwargs)

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Chat SQL templates (shared by chat blueprint)
# ---------------------------------------------------------------------------

CHAT_CHANNEL_SQL_TEMPLATES = {
    "public.summaries_v2_comprehensive_notes_embedding": """
        SELECT ev.content, s.video_id, v.title AS video_title,
               1 - (ev.embedding <=> :q_emb) AS similarity
        FROM %(view)s ev
        JOIN summaries_v2 s ON ev.source_id = s.id::VARCHAR
        JOIN video_folders vf ON s.video_id = vf.video_id
        JOIN videos v        ON s.video_id = v.video_id
        WHERE vf.folder_name = :chan
        ORDER BY similarity DESC LIMIT 5
    """,
    "public.summaries_v2_concise_summary_embedding": """
        SELECT ev.content, s.video_id, v.title AS video_title,
               1 - (ev.embedding <=> :q_emb) AS similarity
        FROM %(view)s ev
        JOIN summaries_v2 s ON ev.source_id = s.id::VARCHAR
        JOIN video_folders vf ON s.video_id = vf.video_id
        JOIN videos v        ON s.video_id = v.video_id
        WHERE vf.folder_name = :chan
        ORDER BY similarity DESC LIMIT 5
    """,
    "public.summaries_v2_key_topics_embedding": """
        SELECT ev.content, s.video_id, v.title AS video_title,
               1 - (ev.embedding <=> :q_emb) AS similarity
        FROM %(view)s ev
        JOIN summaries_v2 s ON ev.source_id = s.id::VARCHAR
        JOIN video_folders vf ON s.video_id = vf.video_id
        JOIN videos v        ON s.video_id = v.video_id
        WHERE vf.folder_name = :chan
        ORDER BY similarity DESC LIMIT 5
    """,
    "public.summaries_v2_important_takeaways_embedding": """
        SELECT ev.content, s.video_id, v.title AS video_title,
               1 - (ev.embedding <=> :q_emb) AS similarity
        FROM %(view)s ev
        JOIN summaries_v2 s ON ev.source_id = s.id::VARCHAR
        JOIN video_folders vf ON s.video_id = vf.video_id
        JOIN videos v        ON s.video_id = v.video_id
        WHERE vf.folder_name = :chan
        ORDER BY similarity DESC LIMIT 5
    """,
    "public.videos_transcript_no_ts_embedding": """
        SELECT ev.content, ev.source_id AS video_id, v.title AS video_title,
               1 - (ev.embedding <=> :q_emb) AS similarity
        FROM %(view)s ev
        JOIN video_folders vf ON ev.source_id = vf.video_id
        JOIN videos v        ON ev.source_id = v.video_id
        WHERE vf.folder_name = :chan
        ORDER BY similarity DESC LIMIT 5
    """,
}

CHAT_VIDEO_SQL_TEMPLATES = {
    "public.summaries_v2_comprehensive_notes_embedding": """
        SELECT chunk, 1 - (embedding <=> :q_emb) AS similarity
        FROM %(view)s WHERE video_id = :vid ORDER BY similarity DESC LIMIT 5
    """,
    "public.summaries_v2_concise_summary_embedding": """
        SELECT chunk, 1 - (embedding <=> :q_emb) AS similarity
        FROM %(view)s WHERE video_id = :vid ORDER BY similarity DESC LIMIT 5
    """,
    "public.summaries_v2_key_topics_embedding": """
        SELECT chunk, 1 - (embedding <=> :q_emb) AS similarity
        FROM %(view)s WHERE video_id = :vid ORDER BY similarity DESC LIMIT 5
    """,
    "public.summaries_v2_important_takeaways_embedding": """
        SELECT chunk, 1 - (embedding <=> :q_emb) AS similarity
        FROM %(view)s WHERE video_id = :vid ORDER BY similarity DESC LIMIT 5
    """,
    "public.videos_transcript_no_ts_embedding": """
        SELECT chunk, 1 - (embedding <=> :q_emb) AS similarity
        FROM %(view)s WHERE video_id = :vid ORDER BY similarity DESC LIMIT 5
    """,
}


# ---------------------------------------------------------------------------
# Aliases for blueprint imports (lowercase / expected names)
# ---------------------------------------------------------------------------
# These ensure blueprints can import from app_config with the names they expect.
logger = _logger  # blueprint alias
shared_logger = _logger  # blueprint alias (used by api.py)
chat_channel_sql_templates = CHAT_CHANNEL_SQL_TEMPLATES  # blueprint alias
chat_video_sql_templates = CHAT_VIDEO_SQL_TEMPLATES  # blueprint alias
text = text  # blueprint alias
