"""contact prompt timestamps

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-22

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "contact_attempts",
        sa.Column("initiator_prompt_sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "contact_attempts",
        sa.Column("author_prompt_sent_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("contact_attempts", "author_prompt_sent_at")
    op.drop_column("contact_attempts", "initiator_prompt_sent_at")
