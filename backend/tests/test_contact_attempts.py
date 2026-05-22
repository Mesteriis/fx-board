from datetime import timedelta

from sqlalchemy import select

from app.core.time import utc_now
from app.db.models import Ad, ContactAttempt, User, UserChannelMembership


def ad_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "side": "sell",
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


async def test_contact_rejects_self_contact(client, authenticate) -> None:
    csrf_token = await authenticate(client, telegram_id=5001, username="author")
    ad_id = await create_ad(client, csrf_token)

    response = await client.post(
        f"/api/ads/{ad_id}/contact",
        headers={"X-CSRF-Token": csrf_token},
    )

    assert response.status_code == 403
    assert response.json()["message"] == "cannot contact your own ad"


async def test_contact_rejects_unavailable_author_username(
    client,
    authenticate,
    test_session,
) -> None:
    author_csrf = await authenticate(client, telegram_id=5002, username="author")
    ad_id = await create_ad(client, author_csrf)
    author = (await test_session.execute(select(User).where(User.telegram_id == 5002))).scalar_one()
    author.username = None
    await test_session.commit()

    initiator_csrf = await authenticate(client, telegram_id=5003, username="initiator")
    response = await client.post(
        f"/api/ads/{ad_id}/contact",
        headers={"X-CSRF-Token": initiator_csrf},
    )

    assert response.status_code == 403
    assert response.json()["message"] == "contact unavailable"


async def test_contact_creates_attempt_and_returns_telegram_url(
    client,
    authenticate,
    test_session,
    test_settings,
) -> None:
    test_settings.deal_followup_delay_hours = 3
    author_csrf = await authenticate(client, telegram_id=5004, username="author_name")
    ad_id = await create_ad(client, author_csrf)

    initiator_csrf = await authenticate(client, telegram_id=5005, username="initiator")
    before = utc_now()
    response = await client.post(
        f"/api/ads/{ad_id}/contact",
        headers={"X-CSRF-Token": initiator_csrf},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["telegram_url"] == "https://t.me/author_name"
    attempt = await test_session.get(ContactAttempt, body["contact_attempt_id"])
    assert attempt is not None
    assert attempt.status == "OPENED"
    assert attempt.ad_id == ad_id
    assert attempt.followup_due_at >= before + timedelta(hours=3)


async def test_contact_rejects_missing_and_invalid_csrf(client, authenticate) -> None:
    author_csrf = await authenticate(client, telegram_id=5101, username="author")
    ad_id = await create_ad(client, author_csrf)

    await authenticate(client, telegram_id=5102, username="initiator")
    missing_response = await client.post(f"/api/ads/{ad_id}/contact")
    invalid_response = await client.post(
        f"/api/ads/{ad_id}/contact",
        headers={"X-CSRF-Token": "invalid"},
    )

    assert missing_response.status_code == 403
    assert missing_response.json()["message"] == "invalid csrf token"
    assert invalid_response.status_code == 403
    assert invalid_response.json()["message"] == "invalid csrf token"


async def test_required_channel_denies_contact(
    client_with_required_channel,
    fake_telegram_client,
    authenticate,
    test_session,
) -> None:
    author_csrf = await authenticate(
        client_with_required_channel,
        telegram_id=5103,
        username="author",
    )
    ad_id = await create_ad(client_with_required_channel, author_csrf)
    initiator_csrf = await authenticate(
        client_with_required_channel,
        telegram_id=5104,
        username="initiator",
    )
    await expire_required_channel_membership(test_session, telegram_id=5104)
    fake_telegram_client.status_by_chat_id["@required"] = "left"

    response = await client_with_required_channel.post(
        f"/api/ads/{ad_id}/contact",
        headers={"X-CSRF-Token": initiator_csrf},
    )

    assert response.status_code == 403
    assert response.json()["message"] == "required channel membership missing"


async def test_new_contact_cancels_prior_pending_followup(
    client,
    authenticate,
    test_session,
) -> None:
    first_author_csrf = await authenticate(client, telegram_id=5006, username="first_author")
    first_ad_id = await create_ad(client, first_author_csrf)

    second_author_csrf = await authenticate(client, telegram_id=5007, username="second_author")
    second_ad_id = await create_ad(
        client,
        second_author_csrf,
        base_currency="EUR",
        quote_currency="USD",
    )

    initiator_csrf = await authenticate(client, telegram_id=5008, username="initiator")
    first_contact = await client.post(
        f"/api/ads/{first_ad_id}/contact",
        headers={"X-CSRF-Token": initiator_csrf},
    )
    assert first_contact.status_code == 201

    second_contact = await client.post(
        f"/api/ads/{second_ad_id}/contact",
        headers={"X-CSRF-Token": initiator_csrf},
    )

    assert second_contact.status_code == 201
    attempts = (
        await test_session.execute(select(ContactAttempt).order_by(ContactAttempt.id))
    ).scalars().all()
    assert [attempt.status for attempt in attempts] == ["CANCELED_BY_NEW_CONTACT", "OPENED"]
    assert attempts[0].updated_at <= attempts[1].created_at


async def test_contact_cancels_previous_opened_attempt_for_same_initiator_and_ad(
    client,
    authenticate,
    test_session,
) -> None:
    author_csrf = await authenticate(client, telegram_id=5009, username="author")
    ad_id = await create_ad(client, author_csrf)

    initiator_csrf = await authenticate(client, telegram_id=5010, username="initiator")
    first_contact = await client.post(
        f"/api/ads/{ad_id}/contact",
        headers={"X-CSRF-Token": initiator_csrf},
    )
    second_contact = await client.post(
        f"/api/ads/{ad_id}/contact",
        headers={"X-CSRF-Token": initiator_csrf},
    )

    assert first_contact.status_code == 201
    assert second_contact.status_code == 201
    attempts = (
        await test_session.execute(select(ContactAttempt).order_by(ContactAttempt.id))
    ).scalars().all()
    assert [attempt.status for attempt in attempts] == ["CANCELED_BY_NEW_CONTACT", "OPENED"]


async def test_contact_rejects_non_active_ad(client, authenticate, test_session) -> None:
    author_csrf = await authenticate(client, telegram_id=5011, username="author")
    ad_id = await create_ad(client, author_csrf)
    ad = await test_session.get(Ad, ad_id)
    assert ad is not None
    ad.status = "REVOKED"
    await test_session.commit()

    initiator_csrf = await authenticate(client, telegram_id=5012, username="initiator")
    response = await client.post(
        f"/api/ads/{ad_id}/contact",
        headers={"X-CSRF-Token": initiator_csrf},
    )

    assert response.status_code == 404


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
