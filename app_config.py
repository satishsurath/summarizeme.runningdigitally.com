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
from sqlalchemy.sql import text  # noqa: F401  # re-exported for blueprints

from auth_utils import get_current_user

# If you store your models and sync code in separate modules:
from db.models import SummariesV2, User, Video, VideoFolder  # noqa: F401  # re-exported for blueprints

# Task store — Redis-backed, shared across all blueprints
from services.task_store import TaskStore
from summarizer_v2 import (  # noqa: F401  # re-exported for blueprints
    build_prompts_for_chunk,
    chunk_transcript,
    vllm_embed_chunk,
    vllm_generate_chunk,
)
from youtube_utils import download_channel_transcripts  # noqa: F401  # re-exported for blueprints

DEFAULT_GEN_MODEL = os.getenv("VLLM_GEN_MODEL", "nemo-qwen3.6-35b-a3b-nvfp4")


def md_safe(s):
    """Render markdown to HTML, escaping raw HTML first to prevent XSS.

    markupsafe.escape converts <, >, &, ", ' to entities before markdown
    processes the string, so injected script/HTML tags are neutralised.
    """
    if not s:
        return ""
    return markdown.markdown(str(_html_escape(s)))


load_dotenv()

DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    raise RuntimeError("DATABASE_URL is not set. Create a .env file or export DATABASE_URL before starting the app.")
if not (
    DB_URL.startswith("postgresql://") or DB_URL.startswith("postgresql+psycopg2://") or DB_URL.startswith("sqlite://")
):
    raise RuntimeError(
        f"DATABASE_URL must start with 'postgresql://' or 'postgresql+psycopg2://', got: {DB_URL[:50]}..."
    )
engine = create_engine(DB_URL, echo=False, pool_pre_ping=True, pool_recycle=1800)  # 30 minutes
SessionLocal = sessionmaker(bind=engine)
VLLM_EMBED_MODEL = os.getenv("VLLM_EMBED_MODEL", "nemo-nomic-embed-text-v1.5")

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


# vLLM instance for embeddings (nomic-embed-text)
_VLLM_EMBED_HOST = os.getenv("VLLM_EMBED_HOST", "localhost")
_VLLM_EMBED_PORT = os.getenv("VLLM_EMBED_PORT", "8001")
VLLM_EMBED_URL = f"http://{_VLLM_EMBED_HOST}:{_VLLM_EMBED_PORT}"

# vLLM instance for generation (Llama, etc.)
_VLLM_GEN_HOST = os.getenv("VLLM_GEN_HOST", "localhost")
_VLLM_GEN_PORT = os.getenv("VLLM_GEN_PORT", "8000")
VLLM_GEN_URL = f"http://{_VLLM_GEN_HOST}:{_VLLM_GEN_PORT}"

_logger.info("[Embed LLM] Using vLLM: %s", VLLM_EMBED_URL)
_logger.info("[Gen LLM]   Using vLLM: %s", VLLM_GEN_URL)


task_store = TaskStore()

# Legacy-compatible aliases (backed by task_store)
# download_statuses / summarize_v2_statuses are replaced by task_store methods.
# Old code used: download_statuses[task_id] = {...}
# New code uses: task_store.create_task("download"), task_store.update_task(...)
download_statuses = task_store
summarize_v2_statuses = task_store


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
            import app as app_module

            get_current_user_func = getattr(app_module, "get_current_user", get_current_user)
            email, role = get_current_user_func()
            if not bool(email):
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

# Single base template for channel queries (all keys share identical SQL)
_CHAT_CHANNEL_SQL_TEMPLATE = """
    SELECT ev.content, s.video_id, v.title AS video_title,
           1 - (ev.embedding <=> :q_emb) AS similarity
    FROM %(view)s ev
    JOIN summaries_v2 s ON ev.source_id = CAST(s.id AS VARCHAR)
    JOIN video_folders vf ON s.video_id = vf.video_id
    JOIN videos v        ON s.video_id = v.video_id
    WHERE vf.folder_name = :chan
    ORDER BY similarity DESC LIMIT 15
"""

CHAT_CHANNEL_SQL_TEMPLATES = {
    "public.summaries_v2_comprehensive_notes_embedding": _CHAT_CHANNEL_SQL_TEMPLATE,
    "public.summaries_v2_concise_summary_embedding": _CHAT_CHANNEL_SQL_TEMPLATE,
    "public.summaries_v2_key_topics_embedding": _CHAT_CHANNEL_SQL_TEMPLATE,
    "public.summaries_v2_important_takeaways_embedding": _CHAT_CHANNEL_SQL_TEMPLATE,
    "public.videos_transcript_no_ts_embedding": """
    SELECT ev.content, ev.source_id AS video_id, v.title AS video_title,
           1 - (ev.embedding <=> :q_emb) AS similarity
    FROM %(view)s ev
    JOIN video_folders vf ON ev.source_id = vf.video_id
    JOIN videos v        ON ev.source_id = v.video_id
    WHERE vf.folder_name = :chan
    ORDER BY similarity DESC LIMIT 15
""",
}


# Video query template for summary embeddings (joins summaries_v2 to resolve video_id)
_CHAT_VIDEO_SUMMARY_SQL_TEMPLATE = """
    SELECT ev.content, 1 - (ev.embedding <=> :q_emb) AS similarity
    FROM %(view)s ev
    JOIN summaries_v2 s ON ev.source_id = CAST(s.id AS VARCHAR)
    WHERE s.video_id = :vid
    ORDER BY similarity DESC LIMIT 15
"""

# Video query template for transcript embeddings (source_id is video_id directly)
_CHAT_VIDEO_TRANSCRIPT_SQL_TEMPLATE = """
    SELECT content, 1 - (embedding <=> :q_emb) AS similarity
    FROM %(view)s WHERE source_id = :vid ORDER BY similarity DESC LIMIT 15
"""

CHAT_VIDEO_SQL_TEMPLATES = {
    "public.summaries_v2_comprehensive_notes_embedding": _CHAT_VIDEO_SUMMARY_SQL_TEMPLATE,
    "public.summaries_v2_concise_summary_embedding": _CHAT_VIDEO_SUMMARY_SQL_TEMPLATE,
    "public.summaries_v2_key_topics_embedding": _CHAT_VIDEO_SUMMARY_SQL_TEMPLATE,
    "public.summaries_v2_important_takeaways_embedding": _CHAT_VIDEO_SUMMARY_SQL_TEMPLATE,
    "public.videos_transcript_no_ts_embedding": _CHAT_VIDEO_TRANSCRIPT_SQL_TEMPLATE,
}


# ---------------------------------------------------------------------------
# Aliases for blueprint imports (lowercase / expected names)
# ---------------------------------------------------------------------------
# These ensure blueprints can import from app_config with the names they expect.
shared_logger = _logger  # alias for api.py import
logger = _logger
chat_channel_sql_templates = CHAT_CHANNEL_SQL_TEMPLATES
chat_video_sql_templates = CHAT_VIDEO_SQL_TEMPLATES
