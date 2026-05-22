"""initial

Revision ID: 0001
Revises:
Create Date: 2026-05-22

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("key", sa.String(length=160), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_rate_limit_key_action_created",
        "rate_limit_events",
        ["key", "action", "created_at"],
        unique=False,
    )

    op.create_table(
        "rates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("pair", sa.String(length=16), nullable=False),
        sa.Column("rate", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("rate_date", sa.Date(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_payload", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pair", "rate_date", name="uq_rates_pair_date"),
    )
    op.create_index("idx_rates_date_pair", "rates", ["rate_date", "pair"], unique=False)

    op.create_table(
        "required_channels",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chat_id", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("public_url", sa.String(length=512), nullable=True),
        sa.Column("invite_url", sa.String(length=512), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chat_id"),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("telegram_id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("first_name", sa.String(length=128), nullable=True),
        sa.Column("last_name", sa.String(length=128), nullable=True),
        sa.Column("language_code", sa.String(length=16), nullable=True),
        sa.Column("photo_url", sa.String(length=512), nullable=True),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.Column("is_banned", sa.Boolean(), nullable=False),
        sa.Column("banned_reason", sa.String(length=500), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_id"),
    )
    op.create_index("idx_users_telegram_id", "users", ["telegram_id"], unique=False)

    op.create_table(
        "ads",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("base_currency", sa.String(length=8), nullable=False),
        sa.Column("quote_currency", sa.String(length=8), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("min_amount", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("max_amount", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("rate", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("payment_method", sa.String(length=120), nullable=True),
        sa.Column("location", sa.String(length=120), nullable=True),
        sa.Column("comment", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("report_count", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hidden_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_ads_amount_positive"),
        sa.CheckConstraint(
            "base_currency IN ('USD', 'EUR', 'RUB', 'USDT', 'USDC')",
            name="ck_ads_base_currency",
        ),
        sa.CheckConstraint("base_currency != quote_currency", name="ck_ads_distinct_currencies"),
        sa.CheckConstraint(
            "quote_currency IN ('USD', 'EUR', 'RUB', 'USDT', 'USDC')",
            name="ck_ads_quote_currency",
        ),
        sa.CheckConstraint("rate > 0", name="ck_ads_rate_positive"),
        sa.CheckConstraint("side IN ('BUY', 'SELL')", name="ck_ads_side"),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'REVOKED', 'HIDDEN', 'EXPIRED', 'COMPLETED')",
            name="ck_ads_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_ads_pair", "ads", ["base_currency", "quote_currency"], unique=False)
    op.create_index(
        "idx_ads_status_side_created",
        "ads",
        ["status", "side", "created_at"],
        unique=False,
    )
    op.create_index("idx_ads_user_status", "ads", ["user_id", "status"], unique=False)

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("ip_hash", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_audit_log_created", "audit_log", ["created_at"], unique=False)

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("ip_hash", sa.String(length=128), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_sessions_user_expires", "sessions", ["user_id", "expires_at"])

    op.create_table(
        "user_channel_memberships",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("telegram_status", sa.String(length=64), nullable=True),
        sa.Column("is_member", sa.Boolean(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_response_json", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["channel_id"], ["required_channels.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "channel_id",
            name="uq_user_channel_memberships_user_channel",
        ),
    )
    op.create_index(
        "idx_user_channel_memberships_user_expires",
        "user_channel_memberships",
        ["user_id", "expires_at"],
        unique=False,
    )

    op.create_table(
        "contact_attempts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("initiator_user_id", sa.Integer(), nullable=False),
        sa.Column("author_user_id", sa.Integer(), nullable=False),
        sa.Column("ad_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("followup_due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("initiator_answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("author_answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('OPENED', 'CANCELED_BY_NEW_CONTACT', 'ASKED_INITIATOR', "
            "'INITIATOR_NO_DEAL', 'WAITING_AUTHOR_CONFIRMATION', 'COMPLETED_CONFIRMED', "
            "'AUTHOR_REJECTED', 'EXPIRED')",
            name="ck_contact_attempts_status",
        ),
        sa.ForeignKeyConstraint(["ad_id"], ["ads.id"]),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["initiator_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_contact_attempts_due",
        "contact_attempts",
        ["status", "followup_due_at"],
        unique=False,
    )
    op.create_index(
        "idx_contact_attempts_initiator_status",
        "contact_attempts",
        ["initiator_user_id", "status"],
        unique=False,
    )

    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("reporter_user_id", sa.Integer(), nullable=False),
        sa.Column("target_user_id", sa.Integer(), nullable=False),
        sa.Column("ad_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("comment", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("resolved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "reason IN ('SCAM', 'SPAM', 'WRONG_RATE', 'OFFENSIVE', 'DUPLICATE', "
            "'FAKE_CONTACT', 'OTHER')",
            name="ck_reports_reason",
        ),
        sa.CheckConstraint(
            "status IN ('NEW', 'IN_REVIEW', 'RESOLVED', 'REJECTED')",
            name="ck_reports_status",
        ),
        sa.ForeignKeyConstraint(["ad_id"], ["ads.id"]),
        sa.ForeignKeyConstraint(["reporter_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["resolved_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_reports_status_created",
        "reports",
        ["status", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_reports_unique_user_ad",
        "reports",
        ["reporter_user_id", "ad_id"],
        unique=True,
        sqlite_where=sa.text("ad_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_reports_unique_user_ad", table_name="reports")
    op.drop_index("idx_reports_status_created", table_name="reports")
    op.drop_table("reports")
    op.drop_index("idx_contact_attempts_initiator_status", table_name="contact_attempts")
    op.drop_index("idx_contact_attempts_due", table_name="contact_attempts")
    op.drop_table("contact_attempts")
    op.drop_index(
        "idx_user_channel_memberships_user_expires",
        table_name="user_channel_memberships",
    )
    op.drop_table("user_channel_memberships")
    op.drop_index("idx_sessions_user_expires", table_name="sessions")
    op.drop_table("sessions")
    op.drop_index("idx_audit_log_created", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_index("idx_ads_user_status", table_name="ads")
    op.drop_index("idx_ads_status_side_created", table_name="ads")
    op.drop_index("idx_ads_pair", table_name="ads")
    op.drop_table("ads")
    op.drop_index("idx_users_telegram_id", table_name="users")
    op.drop_table("users")
    op.drop_table("required_channels")
    op.drop_index("idx_rates_date_pair", table_name="rates")
    op.drop_table("rates")
    op.drop_index("idx_rate_limit_key_action_created", table_name="rate_limit_events")
    op.drop_table("rate_limit_events")
