"""add content_type to video_folders

Revision ID: d83220d1c993
Revises: 9fb76444a01b
Create Date: 2026-08-19 19:10:17.320544

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d83220d1c993"
down_revision: str | Sequence[str] | None = "9fb76444a01b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Server default so the add succeeds on non-empty tables; the ORM also
    # supplies "playlist" as a Python-side default.
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("video_folders")]
    if "content_type" not in columns:
        op.add_column(
            "video_folders",
            sa.Column("content_type", sa.String(length=20), server_default="playlist", nullable=False),
        )


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("video_folders")]
    if "content_type" in columns:
        op.drop_column("video_folders", "content_type")
