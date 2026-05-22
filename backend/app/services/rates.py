import json
import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.core.time import utc_now
from app.db.models import Rate
from app.schemas.rates import RateItem, RatesResponse
from app.telegram.notifications import (
    NotificationSink,
    get_notification_sink,
    notify_admin_technical,
)

logger = logging.getLogger(__name__)

CBR_SOURCE = "cbr"
EXCHANGE_RATE_API_SOURCE = "exchange_rate_api"
BINANCE_SOURCE = "binance"
DERIVED_SOURCE = "derived"
FOUR_DECIMALS = Decimal("0.0001")
EIGHT_DECIMALS = Decimal("0.00000001")
REQUIRED_CBR_CODES = {"USD", "EUR"}
USD_PEGGED_CURRENCIES = {"USD", "USDT", "USDC"}
EXPECTED_BINANCE_AR_USDT_SYMBOL = "ARUSDT"
REQUIRED_RESPONSE_RATE_PAIRS = frozenset(
    {
        "AR/EUR",
        "AR/RUB",
        "AR/USDC",
        "AR/USDT",
        "AR/USD",
        "EUR/RUB",
        "EUR/USD",
        "USDC/EUR",
        "USDC/RUB",
        "USDC/USD",
        "USDT/EUR",
        "USDT/RUB",
        "USDT/USD",
        "USD/EUR",
        "USD/RUB",
    }
)

RemoteRatesFetcher = Callable[[str], Awaitable[str]]


class RatesUnavailableError(AppError):
    status_code = 503
    code = "rates_unavailable"


@dataclass(frozen=True, slots=True)
class ParsedCbrRates:
    source_date: str
    base_rates: dict[str, Decimal]


@dataclass(frozen=True, slots=True)
class ParsedExchangeRateApiRates:
    source_date: str
    base_rates: dict[str, Decimal]


def parse_cbr_rates_xml(xml_text: str) -> ParsedCbrRates:
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as exc:
        raise ValueError("invalid CBR XML") from exc

    raw_source_date = root.attrib.get("Date")
    if not raw_source_date:
        raise ValueError("invalid CBR XML: missing Date")
    try:
        source_date = datetime.strptime(raw_source_date, "%d.%m.%Y").date().isoformat()
    except ValueError as exc:
        raise ValueError("invalid CBR XML: invalid Date") from exc

    base_rates: dict[str, Decimal] = {}
    for valute in root.findall("Valute"):
        char_code = (valute.findtext("CharCode") or "").strip().upper()
        if char_code not in REQUIRED_CBR_CODES:
            continue
        base_rates[f"{char_code}/RUB"] = _parse_cbr_unit_rate(valute)

    missing_codes = sorted(
        code for code in REQUIRED_CBR_CODES if f"{code}/RUB" not in base_rates
    )
    if missing_codes:
        raise ValueError(f"missing required CBR rate: {', '.join(missing_codes)}")

    return ParsedCbrRates(source_date=source_date, base_rates=base_rates)


def parse_exchange_rate_api_usd_json(json_text: str) -> ParsedExchangeRateApiRates:
    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid ExchangeRate API JSON") from exc

    if not isinstance(payload, dict):
        raise ValueError("invalid ExchangeRate API JSON")
    if str(payload.get("base_code") or payload.get("base") or "").upper() != "USD":
        raise ValueError("ExchangeRate API response must use USD base")

    rates = payload.get("rates")
    if not isinstance(rates, dict):
        raise ValueError("invalid ExchangeRate API JSON: missing rates")

    try:
        usd_rub = _parse_positive_decimal(str(rates["RUB"]))
        usd_eur = _parse_positive_decimal(str(rates["EUR"]))
    except KeyError as exc:
        raise ValueError("missing required ExchangeRate API rate") from exc

    source_date = str(
        payload.get("time_last_update_utc")
        or payload.get("date")
        or utc_now().date().isoformat()
    )
    return ParsedExchangeRateApiRates(
        source_date=source_date,
        base_rates={
            "USD/RUB": usd_rub,
            "EUR/RUB": _quantize_eight(usd_rub / usd_eur),
        },
    )


