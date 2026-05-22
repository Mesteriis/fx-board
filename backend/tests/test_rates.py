from datetime import timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.core.time import utc_now
from app.db.models import Rate

CBR_XML = """<?xml version="1.0" encoding="windows-1251"?>
<ValCurs Date="23.05.2026" name="Foreign Currency Market">
  <Valute ID="R01235">
    <NumCode>840</NumCode>
    <CharCode>USD</CharCode>
    <Nominal>1</Nominal>
    <Name>Доллар США</Name>
    <Value>71,2090</Value>
    <VunitRate>71,209</VunitRate>
  </Valute>
  <Valute ID="R01239">
    <NumCode>978</NumCode>
    <CharCode>EUR</CharCode>
    <Nominal>1</Nominal>
    <Name>Евро</Name>
    <Value>82,5445</Value>
    <VunitRate>82,5445</VunitRate>
  </Valute>
</ValCurs>
"""
BINANCE_AR_USDT_JSON = '{"symbol":"ARUSDT","price":"2.50000000"}'


def test_parse_cbr_rates_xml_extracts_required_fiat_rates() -> None:
    from app.services.rates import parse_cbr_rates_xml

    parsed = parse_cbr_rates_xml(CBR_XML)

    assert parsed.source_date == "2026-05-23"
    assert parsed.base_rates == {
        "USD/RUB": Decimal("71.2090"),
        "EUR/RUB": Decimal("82.5445"),
    }

    with pytest.raises(ValueError, match="missing required CBR rate"):
        parse_cbr_rates_xml(
            """<?xml version="1.0" encoding="windows-1251"?>
            <ValCurs Date="23.05.2026">
              <Valute><CharCode>USD</CharCode><VunitRate>71,209</VunitRate></Valute>
            </ValCurs>
            """
        )

    with pytest.raises(ValueError, match="invalid CBR XML"):
        parse_cbr_rates_xml("<not-xml")


def test_derive_reference_rates_builds_crosses_and_stablecoin_pairs() -> None:
    from app.services.rates import derive_reference_rates

    derived = derive_reference_rates(
        {
            "USD/RUB": Decimal("92.5000"),
            "EUR/RUB": Decimal("100.2000"),
            "AR/USD": Decimal("2.50000000"),
        }
    )

    assert derived["USD/RUB"] == Decimal("92.5000")
    assert derived["EUR/RUB"] == Decimal("100.2000")
    assert derived["EUR/USD"] == Decimal("1.08324324")
    assert derived["USD/EUR"] == Decimal("0.92315369")
    assert derived["USDT/USD"] == Decimal("1.0000")
    assert derived["USDC/USD"] == Decimal("1.0000")
    assert derived["USDT/RUB"] == Decimal("92.5000")
    assert derived["USDC/RUB"] == Decimal("92.5000")
    assert derived["USDT/EUR"] == Decimal("0.92315369")
    assert derived["USDC/EUR"] == Decimal("0.92315369")
    assert derived["AR/USD"] == Decimal("2.50000000")
    assert derived["AR/USDT"] == Decimal("2.50000000")
    assert derived["AR/USDC"] == Decimal("2.50000000")
    assert derived["AR/RUB"] == Decimal("231.2500")
    assert derived["AR/EUR"] == Decimal("2.30788422")


def test_parse_binance_symbol_price_json_extracts_ar_usdt_price() -> None:
    from app.services.rates import parse_binance_symbol_price_json

    assert parse_binance_symbol_price_json(BINANCE_AR_USDT_JSON) == Decimal("2.50000000")

    with pytest.raises(ValueError, match="unexpected Binance symbol"):
        parse_binance_symbol_price_json('{"symbol":"BTCUSDT","price":"2.50000000"}')

    with pytest.raises(ValueError, match="invalid Binance ticker JSON"):
        parse_binance_symbol_price_json("{not-json")


