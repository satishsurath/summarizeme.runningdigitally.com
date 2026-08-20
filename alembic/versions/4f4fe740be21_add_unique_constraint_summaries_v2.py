"""add unique constraint on summaries_v2 (video_id, model_name)

Revision ID: 4f4fe740be21
Revises: d83220d1c993
Create Date: 2026-08-19 19:15:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4f4fe740be21"
down_revision: str | Sequence[str] | None = "d83220d1c993"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Deduplicate any pre-existing (video_id, model_name) pairs, keeping the
    # newest row (highest id) per pair. NULL video_id/model_name never match,
    # so rows with NULLs are untouched.
    op.execute(
        """
        DELETE FROM summaries_v2 a
        USING summaries_v2 b
        WHERE a.video_id = b.video_id
          AND a.model_name = b.model_name
          AND a.id < b.id
        """
    )
    op.create_unique_constraint("uq_summaries_v2_video_model", "summaries_v2", ["video_id", "model_name"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("uq_summaries_v2_video_model", "summaries_v2", type_="unique")
