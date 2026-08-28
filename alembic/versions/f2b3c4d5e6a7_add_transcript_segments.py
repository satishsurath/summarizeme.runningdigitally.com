"""add transcript_segments table

Revision ID: f2b3c4d5e6a7
Revises: e1a2b3c4d5f6
Create Date: 2026-08-27 14:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2b3c4d5e6a7"
down_revision: str | Sequence[str] | None = "e1a2b3c4d5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "transcript_segments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("video_id", sa.String(length=50), nullable=False),
        sa.Column("segment_index", sa.Integer(), nullable=False),
        sa.Column("start_seconds", sa.Float(), nullable=False),
        sa.Column("end_seconds", sa.Float(), nullable=False),
        sa.Column("speaker", sa.String(length=255), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["video_id"], ["videos.video_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("video_id", "segment_index", name="uq_transcript_segments_video_idx"),
    )
    op.create_index("ix_transcript_segments_video_id", "transcript_segments", ["video_id"], unique=False)
    op.create_index(
        "ix_transcript_segments_video_start", "transcript_segments", ["video_id", "start_seconds"], unique=False
    )
    op.create_index("ix_transcript_segments_hash", "transcript_segments", ["content_hash"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("transcript_segments")
