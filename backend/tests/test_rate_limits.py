from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.errors import ForbiddenError
from app.core.limits import check_rate_limit
from app.core.time import utc_now
from app.db.models import Ad, RateLimitEvent, User, UserChannelMembership


def ad_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "side": "SELL",
        "base_currency": "USD",
        "quote_currency": "RUB",
        "amount": "100.00",
        "rate": "92.50",
    }
    payload.update(overrides)
    return payload


async def create_ad(client, csrf_token: str, **overrides: object) -> int:
    response = await client.post(
        "/api/ads",
        json=ad_payload(**overrides),
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 201
    return int(response.json()["id"])


async def seed_reportable_ads(test_session, *, count: int) -> list[tuple[int, int]]:
    now = utc_now()
    pairs: list[tuple[int, int]] = []
    for index in range(count):
        user = User(
            telegram_id=9000 + index,
            username=f"author{index}",
            is_admin=False,
            is_banned=False,
            first_seen_at=now,
            last_seen_at=now,
            created_at=now,
            updated_at=now,
        )
        test_session.add(user)
        await test_session.flush()
        ad = Ad(
            user_id=user.id,
            side="SELL",
            base_currency="USD",
            quote_currency="RUB",
            amount=Decimal("100.00"),
            rate=Decimal("92.50"),
            status="ACTIVE",
            report_count=0,
            expires_at=now + timedelta(days=1),
            created_at=now,
            updated_at=now,
        )
        test_session.add(ad)
        await test_session.flush()
        pairs.append((ad.id, user.id))
    await test_session.commit()
    return pairs


async def expire_required_channel_membership(test_session, *, telegram_id: int) -> None:
    membership = (
        await test_session.execute(
            select(UserChannelMembership)
            .join(User, User.id == UserChannelMembership.user_id)
            .where(User.telegram_id == telegram_id)
        )
    ).scalar_one()
    membership.expires_at = utc_now() - timedelta(seconds=1)
    await test_session.commit()


async def test_check_rate_limit_enforces_limit(test_session) -> None:
    await check_rate_limit(
        test_session,
        key="user:1",
        action="report",
        limit=1,
        window_seconds=60,
    )

    with pytest.raises(ForbiddenError, match="rate limit exceeded"):
        await check_rate_limit(
            test_session,
            key="user:1",
            action="report",
            limit=1,
            window_seconds=60,
        )


async def test_check_rate_limit_ignores_old_window_events(test_session) -> None:
    old_event = RateLimitEvent(
        key="user:1",
        action="report",
        created_at=utc_now() - timedelta(seconds=61),
    )
    test_session.add(old_event)
    await test_session.commit()

    await check_rate_limit(
        test_session,
        key="user:1",
        action="report",
        limit=1,
        window_seconds=60,
    )
    await test_session.commit()

    events = (await test_session.execute(select(RateLimitEvent))).scalars().all()
    assert len(events) == 1
    assert events[0].created_at > old_event.created_at


async def test_auth_rate_limit_is_enforced_by_ip(client, make_init_data) -> None:
    for index in range(10):
        response = await client.post(
            "/api/auth/telegram-webapp",
            json={"init_data": make_init_data(telegram_id=8000 + index)},
        )
        assert response.status_code == 200

    response = await client.post(
        "/api/auth/telegram-webapp",
        json={"init_data": make_init_data(telegram_id=8011)},
    )

    assert response.status_code == 403
    assert response.json()["message"] == "rate limit exceeded"


async def test_create_ad_rate_limit_is_enforced_by_user(client, authenticate) -> None:
    csrf_token = await authenticate(client, telegram_id=8101, username="seller")
    for index in range(5):
        response = await client.post(
            "/api/ads",
            json=ad_payload(amount=str(100 + index)),
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 201

    response = await client.post(
        "/api/ads",
        json=ad_payload(amount="1000.00"),
        headers={"X-CSRF-Token": csrf_token},
    )

    assert response.status_code == 403
    assert response.json()["message"] == "rate limit exceeded"


async def test_update_ad_rate_limit_is_enforced_by_user(client, authenticate) -> None:
    csrf_token = await authenticate(client, telegram_id=8201, username="seller")
    ad_id = await create_ad(client, csrf_token)
    for index in range(30):
        response = await client.patch(
            f"/api/ads/{ad_id}",
            json={"comment": f"update {index}"},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

    response = await client.patch(
        f"/api/ads/{ad_id}",
        json={"comment": "blocked"},
        headers={"X-CSRF-Token": csrf_token},
    )

    assert response.status_code == 403
    assert response.json()["message"] == "rate limit exceeded"


async def test_report_rate_limit_is_enforced_by_user(
    client,
    authenticate,
    test_session,
) -> None:
    reportable_ads = await seed_reportable_ads(test_session, count=11)
    csrf_token = await authenticate(client, telegram_id=8301, username="reporter")
    for ad_id, target_user_id in reportable_ads[:10]:
        response = await client.post(
            "/api/reports",
            json={"ad_id": ad_id, "target_user_id": target_user_id, "reason": "SCAM"},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

    blocked_ad_id, blocked_target_id = reportable_ads[10]
    response = await client.post(
        "/api/reports",
        json={"ad_id": blocked_ad_id, "target_user_id": blocked_target_id, "reason": "SCAM"},
        headers={"X-CSRF-Token": csrf_token},
    )

    assert response.status_code == 403
    assert response.json()["message"] == "rate limit exceeded"


async def test_required_channel_check_rate_limit_is_enforced_by_user(
    client_with_required_channel,
    authenticate,
    test_session,
) -> None:
    await authenticate(client_with_required_channel, telegram_id=8401, username="member")

    for _ in range(9):
        await expire_required_channel_membership(test_session, telegram_id=8401)
        response = await client_with_required_channel.get("/api/auth/me")
        assert response.status_code == 200

    await expire_required_channel_membership(test_session, telegram_id=8401)
    response = await client_with_required_channel.get("/api/auth/me")

    assert response.status_code == 403
    assert response.json()["message"] == "rate limit exceeded"
