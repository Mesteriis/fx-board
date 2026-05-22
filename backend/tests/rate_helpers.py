from decimal import Decimal
from zoneinfo import ZoneInfo

from app.core.config import Settings
from app.core.time import utc_now
from app.db.models import Rate


async def seed_reference_rates_in_session(session, settings: Settings) -> None:
    today = utc_now().astimezone(ZoneInfo(settings.rates_refresh_timezone)).date()
    fetched_at = utc_now()
    session.add_all(
        [
            Rate(
                pair=pair,
                rate=rate,
                source="test",
                rate_date=today,
                fetched_at=fetched_at,
                raw_payload="test",
            )
            for pair, rate in {
                "EUR/RUB": Decimal("100.2000"),
                "EUR/USD": Decimal("1.0832"),
                "AR/EUR": Decimal("2.30788423"),
                "AR/RUB": Decimal("231.2500"),
                "AR/USDC": Decimal("2.50000000"),
                "AR/USDT": Decimal("2.50000000"),
                "AR/USD": Decimal("2.50000000"),
                "USDC/EUR": Decimal("0.9232"),
                "USDC/RUB": Decimal("92.5000"),
                "USDC/USD": Decimal("1.0000"),
                "USDT/EUR": Decimal("0.9232"),
                "USDT/RUB": Decimal("92.5000"),
                "USDT/USD": Decimal("1.0000"),
                "USD/EUR": Decimal("0.9232"),
                "USD/RUB": Decimal("92.5000"),
            }.items()
        ]
    )
    await session.commit()
