from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.time import utc_now
from app.db.models import Ad, ContactAttempt, User, UserChannelMembership


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


def internal_headers(test_settings) -> dict[str, str]:
    return {
        "X-Internal-Bot-Secret": (
            test_settings.telegram_internal_bot_secret.get_secret_value()
        )
    }


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


async def test_invalid_csrf_does_not_check_required_channel_on_contact(
    client_with_required_channel,
    fake_telegram_client,
    authenticate,
    test_session,
) -> None:
    author_csrf = await authenticate(
        client_with_required_channel,
        telegram_id=5151,
        username="author",
    )
    ad_id = await create_ad(client_with_required_channel, author_csrf)
    await authenticate(
        client_with_required_channel,
        telegram_id=5152,
        username="initiator",
    )
    await expire_required_channel_membership(test_session, telegram_id=5152)
    fake_telegram_client.status_by_chat_id["@required"] = "left"
    call_count = len(fake_telegram_client.calls)

    response = await client_with_required_channel.post(
        f"/api/ads/{ad_id}/contact",
        headers={"X-CSRF-Token": "invalid"},
    )

    assert response.status_code == 403
    assert response.json()["message"] == "invalid csrf token"
    assert len(fake_telegram_client.calls) == call_count


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


async def test_claim_due_followups_ignores_canceled_attempts_and_marks_claimed(
    client,
    authenticate,
    test_session,
    test_settings,
) -> None:
    first_author_csrf = await authenticate(client, telegram_id=5201, username="first_author")
    first_ad_id = await create_ad(client, first_author_csrf)
    second_author_csrf = await authenticate(client, telegram_id=5202, username="second_author")
    second_ad_id = await create_ad(
        client,
        second_author_csrf,
        side="BUY",
        base_currency="EUR",
        quote_currency="USD",
        amount="250.00",
    )
    initiator_csrf = await authenticate(client, telegram_id=5203, username="initiator")

    first_contact = await client.post(
        f"/api/ads/{first_ad_id}/contact",
        headers={"X-CSRF-Token": initiator_csrf},
    )
    second_contact = await client.post(
        f"/api/ads/{second_ad_id}/contact",
        headers={"X-CSRF-Token": initiator_csrf},
    )
    assert first_contact.status_code == 201
    assert second_contact.status_code == 201

    due_at = utc_now() - timedelta(minutes=1)
    attempts = (
        await test_session.execute(select(ContactAttempt).order_by(ContactAttempt.id))
    ).scalars().all()
    for attempt in attempts:
        attempt.followup_due_at = due_at
    await test_session.commit()

    response = await client.post(
        "/api/internal/contact-followups/claim",
        headers={
            "X-Internal-Bot-Secret": (
                test_settings.telegram_internal_bot_secret.get_secret_value()
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["contact_attempt_id"] == second_contact.json()["contact_attempt_id"]
    assert item["initiator_telegram_id"] == 5203
    assert item["author_telegram_id"] == 5202
    assert item["ad_id"] == second_ad_id
    assert item["side"] == "BUY"
    assert item["pair"] == "EUR/USD"
    assert item["amount"] == "250.00000000"
    assert "BUY 250.00000000 EUR/USD" in item["summary"]

    attempts = (
        await test_session.execute(select(ContactAttempt).order_by(ContactAttempt.id))
    ).scalars().all()
    assert [attempt.status for attempt in attempts] == ["CANCELED_BY_NEW_CONTACT", "OPENED"]
    await test_session.commit()

    prompt_sent_response = await client.post(
        f"/api/internal/contact-followups/{item['contact_attempt_id']}/prompt-sent",
        json={"prompt_type": "initiator"},
        headers={
            "X-Internal-Bot-Secret": (
                test_settings.telegram_internal_bot_secret.get_secret_value()
            )
        },
    )
    assert prompt_sent_response.status_code == 200
    assert prompt_sent_response.json()["action"] == "prompt_recorded"
    second_attempt = await test_session.get(ContactAttempt, item["contact_attempt_id"])
    assert second_attempt is not None
    assert second_attempt.status == "ASKED_INITIATOR"
    assert second_attempt.initiator_prompt_sent_at is not None
    await test_session.commit()

    second_response = await client.post(
        "/api/internal/contact-followups/claim",
        headers={
            "X-Internal-Bot-Secret": (
                test_settings.telegram_internal_bot_secret.get_secret_value()
            )
        },
    )
    assert second_response.status_code == 200
    assert second_response.json() == {"items": []}


async def test_new_contact_cancels_already_asked_initiator_followup(
    client,
    authenticate,
    test_session,
) -> None:
    first_author_csrf = await authenticate(client, telegram_id=5221, username="first_author")
    first_ad_id = await create_ad(client, first_author_csrf)
    second_author_csrf = await authenticate(client, telegram_id=5222, username="second_author")
    second_ad_id = await create_ad(
        client,
        second_author_csrf,
        base_currency="EUR",
        quote_currency="USD",
    )
    initiator_csrf = await authenticate(client, telegram_id=5223, username="initiator")
    first_contact = await client.post(
        f"/api/ads/{first_ad_id}/contact",
        headers={"X-CSRF-Token": initiator_csrf},
    )
    assert first_contact.status_code == 201
    first_attempt = await test_session.get(
        ContactAttempt,
        first_contact.json()["contact_attempt_id"],
    )
    assert first_attempt is not None
    first_attempt.status = "ASKED_INITIATOR"
    await test_session.commit()

    second_contact = await client.post(
        f"/api/ads/{second_ad_id}/contact",
        headers={"X-CSRF-Token": initiator_csrf},
    )

    assert second_contact.status_code == 201
    attempts = (
        await test_session.execute(select(ContactAttempt).order_by(ContactAttempt.id))
    ).scalars().all()
    assert [attempt.status for attempt in attempts] == ["CANCELED_BY_NEW_CONTACT", "OPENED"]


async def test_prompt_sent_for_canceled_claim_returns_stale(
    client,
    authenticate,
    test_session,
    test_settings,
) -> None:
    first_author_csrf = await authenticate(client, telegram_id=5231, username="first_author")
    first_ad_id = await create_ad(client, first_author_csrf)
    second_author_csrf = await authenticate(client, telegram_id=5232, username="second_author")
    second_ad_id = await create_ad(
        client,
        second_author_csrf,
        base_currency="EUR",
        quote_currency="USD",
    )
    initiator_csrf = await authenticate(client, telegram_id=5233, username="initiator")
    first_contact = await client.post(
        f"/api/ads/{first_ad_id}/contact",
        headers={"X-CSRF-Token": initiator_csrf},
    )
    first_contact_id = first_contact.json()["contact_attempt_id"]
    first_attempt = await test_session.get(ContactAttempt, first_contact_id)
    assert first_attempt is not None
    first_attempt.followup_due_at = utc_now() - timedelta(minutes=1)
    await test_session.commit()

    claim_response = await client.post(
        "/api/internal/contact-followups/claim",
        headers=internal_headers(test_settings),
    )
    assert claim_response.status_code == 200
    assert claim_response.json()["items"][0]["contact_attempt_id"] == first_contact_id

    second_contact = await client.post(
        f"/api/ads/{second_ad_id}/contact",
        headers={"X-CSRF-Token": initiator_csrf},
    )
    assert second_contact.status_code == 201

    prompt_sent_response = await client.post(
        f"/api/internal/contact-followups/{first_contact_id}/prompt-sent",
        json={"prompt_type": "initiator"},
        headers=internal_headers(test_settings),
    )

    assert prompt_sent_response.status_code == 200
    assert prompt_sent_response.json()["action"] == "stale"
    attempts = (
        await test_session.execute(select(ContactAttempt).order_by(ContactAttempt.id))
    ).scalars().all()
    assert [attempt.status for attempt in attempts] == ["CANCELED_BY_NEW_CONTACT", "OPENED"]
    assert attempts[0].initiator_prompt_sent_at is None


async def test_author_prompt_is_claimed_after_initiator_yes_and_recorded_after_send(
    client,
    authenticate,
    test_session,
    test_settings,
) -> None:
    author_csrf = await authenticate(client, telegram_id=5234, username="author")
    ad_id = await create_ad(client, author_csrf)
    initiator_csrf = await authenticate(client, telegram_id=5235, username="initiator")
    contact_response = await client.post(
        f"/api/ads/{ad_id}/contact",
        headers={"X-CSRF-Token": initiator_csrf},
    )
    contact_attempt_id = contact_response.json()["contact_attempt_id"]
    attempt = await test_session.get(ContactAttempt, contact_attempt_id)
    assert attempt is not None
    attempt.status = "ASKED_INITIATOR"
    await test_session.commit()

    initiator_response = await client.post(
        f"/api/internal/contact-followups/{contact_attempt_id}/answer",
        json={"actor_telegram_id": 5235, "answer": "yes"},
        headers=internal_headers(test_settings),
    )
    assert initiator_response.status_code == 200
    assert initiator_response.json()["action"] == "ask_author"

    claim_response = await client.post(
        "/api/internal/contact-followups/claim",
        headers=internal_headers(test_settings),
    )
    assert claim_response.status_code == 200
    item = claim_response.json()["items"][0]
    assert item["contact_attempt_id"] == contact_attempt_id
    assert item["prompt_type"] == "author"
    assert item["author_telegram_id"] == 5234

    prompt_sent_response = await client.post(
        f"/api/internal/contact-followups/{contact_attempt_id}/prompt-sent",
        json={"prompt_type": "author"},
        headers=internal_headers(test_settings),
    )

    assert prompt_sent_response.status_code == 200
    assert prompt_sent_response.json()["action"] == "prompt_recorded"
    attempt = await test_session.get(ContactAttempt, contact_attempt_id)
    assert attempt is not None
    assert attempt.status == "WAITING_AUTHOR_CONFIRMATION"
    assert attempt.author_prompt_sent_at is not None
    assert attempt.followup_due_at > utc_now()
    await test_session.commit()

    second_claim_response = await client.post(
        "/api/internal/contact-followups/claim",
        headers=internal_headers(test_settings),
    )
    assert second_claim_response.status_code == 200
    assert second_claim_response.json() == {"items": []}


async def test_due_answer_prompts_expire_when_user_does_not_reply(
    client,
    authenticate,
    test_session,
    test_settings,
) -> None:
    first_author_csrf = await authenticate(client, telegram_id=5236, username="first_author")
    first_ad_id = await create_ad(client, first_author_csrf)
    second_author_csrf = await authenticate(client, telegram_id=5237, username="second_author")
    second_ad_id = await create_ad(
        client,
        second_author_csrf,
        side="BUY",
        base_currency="EUR",
        quote_currency="USD",
    )
    initiator_csrf = await authenticate(client, telegram_id=5238, username="initiator")
    first_contact = await client.post(
        f"/api/ads/{first_ad_id}/contact",
        headers={"X-CSRF-Token": initiator_csrf},
    )
    second_contact = await client.post(
        f"/api/ads/{second_ad_id}/contact",
        headers={"X-CSRF-Token": initiator_csrf},
    )
    assert first_contact.status_code == 201
    assert second_contact.status_code == 201

    now = utc_now()
    first_attempt = await test_session.get(
        ContactAttempt,
        first_contact.json()["contact_attempt_id"],
    )
    second_attempt = await test_session.get(
        ContactAttempt,
        second_contact.json()["contact_attempt_id"],
    )
    assert first_attempt is not None
    assert second_attempt is not None
    first_attempt.status = "ASKED_INITIATOR"
    first_attempt.followup_due_at = now - timedelta(minutes=1)
    second_attempt.status = "WAITING_AUTHOR_CONFIRMATION"
    second_attempt.author_prompt_sent_at = now - timedelta(days=1)
    second_attempt.followup_due_at = now - timedelta(minutes=1)
    await test_session.commit()

    response = await client.post(
        "/api/internal/contact-followups/claim",
        headers=internal_headers(test_settings),
    )

    assert response.status_code == 200
    assert response.json() == {"items": []}
    attempts = (
        await test_session.execute(select(ContactAttempt).order_by(ContactAttempt.id))
    ).scalars().all()
    assert [attempt.status for attempt in attempts] == ["EXPIRED", "EXPIRED"]


async def test_initiator_no_answer_closes_attempt(
    client,
    authenticate,
    test_session,
    test_settings,
) -> None:
    author_csrf = await authenticate(client, telegram_id=5204, username="author")
    ad_id = await create_ad(client, author_csrf)
    initiator_csrf = await authenticate(client, telegram_id=5205, username="initiator")
    contact_response = await client.post(
        f"/api/ads/{ad_id}/contact",
        headers={"X-CSRF-Token": initiator_csrf},
    )
    contact_attempt_id = contact_response.json()["contact_attempt_id"]
    attempt = await test_session.get(ContactAttempt, contact_attempt_id)
    assert attempt is not None
    attempt.status = "ASKED_INITIATOR"
    await test_session.commit()

    response = await client.post(
        f"/api/internal/contact-followups/{contact_attempt_id}/answer",
        json={"actor_telegram_id": 5205, "answer": "no"},
        headers={
            "X-Internal-Bot-Secret": (
                test_settings.telegram_internal_bot_secret.get_secret_value()
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "INITIATOR_NO_DEAL"
    attempt = await test_session.get(ContactAttempt, contact_attempt_id)
    assert attempt is not None
    assert attempt.status == "INITIATOR_NO_DEAL"
    assert attempt.initiator_answered_at is not None


async def test_author_confirmation_yes_completes_ad_and_removes_from_active_board(
    client,
    authenticate,
    test_session,
    test_settings,
) -> None:
    author_csrf = await authenticate(client, telegram_id=5206, username="author")
    ad_id = await create_ad(client, author_csrf)
    initiator_csrf = await authenticate(client, telegram_id=5207, username="initiator")
    contact_response = await client.post(
        f"/api/ads/{ad_id}/contact",
        headers={"X-CSRF-Token": initiator_csrf},
    )
    contact_attempt_id = contact_response.json()["contact_attempt_id"]
    attempt = await test_session.get(ContactAttempt, contact_attempt_id)
    assert attempt is not None
    attempt.status = "ASKED_INITIATOR"
    await test_session.commit()

    initiator_response = await client.post(
        f"/api/internal/contact-followups/{contact_attempt_id}/answer",
        json={"actor_telegram_id": 5207, "answer": "yes"},
        headers={
            "X-Internal-Bot-Secret": (
                test_settings.telegram_internal_bot_secret.get_secret_value()
            )
        },
    )

    assert initiator_response.status_code == 200
    assert initiator_response.json()["status"] == "WAITING_AUTHOR_CONFIRMATION"
    assert initiator_response.json()["action"] == "ask_author"
    assert initiator_response.json()["author_telegram_id"] == 5206

    author_response = await client.post(
        f"/api/internal/contact-followups/{contact_attempt_id}/answer",
        json={"actor_telegram_id": 5206, "answer": "yes"},
        headers={
            "X-Internal-Bot-Secret": (
                test_settings.telegram_internal_bot_secret.get_secret_value()
            )
        },
    )

    assert author_response.status_code == 200
    assert author_response.json()["status"] == "COMPLETED_CONFIRMED"
    ad = await test_session.get(Ad, ad_id)
    assert ad is not None
    assert ad.status == "COMPLETED"
    assert ad.completed_at is not None
    assert ad.updated_at == ad.completed_at
    attempt = await test_session.get(ContactAttempt, contact_attempt_id)
    assert attempt is not None
    assert attempt.status == "COMPLETED_CONFIRMED"
    assert attempt.author_answered_at is not None

    active_response = await client.get("/api/ads")
    assert active_response.status_code == 200
    assert active_response.json()["sell"] == []
    assert active_response.json()["buy"] == []


async def test_author_no_rejects_waiting_attempt_without_completing_ad(
    client,
    authenticate,
    test_session,
    test_settings,
) -> None:
    author_csrf = await authenticate(client, telegram_id=5208, username="author")
    ad_id = await create_ad(client, author_csrf)
    initiator_csrf = await authenticate(client, telegram_id=5209, username="initiator")
    contact_response = await client.post(
        f"/api/ads/{ad_id}/contact",
        headers={"X-CSRF-Token": initiator_csrf},
    )
    contact_attempt_id = contact_response.json()["contact_attempt_id"]
    attempt = await test_session.get(ContactAttempt, contact_attempt_id)
    assert attempt is not None
    attempt.status = "WAITING_AUTHOR_CONFIRMATION"
    await test_session.commit()

    response = await client.post(
        f"/api/internal/contact-followups/{contact_attempt_id}/answer",
        json={"actor_telegram_id": 5208, "answer": "no"},
        headers={
            "X-Internal-Bot-Secret": (
                test_settings.telegram_internal_bot_secret.get_secret_value()
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "AUTHOR_REJECTED"
    ad = await test_session.get(Ad, ad_id)
    assert ad is not None
    assert ad.status == "ACTIVE"


async def test_author_yes_rejects_when_ad_is_no_longer_active(
    client,
    authenticate,
    test_session,
    test_settings,
) -> None:
    author_csrf = await authenticate(client, telegram_id=5241, username="author")
    ad_id = await create_ad(client, author_csrf)
    initiator_csrf = await authenticate(client, telegram_id=5242, username="initiator")
    contact_response = await client.post(
        f"/api/ads/{ad_id}/contact",
        headers={"X-CSRF-Token": initiator_csrf},
    )
    contact_attempt_id = contact_response.json()["contact_attempt_id"]
    attempt = await test_session.get(ContactAttempt, contact_attempt_id)
    ad = await test_session.get(Ad, ad_id)
    assert attempt is not None
    assert ad is not None
    attempt.status = "WAITING_AUTHOR_CONFIRMATION"
    ad.status = "REVOKED"
    await test_session.commit()

    response = await client.post(
        f"/api/internal/contact-followups/{contact_attempt_id}/answer",
        json={"actor_telegram_id": 5241, "answer": "yes"},
        headers=internal_headers(test_settings),
    )

    assert response.status_code == 400
    assert response.json()["message"] == "ad is no longer active"
    ad = await test_session.get(Ad, ad_id)
    attempt = await test_session.get(ContactAttempt, contact_attempt_id)
    assert ad is not None
    assert attempt is not None
    assert ad.status == "REVOKED"
    assert ad.completed_at is None
    assert attempt.status == "WAITING_AUTHOR_CONFIRMATION"


async def test_answer_rejects_wrong_actor(
    client,
    authenticate,
    test_session,
    test_settings,
) -> None:
    author_csrf = await authenticate(client, telegram_id=5210, username="author")
    ad_id = await create_ad(client, author_csrf)
    initiator_csrf = await authenticate(client, telegram_id=5211, username="initiator")
    contact_response = await client.post(
        f"/api/ads/{ad_id}/contact",
        headers={"X-CSRF-Token": initiator_csrf},
    )
    contact_attempt_id = contact_response.json()["contact_attempt_id"]
    attempt = await test_session.get(ContactAttempt, contact_attempt_id)
    assert attempt is not None
    attempt.status = "ASKED_INITIATOR"
    await test_session.commit()

    response = await client.post(
        f"/api/internal/contact-followups/{contact_attempt_id}/answer",
        json={"actor_telegram_id": 5210, "answer": "yes"},
        headers={
            "X-Internal-Bot-Secret": (
                test_settings.telegram_internal_bot_secret.get_secret_value()
            )
        },
    )

    assert response.status_code == 403
    assert response.json()["message"] == "actor cannot answer this contact attempt"


async def test_database_rejects_two_opened_contacts_for_same_initiator(
    client,
    authenticate,
    test_session,
) -> None:
    author_csrf = await authenticate(client, telegram_id=5013, username="author")
    ad_id = await create_ad(client, author_csrf)
    initiator_csrf = await authenticate(client, telegram_id=5014, username="initiator")
    first_contact = await client.post(
        f"/api/ads/{ad_id}/contact",
        headers={"X-CSRF-Token": initiator_csrf},
    )
    assert first_contact.status_code == 201

    initiator = (
        await test_session.execute(select(User).where(User.telegram_id == 5014))
    ).scalar_one()
    author = (
        await test_session.execute(select(User).where(User.telegram_id == 5013))
    ).scalar_one()
    now = utc_now()
    test_session.add(
        ContactAttempt(
            initiator_user_id=initiator.id,
            author_user_id=author.id,
            ad_id=ad_id,
            status="OPENED",
            followup_due_at=now + timedelta(hours=2),
            created_at=now,
            updated_at=now,
        )
    )

    with pytest.raises(IntegrityError):
        await test_session.commit()
    await test_session.rollback()


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
