import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.db.models import AuditLog


async def write_audit(
    db: AsyncSession,
    *,
    actor_user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | None,
    payload: dict[str, object],
    ip_hash: str | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            payload_json=json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
            ip_hash=ip_hash,
            created_at=utc_now(),
        )
    )