async def test_get_rates_fetches_cbr_xml_stores_base_cross_and_stablecoin_rates(
    test_session,
    test_settings,
    fake_notification_sink,
) -> None:
    from app.services.rates import get_rates

    test_settings.rates_provider = "cbr"
    test_settings.cbr_rates_xml_url = "https://example.test/cbr.xml"
    test_settings.binance_ar_usdt_ticker_url = "https://example.test/binance/ar"

    async def fetch_remote(url: str) -> str:
        if url == "https://example.test/cbr.xml":
            return CBR_XML
        if url == "https://example.test/binance/ar":
            return BINANCE_AR_USDT_JSON
        raise AssertionError(f"unexpected rates URL: {url}")

    response = await get_rates(
        test_session,
        settings=test_settings,
        fetch_remote=fetch_remote,
        notification_sink=fake_notification_sink,
    )

    assert response.source == "cbr"
    assert response.is_stale is False
    assert {item.pair: item.rate for item in response.rates} == {
        "AR/EUR": "2.1567",
        "AR/RUB": "178.0225",
        "AR/USDC": "2.5000",
        "AR/USDT": "2.5000",
        "AR/USD": "2.5000",
        "EUR/RUB": "82.5445",
        "EUR/USD": "1.1592",
        "USDC/EUR": "0.8627",
        "USDC/RUB": "71.2090",
        "USDC/USD": "1.0000",
        "USDT/EUR": "0.8627",
        "USDT/RUB": "71.2090",
        "USDT/USD": "1.0000",
        "USD/EUR": "0.8627",
        "USD/RUB": "71.2090",
    }
    assert fake_notification_sink.intents == []

    stored = (await test_session.execute(select(Rate).order_by(Rate.pair))).scalars().all()
    assert [row.pair for row in stored] == [item.pair for item in response.rates]
    assert stored[0].rate_date.isoformat() == response.date
    assert {row.pair: f"{row.rate:.4f}" for row in stored}["USD/RUB"] == "71.2090"
    assert {row.source for row in stored} == {"binance", "cbr", "derived"}


async def test_get_rates_refreshes_incomplete_daily_cache(
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
            source="cbr",
            rate_date=today,
            fetched_at=fetched_at,
            raw_payload="cached-before-ar",
        )
    )
    await test_session.commit()

    test_settings.cbr_rates_xml_url = "https://example.test/cbr.xml"
    test_settings.binance_ar_usdt_ticker_url = "https://example.test/binance/ar"
    fetched_urls: list[str] = []

    async def fetch_remote(url: str) -> str:
        fetched_urls.append(url)
        if url == "https://example.test/cbr.xml":
            return CBR_XML
        if url == "https://example.test/binance/ar":
            return BINANCE_AR_USDT_JSON
        raise AssertionError(f"unexpected rates URL: {url}")

    response = await get_rates(
        test_session,
        settings=test_settings,
        fetch_remote=fetch_remote,
        notification_sink=fake_notification_sink,
    )

    assert fetched_urls == [
        "https://example.test/cbr.xml",
        "https://example.test/binance/ar",
    ]
    assert "AR/USD" in {item.pair for item in response.rates}


async def test_get_rates_uses_complete_daily_cache_without_fetching(
    test_session,
    test_settings,
    fake_notification_sink,
) -> None:
    from app.services.rates import derive_reference_rates, get_rates

    today = utc_now().astimezone(ZoneInfo(test_settings.rates_refresh_timezone)).date()
    fetched_at = utc_now()
    test_session.add_all(
        [
            Rate(
                pair=pair,
                rate=rate,
                source="test",
                rate_date=today,
                fetched_at=fetched_at,
                raw_payload="cached",
            )
            for pair, rate in derive_reference_rates(
                {
                    "USD/RUB": Decimal("91.2500"),
                    "EUR/RUB": Decimal("99.5000"),
                    "AR/USD": Decimal("2.50000000"),
                }
            ).items()
        ]
    )
    await test_session.commit()

    async def fetch_remote(_url: str) -> str:
        raise AssertionError("complete daily cache should avoid fetching rates")

    response = await get_rates(
        test_session,
        settings=test_settings,
        fetch_remote=fetch_remote,
        notification_sink=fake_notification_sink,
    )

    assert response.is_stale is False
    assert response.date == today.isoformat()
    assert "AR/USD" in {item.pair for item in response.rates}
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
            source="cbr",
            rate_date=historical_date,
            fetched_at=fetched_at,
            raw_payload="historical",
        )
    )
    await test_session.commit()

    async def fetch_xml(_url: str) -> str:
        raise ValueError("xml exploded")

    response = await get_rates(
        test_session,
        settings=test_settings,
        fetch_remote=fetch_xml,
        notification_sink=fake_notification_sink,
    )

    assert response.is_stale is True
    assert response.date == historical_date.isoformat()
    assert [(item.pair, item.rate) for item in response.rates] == [("USD/RUB", "90.0000")]
    assert [intent.kind for intent in fake_notification_sink.intents] == ["admin_technical"]
    assert fake_notification_sink.intents[0].payload["event"] == "rates_refresh_failed"


