"""Add conversation state table and conversation_id on questions

Revision ID: 0296
Revises: 0295
Create Date: 2025-12-29 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0297"
down_revision: Union[str, None] = "0296"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # 1) Wire conversation_id into questions so each question can be
    #    associated with a logical conversation.
    op.add_column(
        "questions",
        sa.Column("conversation_id", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "idx_questions_conversation",
        "questions",
        ["conversation_id"],
        unique=False,
    )

    # 2) Add a small table to store per-conversation state used by
    #    _load_conversation_state / _save_conversation_state in
    #    LangGraphOrchestrationAPI.
    #
    #    We use conversation_id as the primary key so there is exactly
    #    one row per logical conversation, and keep the payload in a
    #    single JSONB column for flexibility.
    op.create_table(
        "conversation_states",
        sa.Column(
            "conversation_id",
            sa.String(length=255),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "state",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Arbitrary conversation-scoped state (wizard, classifier_result, etc.)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Optional: index updated_at for “recent conversations” queries.
    op.create_index(
        "idx_conversation_states_updated",
        "conversation_states",
        ["updated_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""

    # Drop conversation_states table + index
    op.drop_index(
        "idx_conversation_states_updated",
        table_name="conversation_states",
    )
    op.drop_table("conversation_states")

    # Remove conversation_id from questions
    op.drop_index(
        "idx_questions_conversation",
        table_name="questions",
    )
    op.drop_column("questions", "conversation_id")