def derive_reference_rates(base_rates: Mapping[str, Decimal]) -> dict[str, Decimal]:
    usd_rub = _require_rate(base_rates, "USD/RUB")
    eur_rub = _require_rate(base_rates, "EUR/RUB")
    ar_usd = _require_rate(base_rates, "AR/USD")

    usd_eur = _quantize_eight(usd_rub / eur_rub)
    eur_usd = _quantize_eight(eur_rub / usd_rub)
    ar_usd = _quantize_eight(ar_usd)

    return {
        "AR/EUR": _quantize_eight(ar_usd * usd_eur),
        "AR/RUB": _quantize_four(ar_usd * usd_rub),
        "AR/USDC": ar_usd,
        "AR/USDT": ar_usd,
        "AR/USD": ar_usd,
        "EUR/RUB": _quantize_four(eur_rub),
        "EUR/USD": eur_usd,
        "USDC/EUR": usd_eur,
        "USDC/RUB": _quantize_four(usd_rub),
        "USDC/USD": Decimal("1.0000"),
        "USDT/EUR": usd_eur,
        "USDT/RUB": _quantize_four(usd_rub),
        "USDT/USD": Decimal("1.0000"),
        "USD/EUR": usd_eur,
        "USD/RUB": _quantize_four(usd_rub),
    }


def parse_binance_symbol_price_json(json_text: str) -> Decimal:
    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid Binance ticker JSON") from exc

    if not isinstance(payload, dict):
        raise ValueError("invalid Binance ticker JSON")

    symbol = str(payload.get("symbol", "")).upper()
    if symbol != EXPECTED_BINANCE_AR_USDT_SYMBOL:
        raise ValueError("unexpected Binance symbol")

    raw_price = payload.get("price")
    if raw_price is None:
        raise ValueError("invalid Binance ticker JSON: missing price")
    return _parse_positive_decimal(str(raw_price))


async def fetch_rates_remote(url: str) -> str:
    if not url.strip():
        raise ValueError("rates source url is not configured")

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text


async def get_rates(
    db: AsyncSession,
    *,
    settings: Settings,
    fetch_remote: RemoteRatesFetcher | None = None,
    notification_sink: NotificationSink | None = None,
) -> RatesResponse:
    today = utc_now().astimezone(_rates_timezone(settings)).date()
    today_rows = await _rates_for_date(db, today)
    if _rates_cache_complete(today_rows):
        return _rates_response(today_rows, rate_date=today, is_stale=False)

    fetcher = fetch_remote or fetch_rates_remote
    try:
        fiat_rates, fiat_source, fiat_raw_payload = await _fetch_fiat_rates(
            settings,
            fetcher,
        )
        ar_usdt_json_text = await fetcher(settings.binance_ar_usdt_ticker_url)
        all_rates = derive_reference_rates(
            {
                **fiat_rates,
                "AR/USD": parse_binance_symbol_price_json(ar_usdt_json_text),
            }
        )
        now = utc_now()
        raw_payload = json.dumps(
            {
                **fiat_raw_payload,
                "binance_ar_usdt": ar_usdt_json_text,
            },
            ensure_ascii=False,
        )
        insert_statement = postgresql_insert(Rate).values(
            [
                {
                    "pair": pair,
                    "rate": rate,
                    "source": _source_for_pair(pair, fiat_rates, fiat_source),
                    "rate_date": today,
                    "fetched_at": now,
                    "raw_payload": raw_payload,
                }
                for pair, rate in sorted(all_rates.items())
            ]
        )
        await db.execute(
            insert_statement.on_conflict_do_update(
                index_elements=["pair", "rate_date"],
                set_={
                    "rate": insert_statement.excluded.rate,
                    "source": insert_statement.excluded.source,
                    "fetched_at": insert_statement.excluded.fetched_at,
                    "raw_payload": insert_statement.excluded.raw_payload,
                },
            )
        )
        return _rates_response(await _rates_for_date(db, today), rate_date=today, is_stale=False)
    except (httpx.HTTPError, ValueError) as exc:
        return await _stale_rates_response(
            db,
            notification_sink=notification_sink,
            cause=exc,
        )


