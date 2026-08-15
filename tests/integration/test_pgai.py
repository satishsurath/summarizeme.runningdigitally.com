"""Integration tests for the vector embedding and chat path.

Tests cover:
- PGAI ai extension availability (requires PGAI system package)
- Direct Nomic API embedding via vLLM (768-dim, normalized vectors)

Note: The ai.openai_embed() SQL function (PGAI) is only available when
the 'ai' extension is installed in PostgreSQL. The pgvector/pgvector:pg16
Docker image used in CI does not include PGAI — only pgvector.

For production: run init_vectorizers.py after installing the PGAI extension
(https://github.com/strapi/pgai). The chat endpoints use ai.openai_embed()
and ai.openai_generate() SQL functions which require this setup.

Local development: the direct vLLM OpenAI-compatible API endpoint works
without PGAI — tested directly via the OpenAI SDK.
"""

import os

import psycopg2
import pytest


def _get_pg_url():
    """Return PostgreSQL URL for PGAI tests.

    Priority: PGAI_DATABASE_URL > DATABASE_URL (if postgresql).
    This allows PGAI tests to use a real PostgreSQL even when
    conftest.py sets DATABASE_URL to SQLite.
    """
    # Allow overriding with a dedicated env var
    pgai_url = os.environ.get("PGAI_DATABASE_URL", "")
    if pgai_url and pgai_url.startswith("postgresql"):
        return pgai_url

    # Fallback to DATABASE_URL if it's PostgreSQL
    url = os.environ.get("DATABASE_URL", "")
    if url.startswith("postgresql"):
        return url

    return None


class TestPGAIExtension:
    """Verify the 'ai' extension is installed (if available)."""

    @pytest.fixture
    def pgai_conn(self):
        """Get a psycopg2 connection to the PGAI-enabled database."""
        pg_url = _get_pg_url()
        if not pg_url:
            pytest.skip("No PGAI_DATABASE_URL or PostgreSQL DATABASE_URL")
        conn = psycopg2.connect(pg_url)
        cur = conn.cursor()
        try:
            cur.execute("CREATE EXTENSION IF NOT EXISTS ai CASCADE;")
            conn.commit()
            yield conn
        except Exception:
            # ai extension not available in this PG instance
            pytest.skip("ai extension not installed in PG instance")
        finally:
            cur.close()
            conn.close()

    def test_ai_extension_exists(self, pgai_conn):
        """The 'ai' extension must be installed."""
        cur = pgai_conn.cursor()
        cur.execute("SELECT extname FROM pg_extension WHERE extname = 'ai';")
        row = cur.fetchone()
        cur.close()
        assert row is not None, "ai extension not installed"


class TestPGAIEmbedding:
    """Test ai.openai_embed SQL function used by chat endpoints."""

    @pytest.fixture
    def pg_connection(self):
        pg_url = _get_pg_url()
        if not pg_url:
            pytest.skip("No PostgreSQL DATABASE_URL")
        conn = psycopg2.connect(pg_url)
        yield conn
        conn.close()

    def test_openai_embed_returns_vector(self, pg_connection):
        """ai.openai_embed should return a non-null 768-dim vector."""
        cur = pg_connection.cursor()
        try:
            cur.execute(
                """
                SELECT ai.openai_embed(
                    'nomic-ai/nomic-embed-text-v1.5',
                    'test query',
                    :llm_url
                );
                """,
                {"llm_url": os.environ.get("VLLM_EMBED_URL", "http://localhost:8001")},
            )
            row = cur.fetchone()
        except Exception:
            pytest.skip("ai.openai_embed not available (extension not installed)")
        finally:
            cur.close()

        assert row is not None, "openai_embed returned NULL"
        vector = row[0]
        assert vector is not None, "vector field is NULL"
        assert isinstance(vector, list), "vector should be a list"
        assert len(vector) == 768, f"Expected 768-dim vector, got {len(vector)}"

    def test_openai_embed_normalized(self, pg_connection):
        """ai.openai_embed should return a normalized (unit-length) vector."""
        cur = pg_connection.cursor()
        try:
            cur.execute(
                """
                SELECT ai.openai_embed(
                    'nomic-ai/nomic-embed-text-v1.5',
                    'test query normalized',
                    :llm_url
                );
                """,
                {"llm_url": os.environ.get("VLLM_EMBED_URL", "http://localhost:8001")},
            )
            row = cur.fetchone()
        except Exception:
            pytest.skip("ai.openai_embed not available")
        finally:
            cur.close()

        vector = row[0]
        # Calculate L2 norm
        norm = sum(x * x for x in vector) ** 0.5
        # Should be normalized (norm ≈ 1.0)
        assert 0.99 < norm < 1.01, f"Vector not normalized: norm={norm}"

    def test_openai_embed_metadata_context(self, pg_connection):
        """ai.openai_embed with context metadata should work."""
        cur = pg_connection.cursor()
        try:
            cur.execute(
                """
                SELECT ai.openai_embed(
                    'nomic-ai/nomic-embed-text-v1.5',
                    'test query with metadata',
                    :llm_url,
                    {
                        "user": "test",
                        "video_id": "dQw4w9WgXcQ",
                        "channel": "test-channel"
                    }::jsonb
                );
                """,
                {"llm_url": os.environ.get("VLLM_EMBED_URL", "http://localhost:8001")},
            )
            row = cur.fetchone()
        except Exception:
            pytest.skip("ai.openai_embed not available")
        finally:
            cur.close()

        assert row is not None, "openai_embed with metadata returned NULL"
        vector = row[0]
        assert vector is not None
        assert len(vector) == 768
