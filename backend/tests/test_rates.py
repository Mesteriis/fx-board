from datetime import timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.core.time import utc_now
from app.db.models import Rate


def test_parse_rates_csv_validates_columns_and_normalizes_rates() -> None:
    from app.services.rates import parse_rates_csv

    parsed = parse_rates_csv(
        "pair,rate,source,updated_at\n"
        "usd/rub,92.5,googlefinance,2026-05-22T10:00:00Z\n"
        "USD/EUR,0.923456,googlefinance,2026-05-22T10:00:00Z\n"
    )

    assert parsed == {"USD/RUB": "92.5000", "USD/EUR": "0.9235"}

    with pytest.raises(ValueError, match="invalid columns"):
        parse_rates_csv("pair,rate\nUSD/RUB,92.5\n")

    with pytest.raises(ValueError, match="invalid rate"):
        parse_rates_csv(
            "pair,rate,source,updated_at\n"
            "USD/RUB,0,googlefinance,2026-05-22T10:00:00Z\n"
        )

    with pytest.raises(ValueError, match="invalid rate"):
        parse_rates_csv(
            "pair,rate,source,updated_at\n"
            "USD/RUB,NaN,googlefinance,2026-05-22T10:00:00Z\n"
        )


def test_rates_derives_stablecoin_pairs() -> None:
    from app.services.rates import derive_stablecoin_rates

    derived = derive_stablecoin_rates({"USD/RUB": "92.5000", "USD/EUR": "0.9200"})

    assert derived["USDT/USD"] == "1.0000"
    assert derived["USDC/USD"] == "1.0000"
    assert derived["USDT/RUB"] == "92.5000"
    assert derived["USDC/RUB"] == "92.5000"
    assert derived["USDT/EUR"] == "0.9200"
    assert derived["USDC/EUR"] == "0.9200"


async def test_get_rates_fetches_csv_stores_base_and_derived_rates(
    test_session,
    test_settings,
    fake_notification_sink,
) -> None:
    from app.services.rates import get_rates

    test_settings.google_rates_csv_url = "https://example.test/rates.csv"

    async def fetch_csv(url: str) -> str:
        assert url == "https://example.test/rates.csv"
        return (
            "pair,rate,source,updated_at\n"
            "USD/RUB,92.5,googlefinance,2026-05-22T10:00:00Z\n"
            "USD/EUR,0.92,googlefinance,2026-05-22T10:00:00Z\n"
        )

    response = await get_rates(
        test_session,
        settings=test_settings,
        fetch_csv=fetch_csv,
        notification_sink=fake_notification_sink,
    )

    assert response.source == "googlefinance"
    assert response.is_stale is False
    assert {item.pair: item.rate for item in response.rates} == {
        "USDC/EUR": "0.9200",
        "USDC/RUB": "92.5000",
        "USDC/USD": "1.0000",
        "USDT/EUR": "0.9200",
        "USDT/RUB": "92.5000",
        "USDT/USD": "1.0000",
        "USD/EUR": "0.9200",
        "USD/RUB": "92.5000",
    }
    assert fake_notification_sink.intents == []

    stored = (await test_session.execute(select(Rate).order_by(Rate.pair))).scalars().all()
    assert [row.pair for row in stored] == [item.pair for item in response.rates]
    assert stored[0].rate_date.isoformat() == response.date
    assert {row.pair: f"{row.rate:.4f}" for row in stored}["USD/RUB"] == "92.5000"


async def test_get_rates_uses_daily_cache_without_fetching(
    test_session,
    test_settings,
    fake_notification_sink,
) -> None:
    from app.services.rates import get_rates

    today = utc_now().astimezone(ZoneInfo(test_settings.rates_refresh_timezone)).date()
    fetched_at = utc_now()
    test_session.add(
        Rate(
            pair="USD/RUB",
            rate=Decimal("91.2500"),
            source="googlefinance",
            rate_date=today,
            fetched_at=fetched_at,
            raw_payload="cached",
        )
    )
    await test_session.commit()

    async def fetch_csv(_url: str) -> str:
        raise AssertionError("daily cache should avoid fetching rates")

    response = await get_rates(
        test_session,
        settings=test_settings,
        fetch_csv=fetch_csv,
        notification_sink=fake_notification_sink,
    )

    assert response.is_stale is False
    assert response.date == today.isoformat()
    assert [(item.pair, item.rate) for item in response.rates] == [("USD/RUB", "91.2500")]
    assert fake_notification_sink.intents == []


