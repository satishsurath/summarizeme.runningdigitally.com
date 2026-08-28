"""add summary_runs table

Revision ID: b3c4d5e6a7f8
Revises: f2b3c4d5e6a7
Create Date: 2026-08-27 14:15:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3c4d5e6a7f8"
down_revision: str | Sequence[str] | None = "f2b3c4d5e6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "summary_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("video_id", sa.String(length=50), nullable=False),
        sa.Column("model_name", sa.String(length=64), nullable=False),
        sa.Column("reasoning_effort", sa.String(length=32), server_default="medium", nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("completion_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("reasoning_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("generation_profile_hash", sa.String(length=64), nullable=True),
        sa.Column("structured_summary", sa.JSON(), nullable=False),
        sa.Column("reasoning_output", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="completed", nullable=False),
        sa.Column("validation_errors", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["video_id"], ["videos.video_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("video_id", "model_name", "reasoning_effort", name="uq_summary_runs_video_model_effort"),
    )
    op.create_index("ix_summary_runs_video_id", "summary_runs", ["video_id"], unique=False)
    op.create_index("ix_summary_runs_created_at", "summary_runs", ["created_at"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("summary_runs")
