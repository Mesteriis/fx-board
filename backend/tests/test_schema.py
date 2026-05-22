from sqlalchemy import text


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
