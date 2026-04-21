from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260421_0003"
down_revision = "20260403_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("intent_tag", sa.Text(), nullable=True))
    op.add_column(
        "sessions",
        sa.Column(
            "clarification_prompts",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "sessions",
        sa.Column(
            "clarification_answers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "reading_cards",
        sa.Column("reflection_question", sa.Text(), nullable=True),
    )
    op.add_column(
        "reading_cards",
        sa.Column("caution_note", sa.Text(), nullable=True),
    )
    op.add_column(
        "reading_cards",
        sa.Column(
            "keywords",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("reading_cards", "keywords")
    op.drop_column("reading_cards", "caution_note")
    op.drop_column("reading_cards", "reflection_question")
    op.drop_column("sessions", "clarification_answers")
    op.drop_column("sessions", "clarification_prompts")
    op.drop_column("sessions", "intent_tag")