async def test_get_rates_does_not_commit_caller_transaction(
    test_session,
    test_settings,
    fake_notification_sink,
) -> None:
    from app.services.rates import get_rates

    test_settings.binance_ar_usdt_ticker_url = "https://example.test/binance/ar"

    async def fetch_remote(url: str) -> str:
        if url == test_settings.cbr_rates_xml_url:
            return CBR_XML
        if url == "https://example.test/binance/ar":
            return BINANCE_AR_USDT_JSON
        raise AssertionError(f"unexpected rates URL: {url}")

    await get_rates(
        test_session,
        settings=test_settings,
        fetch_remote=fetch_remote,
        notification_sink=fake_notification_sink,
    )
    await test_session.rollback()

    stored = (await test_session.execute(select(Rate))).scalars().all()
    assert stored == []


async def test_get_rates_tolerates_parallel_refresh_that_already_inserted_rows(
    test_session,
    test_settings,
    fake_notification_sink,
) -> None:
    from app.services.rates import get_rates

    today = utc_now().astimezone(ZoneInfo(test_settings.rates_refresh_timezone)).date()
    fetched_at = utc_now()

    inserted_parallel_rows = False

    async def fetch_remote(url: str) -> str:
        nonlocal inserted_parallel_rows
        if url == test_settings.cbr_rates_xml_url:
            if not inserted_parallel_rows:
                inserted_parallel_rows = True
                test_session.add_all(
                    [
                        Rate(
                            pair=pair,
                            rate=rate,
                            source="parallel",
                            rate_date=today,
                            fetched_at=fetched_at,
                            raw_payload="parallel",
                        )
                        for pair, rate in {
                            "AR/EUR": Decimal("2.15668517"),
                            "AR/RUB": Decimal("178.0225"),
                            "AR/USDC": Decimal("2.50000000"),
                            "AR/USDT": Decimal("2.50000000"),
                            "AR/USD": Decimal("2.50000000"),
                            "EUR/RUB": Decimal("82.5445"),
                            "EUR/USD": Decimal("1.15918634"),
                            "USDC/EUR": Decimal("0.86267407"),
                            "USDC/RUB": Decimal("71.2090"),
                            "USDC/USD": Decimal("1.0000"),
                            "USDT/EUR": Decimal("0.86267407"),
                            "USDT/RUB": Decimal("71.2090"),
                            "USDT/USD": Decimal("1.0000"),
                            "USD/EUR": Decimal("0.86267407"),
                            "USD/RUB": Decimal("71.2090"),
                        }.items()
                    ]
                )
                await test_session.flush()
            return CBR_XML
        return BINANCE_AR_USDT_JSON

    response = await get_rates(
        test_session,
        settings=test_settings,
        fetch_remote=fetch_remote,
        notification_sink=fake_notification_sink,
    )

    assert response.is_stale is False
    assert len(response.rates) == 15
    stored = (await test_session.execute(select(Rate))).scalars().all()
    assert len(stored) == 15


async def test_get_rates_raises_app_error_when_fetch_fails_without_saved_rates(
    test_session,
    test_settings,
    fake_notification_sink,
) -> None:
    from app.services.rates import RatesUnavailableError, get_rates

    async def fetch_xml(_url: str) -> str:
        raise ValueError("xml exploded")

    with pytest.raises(RatesUnavailableError) as exc_info:
        await get_rates(
            test_session,
            settings=test_settings,
            fetch_remote=fetch_xml,
            notification_sink=fake_notification_sink,
        )

    assert exc_info.value.code == "rates_unavailable"
    assert exc_info.value.status_code == 503
    assert [intent.kind for intent in fake_notification_sink.intents] == ["admin_technical"]


async def test_get_pair_rate_resolves_direct_inverse_and_cross_rates(
    seeded_reference_rates,
    test_session,
    test_settings,
    fake_notification_sink,
) -> None:
    from app.services.rates import get_pair_rate

    assert await get_pair_rate(
        test_session,
        settings=test_settings,
        base_currency="USD",
        quote_currency="RUB",
        notification_sink=fake_notification_sink,
    ) == Decimal("92.50000000")
    assert await get_pair_rate(
        test_session,
        settings=test_settings,
        base_currency="RUB",
        quote_currency="USD",
        notification_sink=fake_notification_sink,
    ) == Decimal("0.01081081")
    assert await get_pair_rate(
        test_session,
        settings=test_settings,
        base_currency="EUR",
        quote_currency="USDT",
        notification_sink=fake_notification_sink,
    ) == Decimal("1.08320000")
    assert await get_pair_rate(
        test_session,
        settings=test_settings,
        base_currency="AR",
        quote_currency="RUB",
        notification_sink=fake_notification_sink,
    ) == Decimal("231.25000000")
