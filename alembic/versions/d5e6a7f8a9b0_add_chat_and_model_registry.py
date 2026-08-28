"""add chat and model registry tables

Revision ID: d5e6a7f8a9b0
Revises: c4d5e6a7f8a9
Create Date: 2026-08-27 14:25:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5e6a7f8a9b0"
down_revision: str | Sequence[str] | None = "c4d5e6a7f8a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. conversations
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("scope_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("model_name", sa.String(length=64), nullable=False),
        sa.Column("reasoning_effort", sa.String(length=32), server_default="medium", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"], unique=False)
    op.create_index("ix_conversations_scope", "conversations", ["scope_type", "scope_id"], unique=False)

    # 2. conversation_messages
    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("sequence_index", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("reasoning_content", sa.Text(), nullable=True),
        sa.Column("sources", sa.JSON(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("completion_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("reasoning_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversation_id", "sequence_index", name="uq_conversation_messages_conv_seq"),
    )
    op.create_index("ix_conversation_messages_conv_id", "conversation_messages", ["conversation_id"], unique=False)

    # 3. ai_endpoints
    op.create_table(
        "ai_endpoints",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("endpoint_type", sa.String(length=32), nullable=False),
        sa.Column("base_url", sa.String(length=255), nullable=False),
        sa.Column("api_key", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # 4. ai_models
    op.create_table(
        "ai_models",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("endpoint_id", sa.String(length=36), nullable=False),
        sa.Column("model_id", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("family", sa.String(length=64), nullable=False),
        sa.Column("context_window", sa.Integer(), server_default="32768", nullable=False),
        sa.Column("qualification_status", sa.String(length=32), server_default="passed", nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["endpoint_id"], ["ai_endpoints.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("endpoint_id", "model_id", name="uq_ai_models_endpoint_model"),
    )
    op.create_index("ix_ai_models_endpoint_id", "ai_models", ["endpoint_id"], unique=False)

    # 5. ai_runtime_pools
    op.create_table(
        "ai_runtime_pools",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("max_in_flight", sa.Integer(), server_default="3", nullable=False),
        sa.Column("interactive_reserve", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # 6. user_ai_preferences
    op.create_table(
        "user_ai_preferences",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("preferred_gen_model", sa.String(length=128), nullable=True),
        sa.Column("preferred_reasoning_effort", sa.String(length=32), server_default="medium", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_user_ai_preferences_user_id", "user_ai_preferences", ["user_id"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("user_ai_preferences")
    op.drop_table("ai_runtime_pools")
    op.drop_table("ai_models")
    op.drop_table("ai_endpoints")
    op.drop_table("conversation_messages")
    op.drop_table("conversations")