async def test_get_rates_returns_stale_latest_rates_when_fetch_fails(
    test_session,
    test_settings,
    fake_notification_sink,
) -> None:
    from app.services.rates import get_rates

    historical_date = utc_now().date() - timedelta(days=1)
    fetched_at = utc_now() - timedelta(days=1)
    test_session.add(
        Rate(
            pair="USD/RUB",
            rate=Decimal("90.0000"),
            source="googlefinance",
            rate_date=historical_date,
            fetched_at=fetched_at,
            raw_payload="historical",
        )
    )
    await test_session.commit()

    async def fetch_csv(_url: str) -> str:
        raise ValueError("csv exploded")

    response = await get_rates(
        test_session,
        settings=test_settings,
        fetch_csv=fetch_csv,
        notification_sink=fake_notification_sink,
    )

    assert response.is_stale is True
    assert response.date == historical_date.isoformat()
    assert [(item.pair, item.rate) for item in response.rates] == [("USD/RUB", "90.0000")]
    assert [intent.kind for intent in fake_notification_sink.intents] == ["admin_technical"]
    assert fake_notification_sink.intents[0].payload["event"] == "rates_refresh_failed"


async def test_get_rates_returns_stale_latest_rates_when_csv_has_nan(
    test_session,
    test_settings,
    fake_notification_sink,
) -> None:
    from app.services.rates import get_rates

    historical_date = utc_now().date() - timedelta(days=1)
    fetched_at = utc_now() - timedelta(days=1)
    test_session.add(
        Rate(
            pair="USD/RUB",
            rate=Decimal("90.0000"),
            source="googlefinance",
            rate_date=historical_date,
            fetched_at=fetched_at,
            raw_payload="historical",
        )
    )
    await test_session.commit()

    async def fetch_csv(_url: str) -> str:
        return (
            "pair,rate,source,updated_at\n"
            "USD/RUB,NaN,googlefinance,2026-05-22T10:00:00Z\n"
        )

    response = await get_rates(
        test_session,
        settings=test_settings,
        fetch_csv=fetch_csv,
        notification_sink=fake_notification_sink,
    )

    assert response.is_stale is True
    assert [(item.pair, item.rate) for item in response.rates] == [("USD/RUB", "90.0000")]
    assert [intent.kind for intent in fake_notification_sink.intents] == ["admin_technical"]


async def test_get_rates_does_not_commit_caller_transaction(
    test_session,
    test_settings,
    fake_notification_sink,
) -> None:
    from app.services.rates import get_rates

    test_settings.google_rates_csv_url = "https://example.test/rates.csv"

    async def fetch_csv(_url: str) -> str:
        return (
            "pair,rate,source,updated_at\n"
            "USD/RUB,92.5,googlefinance,2026-05-22T10:00:00Z\n"
        )

    await get_rates(
        test_session,
        settings=test_settings,
        fetch_csv=fetch_csv,
        notification_sink=fake_notification_sink,
    )
    await test_session.rollback()

    stored = (await test_session.execute(select(Rate))).scalars().all()
    assert stored == []


async def test_get_rates_raises_app_error_when_fetch_fails_without_saved_rates(
    test_session,
    test_settings,
    fake_notification_sink,
) -> None:
    from app.services.rates import RatesUnavailableError, get_rates

    async def fetch_csv(_url: str) -> str:
        raise ValueError("csv exploded")

    with pytest.raises(RatesUnavailableError) as exc_info:
        await get_rates(
            test_session,
            settings=test_settings,
            fetch_csv=fetch_csv,
            notification_sink=fake_notification_sink,
        )

    assert exc_info.value.code == "rates_unavailable"
    assert exc_info.value.status_code == 503
    assert [intent.kind for intent in fake_notification_sink.intents] == ["admin_technical"]