async def get_pair_rate(
    db: AsyncSession,
    *,
    settings: Settings,
    base_currency: str,
    quote_currency: str,
    fetch_remote: RemoteRatesFetcher | None = None,
    notification_sink: NotificationSink | None = None,
) -> Decimal:
    response = await get_rates(
        db,
        settings=settings,
        fetch_remote=fetch_remote,
        notification_sink=notification_sink,
    )
    rates = {item.pair: Decimal(item.rate) for item in response.rates}
    return resolve_pair_rate(
        rates,
        base_currency=base_currency,
        quote_currency=quote_currency,
    )


def resolve_pair_rate(
    rates: Mapping[str, Decimal],
    *,
    base_currency: str,
    quote_currency: str,
) -> Decimal:
    if base_currency == quote_currency:
        raise RatesUnavailableError("rate for pair unavailable")

    direct_pair = f"{base_currency}/{quote_currency}"
    if direct_pair in rates:
        return _quantize_eight(rates[direct_pair])

    base_usd = _currency_to_usd(rates, base_currency)
    quote_usd = _currency_to_usd(rates, quote_currency)
    if base_usd is not None and quote_usd is not None:
        return _quantize_eight(base_usd / quote_usd)

    reverse_pair = f"{quote_currency}/{base_currency}"
    if reverse_pair in rates:
        return _quantize_eight(Decimal("1") / rates[reverse_pair])

    raise RatesUnavailableError("rate for pair unavailable")


async def _fetch_fiat_rates(
    settings: Settings,
    fetcher: RemoteRatesFetcher,
) -> tuple[dict[str, Decimal], str, dict[str, str]]:
    if settings.rates_provider == CBR_SOURCE:
        xml_text = await fetcher(settings.cbr_rates_xml_url)
        parsed = parse_cbr_rates_xml(xml_text)
        return parsed.base_rates, CBR_SOURCE, {"cbr_xml": xml_text}

    if settings.rates_provider == EXCHANGE_RATE_API_SOURCE:
        json_text = await fetcher(settings.exchange_rate_api_usd_url)
        parsed = parse_exchange_rate_api_usd_json(json_text)
        return parsed.base_rates, EXCHANGE_RATE_API_SOURCE, {"exchange_rate_api_usd": json_text}

    raise ValueError(f"unsupported rates provider: {settings.rates_provider}")


def _parse_cbr_unit_rate(valute: ElementTree.Element) -> Decimal:
    unit_rate = (valute.findtext("VunitRate") or "").strip()
    if unit_rate:
        return _parse_positive_decimal(unit_rate.replace(",", "."))

    raw_value = (valute.findtext("Value") or "").strip()
    raw_nominal = (valute.findtext("Nominal") or "").strip()
    if not raw_value or not raw_nominal:
        raise ValueError("invalid CBR XML: missing rate value")
    value = _parse_positive_decimal(raw_value.replace(",", "."))
    nominal = _parse_positive_decimal(raw_nominal.replace(",", "."))
    return _quantize_eight(value / nominal)


def _currency_to_usd(rates: Mapping[str, Decimal], currency: str) -> Decimal | None:
    if currency in USD_PEGGED_CURRENCIES:
        return Decimal("1")
    direct_pair = f"{currency}/USD"
    if direct_pair in rates:
        return rates[direct_pair]
    reverse_pair = f"USD/{currency}"
    if reverse_pair in rates:
        return _quantize_eight(Decimal("1") / rates[reverse_pair])
    return None


