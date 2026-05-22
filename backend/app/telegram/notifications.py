import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

from app.core.time import utc_now

logger = logging.getLogger(__name__)

NotificationRecipient = Literal["admins"]
NotificationKind = Literal["admin_auto_hide_ad", "admin_technical"]


@dataclass(frozen=True, slots=True)
class NotificationIntent:
    recipient: NotificationRecipient
    kind: NotificationKind
    payload: Mapping[str, object]
    created_at: datetime

    def as_log_payload(self) -> dict[str, object]:
        return {
            "recipient": self.recipient,
            "kind": self.kind,
            "payload": dict(self.payload),
            "created_at": self.created_at.isoformat(),
        }


class NotificationSink(Protocol):
    async def record(self, intent: NotificationIntent) -> None:
        """Record an intent for a future Telegram sender."""


class LoggingNotificationSink:
    async def record(self, intent: NotificationIntent) -> None:
        logger.info(
            "telegram notification intent recorded",
            extra={"notification_intent": intent.as_log_payload()},
        )


def get_notification_sink() -> NotificationSink:
    return LoggingNotificationSink()


async def notify_admin_auto_hide_ad(
    sink: NotificationSink,
    *,
    ad_id: int,
    report_count: int,
) -> NotificationIntent:
    return await _record_admin_intent(
        sink,
        kind="admin_auto_hide_ad",
        payload={
            "ad_id": ad_id,
            "report_count": report_count,
        },
    )


async def notify_admin_technical(
    sink: NotificationSink,
    *,
    event: str,
    message: str,
    context: Mapping[str, object] | None = None,
) -> NotificationIntent:
    payload: dict[str, object] = {
        "event": event,
        "message": message,
    }
    if context:
        payload["context"] = dict(context)
    return await _record_admin_intent(sink, kind="admin_technical", payload=payload)


async def _record_admin_intent(
    sink: NotificationSink,
    *,
    kind: NotificationKind,
    payload: Mapping[str, object],
) -> NotificationIntent:
    intent = NotificationIntent(
        recipient="admins",
        kind=kind,
        payload=dict(payload),
        created_at=utc_now(),
    )
    await sink.record(intent)
    return intent
