import csv
import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from io import StringIO
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
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

RATE_RESPONSE_SOURCE = "googlefinance"
FOUR_DECIMALS = Decimal("0.0001")
EXPECTED_COLUMNS = {"pair", "rate", "source", "updated_at"}

RateCsvFetcher = Callable[[str], Awaitable[str]]


class RatesUnavailableError(AppError):
    status_code = 503
    code = "rates_unavailable"


@dataclass(frozen=True, slots=True)
class ParsedRate:
    pair: str
    rate: Decimal
    source: str
    updated_at: str

    @property
    def normalized_rate(self) -> str:
        return _format_rate(self.rate)


def parse_rates_csv(csv_text: str) -> dict[str, str]:
    return {
        pair: parsed_rate.normalized_rate
        for pair, parsed_rate in _parse_rates_csv_rows(csv_text).items()
    }


def derive_stablecoin_rates(base_rates: Mapping[str, str]) -> dict[str, str]:
    derived = {
        "USDT/USD": "1.0000",
        "USDC/USD": "1.0000",
    }
    if "USD/RUB" in base_rates:
        derived["USDT/RUB"] = base_rates["USD/RUB"]
        derived["USDC/RUB"] = base_rates["USD/RUB"]
    if "USD/EUR" in base_rates:
        derived["USDT/EUR"] = base_rates["USD/EUR"]
        derived["USDC/EUR"] = base_rates["USD/EUR"]
    return derived


async def fetch_rates_csv(url: str) -> str:
    if not url.strip():
        raise ValueError("google rates csv url is not configured")

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text


async def get_rates(
    db: AsyncSession,
    *,
    settings: Settings,
    fetch_csv: RateCsvFetcher | None = None,
    notification_sink: NotificationSink | None = None,
) -> RatesResponse:
    today = utc_now().astimezone(ZoneInfo(settings.rates_refresh_timezone)).date()
    today_rows = await _rates_for_date(db, today)
    if today_rows:
        return _rates_response(today_rows, rate_date=today, is_stale=False)

    fetcher = fetch_csv or fetch_rates_csv
    try:
        csv_text = await fetcher(settings.google_rates_csv_url)
        parsed_rows = _parse_rates_csv_rows(csv_text)
        parsed_rates = {pair: row.normalized_rate for pair, row in parsed_rows.items()}
        all_rates = {**parsed_rates, **derive_stablecoin_rates(parsed_rates)}
        now = utc_now()
        for pair, rate in sorted(all_rates.items()):
            source = parsed_rows[pair].source if pair in parsed_rows else "derived_stablecoin"
            db.add(
                Rate(
                    pair=pair,
                    rate=Decimal(rate),
                    source=source,
                    rate_date=today,
                    fetched_at=now,
                    raw_payload=csv_text,
                )
            )
        await db.flush()
        return _rates_response(await _rates_for_date(db, today), rate_date=today, is_stale=False)
    except (httpx.HTTPError, ValueError) as exc:
        return await _stale_rates_response(
            db,
            notification_sink=notification_sink,
            cause=exc,
        )


def _parse_rates_csv_rows(csv_text: str) -> dict[str, ParsedRate]:
    reader = csv.DictReader(StringIO(csv_text))
    if reader.fieldnames is None or EXPECTED_COLUMNS - set(reader.fieldnames):
        raise ValueError("rates csv has invalid columns")

    rates: dict[str, ParsedRate] = {}
    for row in reader:
        pair = (row.get("pair") or "").strip().upper()
        if not pair:
            raise ValueError("rates csv has empty pair")
        if pair in rates:
            raise ValueError(f"duplicate rate for {pair}")

        raw_rate = (row.get("rate") or "").strip()
        try:
            rate = _parse_positive_rate(raw_rate)
        except ValueError as exc:
            raise ValueError(f"invalid rate for {pair}") from exc

        source = (row.get("source") or "").strip()
        if not source:
            raise ValueError(f"missing source for {pair}")
        updated_at = (row.get("updated_at") or "").strip()
        if not updated_at:
            raise ValueError(f"missing updated_at for {pair}")

        rates[pair] = ParsedRate(
            pair=pair,
            rate=rate,
            source=source,
            updated_at=updated_at,
        )
    return rates


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


def _rates_response(rows: list[Rate], *, rate_date, is_stale: bool) -> RatesResponse:
    updated_at = max(row.fetched_at for row in rows)
    return RatesResponse(
        date=rate_date.isoformat(),
        source=RATE_RESPONSE_SOURCE,
        is_stale=is_stale,
        updated_at=updated_at.isoformat(),
        rates=[RateItem(pair=row.pair, rate=_format_rate(row.rate)) for row in rows],
    )


def _format_rate(rate: Decimal) -> str:
    try:
        return f"{rate.quantize(FOUR_DECIMALS):.4f}"
    except InvalidOperation as exc:
        raise ValueError("invalid rate precision") from exc


def _parse_positive_rate(raw_rate: str) -> Decimal:
    try:
        rate = Decimal(raw_rate)
    except InvalidOperation as exc:
        raise ValueError("invalid decimal") from exc
    if not rate.is_finite():
        raise ValueError("rate must be finite")
    if rate <= 0:
        raise ValueError("rate must be positive")
    try:
        rate.quantize(FOUR_DECIMALS)
    except InvalidOperation as exc:
        raise ValueError("invalid decimal precision") from exc
    return rate
