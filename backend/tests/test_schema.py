import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, StatementError

from app.db.models import Ad, Report, Session, User
from app.db.session import DEFAULT_DATABASE_URL, create_engine, get_database_url


def utc_datetime(offset_seconds: int = 0) -> datetime:
    return datetime(2026, 5, 22, 12, 0, offset_seconds, tzinfo=UTC)


def make_user(telegram_id: int, username: str | None = None) -> User:
    now = utc_datetime()
    return User(
        telegram_id=telegram_id,
        username=username,
        is_admin=False,
        is_banned=False,
        first_seen_at=now,
        last_seen_at=now,
        created_at=now,
        updated_at=now,
    )


def make_ad(user_id: int, *, side: str = "SELL", quote_currency: str = "RUB") -> Ad:
    now = utc_datetime()
    return Ad(
        user_id=user_id,
        side=side,
        base_currency="USD",
        quote_currency=quote_currency,
        amount=Decimal("100.00"),
        rate=Decimal("92.50"),
        status="ACTIVE",
        report_count=0,
        expires_at=now + timedelta(hours=24),
        created_at=now,
        updated_at=now,
    )


async def commit_expecting_integrity_error(test_session) -> None:
    with pytest.raises(IntegrityError):
        await test_session.commit()
    await test_session.rollback()


async def test_sqlite_pragmas_and_tables(test_session) -> None:
    result = await test_session.execute(text("PRAGMA foreign_keys"))
    assert result.scalar_one() == 1

    result = await test_session.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    )
    tables = {row[0] for row in result.all()}

    assert {
        "ads",
        "audit_log",
        "contact_attempts",
        "rate_limit_events",
        "rates",
        "reports",
        "required_channels",
        "sessions",
        "user_channel_memberships",
        "users",
    }.issubset(tables)

    result = await test_session.execute(text("PRAGMA index_list('users')"))
    user_indexes = {row[1]: bool(row[2]) for row in result.all()}

    assert "idx_users_username" in user_indexes
    assert user_indexes["idx_users_telegram_id"] is True


async def test_utc_datetimes_round_trip_as_aware_utc(test_session) -> None:
    non_utc = datetime(
        2026,
        5,
        22,
        15,
        30,
        tzinfo=timezone(timedelta(hours=3)),
    )
    expected_utc = non_utc.astimezone(UTC)
    user = make_user(telegram_id=1001, username="timestamp_user")
    test_session.add(user)
    await test_session.flush()
    test_session.add(
        Session(
            id="session-token",
            user_id=user.id,
            expires_at=non_utc,
            created_at=non_utc,
            last_used_at=non_utc,
        )
    )
    await test_session.commit()
    test_session.expire_all()

    session = await test_session.get(Session, "session-token")

    assert session is not None
    assert session.expires_at.tzinfo is not None
    assert session.expires_at.utcoffset() == timedelta(0)
    assert session.expires_at == expected_utc


async def test_utc_datetime_rejects_naive_datetimes(test_session) -> None:
    user = make_user(telegram_id=1006, username="naive_datetime_user")
    test_session.add(user)
    await test_session.flush()
    test_session.add(
        Session(
            id="naive-session",
            user_id=user.id,
            expires_at=datetime(2026, 5, 22, 12, 0),
            created_at=utc_datetime(),
            last_used_at=utc_datetime(),
        )
    )

    with pytest.raises(StatementError):
        await test_session.commit()
    await test_session.rollback()


async def test_foreign_key_enforcement_rejects_invalid_child(test_session) -> None:
    test_session.add(
        Session(
            id="orphan-session",
            user_id=999,
            expires_at=utc_datetime(),
            created_at=utc_datetime(),
            last_used_at=utc_datetime(),
        )
    )

    await commit_expecting_integrity_error(test_session)


async def test_ad_check_constraints_reject_invalid_side_and_same_currency(test_session) -> None:
    user = make_user(telegram_id=1002)
    test_session.add(user)
    await test_session.commit()
    user_id = user.id

    test_session.add(make_ad(user_id, side="TRADE"))
    await commit_expecting_integrity_error(test_session)

    test_session.add(make_ad(user_id, quote_currency="USD"))
    await commit_expecting_integrity_error(test_session)


async def test_unique_telegram_id_index_rejects_duplicates(test_session) -> None:
    test_session.add_all(
        [
            make_user(telegram_id=1003, username="duplicate_a"),
            make_user(telegram_id=1003, username="duplicate_b"),
        ]
    )

    await commit_expecting_integrity_error(test_session)


async def test_report_partial_unique_index_allows_null_ad_id_only(test_session) -> None:
    reporter = make_user(telegram_id=1004, username="reporter")
    target = make_user(telegram_id=1005, username="target")
    test_session.add_all([reporter, target])
    await test_session.commit()

    now = utc_datetime()
    test_session.add_all(
        [
            Report(
                reporter_user_id=reporter.id,
                target_user_id=target.id,
                ad_id=None,
                reason="SPAM",
                status="NEW",
                created_at=now,
                updated_at=now,
            ),
            Report(
                reporter_user_id=reporter.id,
                target_user_id=target.id,
                ad_id=None,
                reason="SCAM",
                status="NEW",
                created_at=now,
                updated_at=now,
            ),
        ]
    )
    await test_session.commit()

    ad = make_ad(target.id)
    test_session.add(ad)
    await test_session.commit()

    test_session.add_all(
        [
            Report(
                reporter_user_id=reporter.id,
                target_user_id=target.id,
                ad_id=ad.id,
                reason="SPAM",
                status="NEW",
                created_at=now,
                updated_at=now,
            ),
            Report(
                reporter_user_id=reporter.id,
                target_user_id=target.id,
                ad_id=ad.id,
                reason="SCAM",
                status="NEW",
                created_at=now,
                updated_at=now,
            ),
        ]
    )

    await commit_expecting_integrity_error(test_session)

    result = await test_session.execute(select(Report).where(Report.ad_id.is_(None)))
    assert len(result.scalars().all()) == 2


def test_alembic_upgrade_and_downgrade_file_db(tmp_path) -> None:
    database_path = tmp_path / "schema.db"
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite+aiosqlite:///{database_path}",
    }

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
        cwd=os.getcwd(),
        env=env,
    )
    subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "base"],
        check=True,
        cwd=os.getcwd(),
        env=env,
    )


def test_explicit_database_url_wins(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///env.db")

    engine = create_engine("sqlite+aiosqlite:///explicit.db")

    assert str(engine.url) == "sqlite+aiosqlite:///explicit.db"


def test_exported_database_url_wins_over_env_file(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///exported.db")
    (tmp_path / ".env").write_text('DATABASE_URL="sqlite+aiosqlite:///dotenv.db"\n')

    assert get_database_url() == "sqlite+aiosqlite:///exported.db"


def test_database_url_reads_env_file_when_process_env_absent(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    (tmp_path / ".env").write_text(
        "# unrelated settings must not be parsed\n"
        "SESSION_SECRET=too-short\n"
        "DATABASE_URL='sqlite+aiosqlite:///dotenv.db'\n"
    )

    assert get_database_url() == "sqlite+aiosqlite:///dotenv.db"


async def test_default_sqlite_parent_directory_is_created(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    engine = create_engine(DEFAULT_DATABASE_URL)
    try:
        async with engine.connect() as connection:
            result = await connection.execute(text("SELECT 1"))
            assert result.scalar_one() == 1
    finally:
        await engine.dispose()

    assert (tmp_path / "data").is_dir()
