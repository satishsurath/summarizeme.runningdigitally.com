"""allow versioned summary runs

Revision ID: e2f3a4b5c6d7
Revises: d5e6a7f8a9b0
Create Date: 2026-08-27 15:15:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e2f3a4b5c6d7"
down_revision: str | Sequence[str] | None = "d5e6a7f8a9b0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Remove the constraint that overwrites earlier generations."""
    op.drop_constraint("uq_summary_runs_video_model_effort", "summary_runs", type_="unique")


def downgrade() -> None:
    """Restore the former one-run-per-model-and-effort constraint."""
    op.create_unique_constraint(
        "uq_summary_runs_video_model_effort",
        "summary_runs",
        ["video_id", "model_name", "reasoning_effort"],
    )
