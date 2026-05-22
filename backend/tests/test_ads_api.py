from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.time import utc_now
from app.db.models import Ad, UserChannelMembership


def ad_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "side": "sell",
        "base_currency": "USD",
        "quote_currency": "RUB",
        "amount": "100.00",
        "min_amount": "25.00",
        "max_amount": "100.00",
        "rate": "92.50",
        "payment_method": "cash",
        "location": "Madrid",
        "comment": "In person only",
    }
    payload.update(overrides)
    return payload


async def test_create_rejects_same_currency(client, authenticate) -> None:
    csrf_token = await authenticate(client)

    response = await client.post(
        "/api/ads",
        json=ad_payload(quote_currency="USD"),
        headers={"X-CSRF-Token": csrf_token},
    )

    assert response.status_code == 422


async def test_successful_create_and_list_split(client, authenticate) -> None:
    first_csrf = await authenticate(client, telegram_id=1001, username="seller")
    sell_response = await client.post(
        "/api/ads",
        json=ad_payload(side="sell", base_currency="USD", quote_currency="RUB"),
        headers={"X-CSRF-Token": first_csrf},
    )
    assert sell_response.status_code == 201

    second_csrf = await authenticate(client, telegram_id=1002, username="buyer")
    buy_response = await client.post(
        "/api/ads",
        json=ad_payload(side="buy", base_currency="EUR", quote_currency="USD", rate="1.08"),
        headers={"X-CSRF-Token": second_csrf},
    )
    assert buy_response.status_code == 201

    response = await client.get("/api/ads")

    assert response.status_code == 200
    body = response.json()
    assert [ad["id"] for ad in body["sell"]] == [sell_response.json()["id"]]
    assert [ad["id"] for ad in body["buy"]] == [buy_response.json()["id"]]
    assert body["pagination"] == {"limit": 20, "offset": 0, "total": 2}


