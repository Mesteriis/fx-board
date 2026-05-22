"""unique opened contact attempt per initiator

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-22

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "idx_contact_attempts_one_opened_per_initiator",
        "contact_attempts",
        ["initiator_user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'OPENED'"),
    )


def downgrade() -> None:
    op.drop_index(
        "idx_contact_attempts_one_opened_per_initiator",
        table_name="contact_attempts",
    )
