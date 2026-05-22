"""add AR currency

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-22

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_CURRENCY_CHECK = "currency IN ('USD', 'EUR', 'RUB', 'USDT', 'USDC')"
NEW_CURRENCY_CHECK = "currency IN ('USD', 'EUR', 'RUB', 'USDT', 'USDC', 'AR')"


def upgrade() -> None:
    _replace_currency_constraints(NEW_CURRENCY_CHECK)


def downgrade() -> None:
    _replace_currency_constraints(OLD_CURRENCY_CHECK)


def _replace_currency_constraints(currency_check: str) -> None:
    op.drop_constraint("ck_ads_base_currency", "ads", type_="check")
    op.drop_constraint("ck_ads_quote_currency", "ads", type_="check")
    op.create_check_constraint(
        "ck_ads_base_currency",
        "ads",
        currency_check.replace("currency", "base_currency"),
    )
    op.create_check_constraint(
        "ck_ads_quote_currency",
        "ads",
        currency_check.replace("currency", "quote_currency"),
    )
