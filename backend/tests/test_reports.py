from datetime import timedelta

from sqlalchemy import select

from app.core.time import utc_now
from app.db.models import Ad, AuditLog, Report, User, UserChannelMembership


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


async def user_id_for_telegram_id(test_session, telegram_id: int) -> int:
    user = (
        await test_session.execute(select(User).where(User.telegram_id == telegram_id))
    ).scalar_one()
    return int(user.id)


async def test_user_cannot_report_self(client, authenticate, test_session) -> None:
    csrf_token = await authenticate(client, telegram_id=6001, username="author")
    ad_id = await create_ad(client, csrf_token)
    author_id = await user_id_for_telegram_id(test_session, 6001)

    response = await client.post(
        "/api/reports",
        json={"ad_id": ad_id, "target_user_id": author_id, "reason": "SCAM"},
        headers={"X-CSRF-Token": csrf_token},
    )

    assert response.status_code == 400
    assert response.json()["message"] == "cannot report yourself"
    reports = (await test_session.execute(select(Report))).scalars().all()
    assert reports == []


async def test_report_rejects_target_that_does_not_match_ad_author(
    client,
    authenticate,
    test_session,
) -> None:
    author_csrf = await authenticate(client, telegram_id=6011, username="author")
    ad_id = await create_ad(client, author_csrf)
    await authenticate(client, telegram_id=6012, username="other")
    other_user_id = await user_id_for_telegram_id(test_session, 6012)
    reporter_csrf = await authenticate(client, telegram_id=6013, username="reporter")

    response = await client.post(
        "/api/reports",
        json={"ad_id": ad_id, "target_user_id": other_user_id, "reason": "SCAM"},
        headers={"X-CSRF-Token": reporter_csrf},
    )

    assert response.status_code == 400
    assert response.json()["message"] == "target_user_id does not match ad author"


async def test_report_rejects_duplicate_ad_report_without_database_error(
    client,
    authenticate,
    test_session,
) -> None:
    author_csrf = await authenticate(client, telegram_id=6021, username="author")
    ad_id = await create_ad(client, author_csrf)
    author_id = await user_id_for_telegram_id(test_session, 6021)
    reporter_csrf = await authenticate(client, telegram_id=6022, username="reporter")

    first_response = await client.post(
        "/api/reports",
        json={"ad_id": ad_id, "target_user_id": author_id, "reason": "SCAM"},
        headers={"X-CSRF-Token": reporter_csrf},
    )
    second_response = await client.post(
        "/api/reports",
        json={"ad_id": ad_id, "target_user_id": author_id, "reason": "SCAM"},
        headers={"X-CSRF-Token": reporter_csrf},
    )

    assert first_response.status_code == 200
    assert first_response.json()["status"] == "NEW"
    assert second_response.status_code == 400
    assert second_response.json()["message"] == "ad already reported"
    reports = (await test_session.execute(select(Report))).scalars().all()
    assert len(reports) == 1


async def test_three_unique_reports_hide_ad_and_write_audit_log(
    client,
    authenticate,
    test_session,
    test_settings,
) -> None:
    test_settings.reports_to_auto_hide = 3
    author_csrf = await authenticate(client, telegram_id=6031, username="author")
    ad_id = await create_ad(client, author_csrf)
    author_id = await user_id_for_telegram_id(test_session, 6031)

    for offset in range(3):
        reporter_csrf = await authenticate(
            client,
            telegram_id=6040 + offset,
            username=f"reporter{offset}",
        )
        response = await client.post(
            "/api/reports",
            json={"ad_id": ad_id, "target_user_id": author_id, "reason": "SCAM"},
            headers={"X-CSRF-Token": reporter_csrf},
        )
        assert response.status_code == 200

    ad = await test_session.get(Ad, ad_id)
    assert ad is not None
    assert ad.status == "HIDDEN"
    assert ad.report_count == 3
    assert ad.hidden_at is not None
    audit_log = (await test_session.execute(select(AuditLog))).scalars().all()
    assert [(entry.action, entry.entity_type, entry.entity_id) for entry in audit_log] == [
        ("auto_hide_ad", "ad", ad_id)
    ]

    response = await client.get(f"/api/ads/{ad_id}")
    assert response.status_code == 404


async def test_report_requires_csrf(client, authenticate, test_session) -> None:
    author_csrf = await authenticate(client, telegram_id=6051, username="author")
    ad_id = await create_ad(client, author_csrf)
    author_id = await user_id_for_telegram_id(test_session, 6051)
    await authenticate(client, telegram_id=6052, username="reporter")

    response = await client.post(
        "/api/reports",
        json={"ad_id": ad_id, "target_user_id": author_id, "reason": "SCAM"},
    )

    assert response.status_code == 403
    assert response.json()["message"] == "invalid csrf token"


async def test_invalid_csrf_does_not_check_required_channel_on_report(
    client_with_required_channel,
    fake_telegram_client,
    authenticate,
    test_session,
) -> None:
    author_csrf = await authenticate(
        client_with_required_channel,
        telegram_id=6053,
        username="author",
    )
    ad_id = await create_ad(client_with_required_channel, author_csrf)
    author_id = await user_id_for_telegram_id(test_session, 6053)
    await authenticate(
        client_with_required_channel,
        telegram_id=6054,
        username="reporter",
    )
    membership = (
        await test_session.execute(
            select(UserChannelMembership)
            .join(User, User.id == UserChannelMembership.user_id)
            .where(User.telegram_id == 6054)
        )
    ).scalar_one()
    membership.expires_at = utc_now() - timedelta(seconds=1)
    await test_session.commit()
    fake_telegram_client.status_by_chat_id["@required"] = "left"
    call_count = len(fake_telegram_client.calls)

    response = await client_with_required_channel.post(
        "/api/reports",
        json={"ad_id": ad_id, "target_user_id": author_id, "reason": "SCAM"},
        headers={"X-CSRF-Token": "invalid"},
    )

    assert response.status_code == 403
    assert response.json()["message"] == "invalid csrf token"
    assert len(fake_telegram_client.calls) == call_count


async def test_required_channel_denies_report(
    client_with_required_channel,
    fake_telegram_client,
    authenticate,
    test_session,
) -> None:
    author_csrf = await authenticate(
        client_with_required_channel,
        telegram_id=6061,
        username="author",
    )
    ad_id = await create_ad(client_with_required_channel, author_csrf)
    author_id = await user_id_for_telegram_id(test_session, 6061)
    reporter_csrf = await authenticate(
        client_with_required_channel,
        telegram_id=6062,
        username="reporter",
    )
    membership = (
        await test_session.execute(
            select(UserChannelMembership)
            .join(User, User.id == UserChannelMembership.user_id)
            .where(User.telegram_id == 6062)
        )
    ).scalar_one()
    membership.expires_at = utc_now() - timedelta(seconds=1)
    await test_session.commit()
    fake_telegram_client.status_by_chat_id["@required"] = "left"

    response = await client_with_required_channel.post(
        "/api/reports",
        json={"ad_id": ad_id, "target_user_id": author_id, "reason": "SCAM"},
        headers={"X-CSRF-Token": reporter_csrf},
    )

    assert response.status_code == 403
    assert response.json()["message"] == "required channel membership missing"
    reports = (await test_session.execute(select(Report))).scalars().all()
    assert reports == []