async def test_active_ad_limit_is_enforced(client, authenticate, test_settings) -> None:
    test_settings.max_active_ads_per_user = 1
    csrf_token = await authenticate(client)

    first_response = await client.post(
        "/api/ads",
        json=ad_payload(),
        headers={"X-CSRF-Token": csrf_token},
    )
    second_response = await client.post(
        "/api/ads",
        json=ad_payload(base_currency="EUR", quote_currency="USD"),
        headers={"X-CSRF-Token": csrf_token},
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 400
    assert second_response.json()["message"] == "active ad limit reached"


async def test_expired_ads_are_not_shown(client, authenticate, test_session) -> None:
    csrf_token = await authenticate(client)
    create_response = await client.post(
        "/api/ads",
        json=ad_payload(),
        headers={"X-CSRF-Token": csrf_token},
    )
    assert create_response.status_code == 201

    ad = await test_session.get(Ad, create_response.json()["id"])
    assert ad is not None
    ad.expires_at = utc_now() - timedelta(seconds=1)
    await test_session.commit()

    response = await client.get("/api/ads")

    assert response.status_code == 200
    body = response.json()
    assert body["sell"] == []
    assert body["buy"] == []
    assert body["pagination"]["total"] == 0


async def test_update_rejects_immutable_fields(client, authenticate, test_session) -> None:
    csrf_token = await authenticate(client)
    create_response = await client.post(
        "/api/ads",
        json=ad_payload(),
        headers={"X-CSRF-Token": csrf_token},
    )
    assert create_response.status_code == 201
    ad_id = create_response.json()["id"]

    response = await client.patch(
        f"/api/ads/{ad_id}",
        json={"side": "buy", "base_currency": "EUR", "user_id": 999},
        headers={"X-CSRF-Token": csrf_token},
    )

    assert response.status_code == 422
    ad = await test_session.get(Ad, ad_id)
    assert ad is not None
    assert ad.side == "SELL"
    assert ad.base_currency == "USD"
    assert ad.user_id != 999


async def test_update_allows_mutable_fields(client, authenticate, test_session) -> None:
    csrf_token = await authenticate(client)
    create_response = await client.post(
        "/api/ads",
        json=ad_payload(comment="before"),
        headers={"X-CSRF-Token": csrf_token},
    )
    assert create_response.status_code == 201
    ad_id = create_response.json()["id"]

    response = await client.patch(
        f"/api/ads/{ad_id}",
        json={"amount": "75.00", "max_amount": "75.00", "rate": "93.00", "comment": "after"},
        headers={"X-CSRF-Token": csrf_token},
    )

    assert response.status_code == 200
    body = response.json()
    assert Decimal(body["amount"]) == Decimal("75.00")
    assert Decimal(body["rate"]) == Decimal("93.00")
    assert body["comment"] == "after"
    ad = await test_session.get(Ad, ad_id)
    assert ad is not None
    assert ad.amount == Decimal("75.00000000")
    assert ad.rate == Decimal("93.00000000")


async def test_revoke_rejects_non_owner(client, authenticate, test_session) -> None:
    csrf_token = await authenticate(client, telegram_id=2001, username="owner")
    create_response = await client.post(
        "/api/ads",
        json=ad_payload(),
        headers={"X-CSRF-Token": csrf_token},
    )
    assert create_response.status_code == 201

    other_csrf = await authenticate(client, telegram_id=2002, username="other")
    response = await client.post(
        f"/api/ads/{create_response.json()['id']}/revoke",
        headers={"X-CSRF-Token": other_csrf},
    )

    assert response.status_code == 403
    ad = await test_session.get(Ad, create_response.json()["id"])
    assert ad is not None
    assert ad.status == "ACTIVE"


async def test_revoke_marks_ad_without_deleting(client, authenticate, test_session) -> None:
    csrf_token = await authenticate(client)
    create_response = await client.post(
        "/api/ads",
        json=ad_payload(),
        headers={"X-CSRF-Token": csrf_token},
    )
    assert create_response.status_code == 201

    response = await client.post(
        f"/api/ads/{create_response.json()['id']}/revoke",
        headers={"X-CSRF-Token": csrf_token},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "revoked"
    assert body["revoked_at"] is not None
    ad = await test_session.get(Ad, create_response.json()["id"])
    assert ad is not None
    assert ad.status == "REVOKED"
    assert ad.revoked_at is not None


async def test_my_ads_returns_current_users_ads_only(client, authenticate) -> None:
    first_csrf = await authenticate(client, telegram_id=3001, username="first")
    first_ad = await client.post(
        "/api/ads",
        json=ad_payload(),
        headers={"X-CSRF-Token": first_csrf},
    )
    assert first_ad.status_code == 201

    second_csrf = await authenticate(client, telegram_id=3002, username="second")
    second_ad = await client.post(
        "/api/ads",
        json=ad_payload(base_currency="EUR", quote_currency="USD"),
        headers={"X-CSRF-Token": second_csrf},
    )
    assert second_ad.status_code == 201

    response = await client.get("/api/ads/my")

    assert response.status_code == 200
    assert [ad["id"] for ad in response.json()["items"]] == [second_ad.json()["id"]]


async def test_public_detail_allows_active_ad(client, authenticate) -> None:
    csrf_token = await authenticate(client, telegram_id=4001, username="seller")
    create_response = await client.post(
        "/api/ads",
        json=ad_payload(),
        headers={"X-CSRF-Token": csrf_token},
    )
    assert create_response.status_code == 201

    response = await client.get(f"/api/ads/{create_response.json()['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == create_response.json()["id"]
    assert response.json()["author"]["username"] == "seller"


async def test_required_channel_denies_mutating_ads_endpoint(
    client_with_required_channel,
    fake_telegram_client,
    authenticate,
    test_session,
) -> None:
    csrf_token = await authenticate(client_with_required_channel)
    membership = (await test_session.execute(select(UserChannelMembership))).scalar_one()
    membership.expires_at = utc_now() - timedelta(seconds=1)
    await test_session.commit()
    fake_telegram_client.status_by_chat_id["@required"] = "left"

    response = await client_with_required_channel.post(
        "/api/ads",
        json=ad_payload(),
        headers={"X-CSRF-Token": csrf_token},
    )

    assert response.status_code == 403
    assert response.json()["message"] == "required channel membership missing"
