from datetime import UTC, datetime

from sqlalchemy import String
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator[datetime]):
    impl = String(32)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, _dialect) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("UTCDateTime requires an aware datetime")
        return value.astimezone(UTC).isoformat(timespec="microseconds")

    def process_result_value(self, value: str | None, _dialect) -> datetime | None:
        if value is None:
            return None
        return datetime.fromisoformat(value).astimezone(UTC)
