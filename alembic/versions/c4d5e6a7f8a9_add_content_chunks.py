"""add content_chunks table

Revision ID: c4d5e6a7f8a9
Revises: b3c4d5e6a7f8
Create Date: 2026-08-27 14:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4d5e6a7f8a9"
down_revision: str | Sequence[str] | None = "b3c4d5e6a7f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "content_chunks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("video_id", sa.String(length=50), nullable=False),
        sa.Column("chunk_type", sa.String(length=32), nullable=False),
        sa.Column("parent_id", sa.String(length=64), nullable=True),
        sa.Column("sequence_index", sa.Integer(), nullable=False),
        sa.Column("start_seconds", sa.Float(), nullable=True),
        sa.Column("end_seconds", sa.Float(), nullable=True),
        sa.Column("speaker", sa.String(length=255), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["video_id"], ["videos.video_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("video_id", "chunk_type", "sequence_index", name="uq_content_chunks_video_type_seq"),
    )
    op.create_index("ix_content_chunks_video_id", "content_chunks", ["video_id"], unique=False)
    op.create_index("ix_content_chunks_video_type", "content_chunks", ["video_id", "chunk_type"], unique=False)
    op.create_index(
        "ix_content_chunks_start_seconds",
        "content_chunks",
        ["video_id", "start_seconds"],
        unique=False,
    )
    op.create_index("ix_content_chunks_hash", "content_chunks", ["content_hash"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("content_chunks")
