"""add pgvector and fts indexes on content_chunks

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-08-27 16:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3a4b5c6d7e8"
down_revision: str | Sequence[str] | None = "e2f3a4b5c6d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema to support PostgreSQL pgvector HNSW and Full-Text Search GIN indexes."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        op.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'content_chunks' AND column_name = 'embedding_vec'
                ) THEN
                    ALTER TABLE content_chunks ADD COLUMN embedding_vec vector(768);
                END IF;
            END $$;
            """
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_content_chunks_embedding_hnsw "
            "ON content_chunks USING hnsw (embedding_vec vector_cosine_ops);"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_content_chunks_fts "
            "ON content_chunks USING gin (to_tsvector('english', text));"
        )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_content_chunks_fts;")
        op.execute("DROP INDEX IF EXISTS ix_content_chunks_embedding_hnsw;")
        op.execute("ALTER TABLE content_chunks DROP COLUMN IF EXISTS embedding_vec;")
