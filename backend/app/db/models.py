from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UTCDateTime


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("idx_users_telegram_id", "telegram_id", unique=True),
        Index("idx_users_username", "username"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(Integer, nullable=False)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    last_name: Mapped[str | None] = mapped_column(String(128))
    language_code: Mapped[str | None] = mapped_column(String(16))
    photo_url: Mapped[str | None] = mapped_column(String(512))
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    banned_reason: Mapped[str | None] = mapped_column(String(500))
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (Index("idx_sessions_user_expires", "user_id", "expires_at"),)

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    last_used_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(500))
    ip_hash: Mapped[str | None] = mapped_column(String(128))


class RequiredChannel(Base):
    __tablename__ = "required_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    title: Mapped[str | None] = mapped_column(String(255))
    public_url: Mapped[str | None] = mapped_column(String(512))
    invite_url: Mapped[str | None] = mapped_column(String(512))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class UserChannelMembership(Base):
    __tablename__ = "user_channel_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "channel_id", name="uq_user_channel_memberships_user_channel"),
        Index("idx_user_channel_memberships_user_expires", "user_id", "expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    channel_id: Mapped[int] = mapped_column(ForeignKey("required_channels.id"), nullable=False)
    telegram_status: Mapped[str | None] = mapped_column(String(64))
    is_member: Mapped[bool] = mapped_column(Boolean, nullable=False)
    checked_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    raw_response_json: Mapped[str | None] = mapped_column(Text)


class Ad(Base):
    __tablename__ = "ads"
    __table_args__ = (
        CheckConstraint("side IN ('BUY', 'SELL')", name="ck_ads_side"),
        CheckConstraint(
            "base_currency IN ('USD', 'EUR', 'RUB', 'USDT', 'USDC')",
            name="ck_ads_base_currency",
        ),
        CheckConstraint(
            "quote_currency IN ('USD', 'EUR', 'RUB', 'USDT', 'USDC')",
            name="ck_ads_quote_currency",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'REVOKED', 'HIDDEN', 'EXPIRED', 'COMPLETED')",
            name="ck_ads_status",
        ),
        CheckConstraint("base_currency != quote_currency", name="ck_ads_distinct_currencies"),
        CheckConstraint("amount > 0", name="ck_ads_amount_positive"),
        CheckConstraint("rate > 0", name="ck_ads_rate_positive"),
        Index("idx_ads_status_side_created", "status", "side", "created_at"),
        Index("idx_ads_pair", "base_currency", "quote_currency"),
        Index("idx_ads_user_status", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(8), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(8), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    min_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    max_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    payment_method: Mapped[str | None] = mapped_column(String(120))
    location: Mapped[str | None] = mapped_column(String(120))
    comment: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    report_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    hidden_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        CheckConstraint(
            "reason IN ('SCAM', 'SPAM', 'WRONG_RATE', 'OFFENSIVE', 'DUPLICATE', "
            "'FAKE_CONTACT', 'OTHER')",
            name="ck_reports_reason",
        ),
        CheckConstraint(
            "status IN ('NEW', 'IN_REVIEW', 'RESOLVED', 'REJECTED')",
            name="ck_reports_status",
        ),
        Index("idx_reports_status_created", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reporter_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    target_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    ad_id: Mapped[int | None] = mapped_column(ForeignKey("ads.id"))
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    comment: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    resolved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


Index(
    "idx_reports_unique_user_ad",
    Report.reporter_user_id,
    Report.ad_id,
    unique=True,
    sqlite_where=Report.ad_id.is_not(None),
)


class Rate(Base):
    __tablename__ = "rates"
    __table_args__ = (
        UniqueConstraint("pair", "rate_date", name="uq_rates_pair_date"),
        Index("idx_rates_date_pair", "rate_date", "pair"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pair: Mapped[str] = mapped_column(String(16), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    raw_payload: Mapped[str | None] = mapped_column(Text)


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (Index("idx_audit_log_created", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(Integer)
    payload_json: Mapped[str | None] = mapped_column(Text)
    ip_hash: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class RateLimitEvent(Base):
    __tablename__ = "rate_limit_events"
    __table_args__ = (Index("idx_rate_limit_key_action_created", "key", "action", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(160), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class ContactAttempt(Base):
    __tablename__ = "contact_attempts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('OPENED', 'CANCELED_BY_NEW_CONTACT', 'ASKED_INITIATOR', "
            "'INITIATOR_NO_DEAL', 'WAITING_AUTHOR_CONFIRMATION', 'COMPLETED_CONFIRMED', "
            "'AUTHOR_REJECTED', 'EXPIRED')",
            name="ck_contact_attempts_status",
        ),
        Index("idx_contact_attempts_due", "status", "followup_due_at"),
        Index("idx_contact_attempts_initiator_status", "initiator_user_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    initiator_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    author_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    ad_id: Mapped[int] = mapped_column(ForeignKey("ads.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    followup_due_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    initiator_answered_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    author_answered_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


Index(
    "idx_contact_attempts_one_opened_per_initiator",
    ContactAttempt.initiator_user_id,
    unique=True,
    sqlite_where=ContactAttempt.status == "OPENED",
)
