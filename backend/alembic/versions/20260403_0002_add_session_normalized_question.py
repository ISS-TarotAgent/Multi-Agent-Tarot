from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260403_0002"
down_revision = "20260403_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("normalized_question", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("sessions", "normalized_question")