async def _stale_rates_response(
    db: AsyncSession,
    *,
    notification_sink: NotificationSink | None,
    cause: Exception,
) -> RatesResponse:
    await _notify_rates_refresh_failed(notification_sink, cause=cause)
    latest_date = await db.scalar(select(Rate.rate_date).order_by(Rate.rate_date.desc()).limit(1))
    if latest_date is None:
        raise RatesUnavailableError("rates unavailable") from cause
    return _rates_response(
        await _rates_for_date(db, latest_date),
        rate_date=latest_date,
        is_stale=True,
    )


async def _notify_rates_refresh_failed(
    notification_sink: NotificationSink | None,
    *,
    cause: Exception,
) -> None:
    sink = notification_sink or get_notification_sink()
    try:
        await notify_admin_technical(
            sink,
            event="rates_refresh_failed",
            message="rates refresh failed",
            context={
                "error_type": type(cause).__name__,
                "error": str(cause),
            },
        )
    except Exception:
        logger.exception("failed to record rates refresh admin notification intent")


async def _rates_for_date(db: AsyncSession, rate_date) -> list[Rate]:
    result = await db.scalars(select(Rate).where(Rate.rate_date == rate_date).order_by(Rate.pair))
    return list(result)


def _rates_cache_complete(rows: list[Rate]) -> bool:
    return REQUIRED_RESPONSE_RATE_PAIRS.issubset({row.pair for row in rows})


def _source_for_pair(pair: str, fiat_pairs: Mapping[str, Decimal], fiat_source: str) -> str:
    if pair in fiat_pairs:
        return fiat_source
    if pair == "AR/USD":
        return BINANCE_SOURCE
    return DERIVED_SOURCE


def _rates_response(rows: list[Rate], *, rate_date, is_stale: bool) -> RatesResponse:
    updated_at = max(row.fetched_at for row in rows)
    return RatesResponse(
        date=rate_date.isoformat(),
        source=_response_source_for_rows(rows),
        is_stale=is_stale,
        updated_at=updated_at.isoformat(),
        rates=[RateItem(pair=row.pair, rate=_format_rate(row.rate)) for row in rows],
    )


def _response_source_for_rows(rows: list[Rate]) -> str:
    sources = {row.source for row in rows}
    if EXCHANGE_RATE_API_SOURCE in sources:
        return EXCHANGE_RATE_API_SOURCE
    if CBR_SOURCE in sources:
        return CBR_SOURCE
    return DERIVED_SOURCE


def _rates_timezone(settings: Settings):
    from zoneinfo import ZoneInfo

    return ZoneInfo(settings.rates_refresh_timezone)


def _require_rate(rates: Mapping[str, Decimal], pair: str) -> Decimal:
    rate = rates.get(pair)
    if rate is None:
        raise ValueError(f"missing required rate: {pair}")
    return rate


def _format_rate(rate: Decimal) -> str:
    try:
        return f"{rate.quantize(FOUR_DECIMALS):.4f}"
    except InvalidOperation as exc:
        raise ValueError("invalid rate precision") from exc


def _quantize_four(rate: Decimal) -> Decimal:
    try:
        return rate.quantize(FOUR_DECIMALS)
    except InvalidOperation as exc:
        raise ValueError("invalid rate precision") from exc


def _quantize_eight(rate: Decimal) -> Decimal:
    try:
        return rate.quantize(EIGHT_DECIMALS)
    except InvalidOperation as exc:
        raise ValueError("invalid rate precision") from exc


def _parse_positive_decimal(raw_value: str) -> Decimal:
    try:
        value = Decimal(raw_value)
    except InvalidOperation as exc:
        raise ValueError("invalid decimal") from exc
    if not value.is_finite():
        raise ValueError("rate must be finite")
    if value <= 0:
        raise ValueError("rate must be positive")
    return value
