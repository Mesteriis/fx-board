import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

from sqlalchemy import select

from app.core.time import utc_now
from app.db.models import RequiredChannel, Session, User, UserChannelMembership


def signed_init_data(
    *,
    bot_token: str = "123456:test",
    telegram_id: int = 123,
    username: str = "ivan",
    auth_date: datetime | None = None,
) -> str:
    timestamp = int((auth_date or datetime.now(UTC)).timestamp())
    payload = {
        "auth_date": str(timestamp),
        "query_id": "AAEAAAE",
        "user": json.dumps(
            {
                "id": telegram_id,
                "username": username,
                "first_name": "Ivan",
                "last_name": "Ivanov",
                "language_code": "en",
            },
            separators=(",", ":"),
        ),
    }
    data_check_string = "\n".join(f"{key}={payload[key]}" for key in sorted(payload))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    digest = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode({**payload, "hash": digest})


async def test_auth_rejects_tampered_init_data(client) -> None:
    response = await client.post(
        "/api/auth/telegram-webapp",
        json={"init_data": "auth_date=1&hash=bad"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


async def test_successful_auth_creates_user_session_and_cookies(client, test_session) -> None:
    response = await client.post(
        "/api/auth/telegram-webapp",
        json={"init_data": signed_init_data()},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["telegram_id"] == 123
    assert body["user"]["username"] == "ivan"
    assert body["user"]["is_admin"] is True
    assert body["access"] == {"allowed": True, "required_channels": [], "missing_channels": []}
    assert body["csrf_token"]
    assert client.cookies.get("session")
    assert client.cookies.get("csrf_token", "").startswith(f"{body['csrf_token']}.")

    users = (await test_session.execute(select(User))).scalars().all()
    sessions = (await test_session.execute(select(Session))).scalars().all()
    assert len(users) == 1
    assert len(sessions) == 1
    assert sessions[0].user_id == users[0].id


async def test_successful_auth_updates_existing_user(client, test_session) -> None:
    first_response = await client.post(
        "/api/auth/telegram-webapp",
        json={"init_data": signed_init_data(telegram_id=123, username="ivan")},
    )
    assert first_response.status_code == 200

    second_response = await client.post(
        "/api/auth/telegram-webapp",
        json={"init_data": signed_init_data(telegram_id=123, username="updated")},
    )

    assert second_response.status_code == 200
    users = (await test_session.execute(select(User))).scalars().all()
    assert len(users) == 1
    assert users[0].username == "updated"


async def test_me_requires_session(client) -> None:
    response = await client.get("/api/auth/me")

    assert response.status_code == 401


async def test_me_returns_current_user_for_valid_session(client) -> None:
    auth_response = await client.post(
        "/api/auth/telegram-webapp",
        json={"init_data": signed_init_data()},
    )
    assert auth_response.status_code == 200

    me_response = await client.get("/api/auth/me")

    assert me_response.status_code == 200
    assert me_response.json()["user"]["telegram_id"] == 123


async def test_me_does_not_echo_tampered_csrf_cookie(client) -> None:
    auth_response = await client.post(
        "/api/auth/telegram-webapp",
        json={"init_data": signed_init_data()},
    )
    assert auth_response.status_code == 200
    client.cookies.set("csrf_token", "attacker-controlled.invalid-signature")

    me_response = await client.get("/api/auth/me")

    assert me_response.status_code == 200
    assert me_response.json()["csrf_token"] == ""


async def test_auth_checks_required_channels_with_cache(
    client_with_required_channel,
    fake_telegram_client,
    test_session,
) -> None:
    response = await client_with_required_channel.post(
        "/api/auth/telegram-webapp",
        json={"init_data": signed_init_data()},
    )

    assert response.status_code == 200
    assert response.json()["access"]["allowed"] is True
    assert fake_telegram_client.calls == [("@required", 123)]

    channel = (await test_session.execute(select(RequiredChannel))).scalar_one()
    membership = (await test_session.execute(select(UserChannelMembership))).scalar_one()
    assert channel.chat_id == "@required"
    assert membership.is_member is True
    assert membership.telegram_status == "member"

    me_response = await client_with_required_channel.get("/api/auth/me")

    assert me_response.status_code == 200
    assert fake_telegram_client.calls == [("@required", 123)]


async def test_auth_denies_missing_required_channel(
    client_with_required_channel,
    fake_telegram_client,
) -> None:
    fake_telegram_client.status_by_chat_id["@required"] = "left"

    response = await client_with_required_channel.post(
        "/api/auth/telegram-webapp",
        json={"init_data": signed_init_data()},
    )

    assert response.status_code == 403
    body = response.json()
    assert body["code"] == "forbidden"


async def test_logout_requires_valid_session(client) -> None:
    client.cookies.set("csrf_token", "token")
    response = await client.post(
        "/api/auth/logout",
        headers={"X-CSRF-Token": "token"},
    )

    assert response.status_code == 401


async def test_logout_rejects_missing_csrf(client) -> None:
    auth_response = await client.post(
        "/api/auth/telegram-webapp",
        json={"init_data": signed_init_data()},
    )
    assert auth_response.status_code == 200

    response = await client.post("/api/auth/logout")

    assert response.status_code == 403


async def test_logout_invalidates_session(client, test_session) -> None:
    auth_response = await client.post(
        "/api/auth/telegram-webapp",
        json={"init_data": signed_init_data()},
    )
    assert auth_response.status_code == 200
    csrf_token = auth_response.json()["csrf_token"]
    session_id = client.cookies.get("session")

    response = await client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf_token})

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert session_id is not None
    assert await test_session.get(Session, session_id) is None

    me_response = await client.get("/api/auth/me")
    assert me_response.status_code == 401


async def test_logout_rejects_csrf_from_different_session(client) -> None:
    first_auth = await client.post(
        "/api/auth/telegram-webapp",
        json={"init_data": signed_init_data(telegram_id=123, username="ivan")},
    )
    assert first_auth.status_code == 200
    first_csrf_token = first_auth.json()["csrf_token"]

    second_auth = await client.post(
        "/api/auth/telegram-webapp",
        json={"init_data": signed_init_data(telegram_id=456, username="petr")},
    )
    assert second_auth.status_code == 200

    response = await client.post("/api/auth/logout", headers={"X-CSRF-Token": first_csrf_token})

    assert response.status_code == 403


async def test_banned_user_is_denied(client, test_session) -> None:
    first_response = await client.post(
        "/api/auth/telegram-webapp",
        json={"init_data": signed_init_data()},
    )
    assert first_response.status_code == 200
    user = (await test_session.execute(select(User))).scalar_one()
    user.is_banned = True
    await test_session.commit()

    response = await client.post(
        "/api/auth/telegram-webapp",
        json={"init_data": signed_init_data()},
    )

    assert response.status_code == 403


async def test_me_rejects_expired_session(client, test_session) -> None:
    auth_response = await client.post(
        "/api/auth/telegram-webapp",
        json={"init_data": signed_init_data()},
    )
    assert auth_response.status_code == 200

    session = (await test_session.execute(select(Session))).scalar_one()
    session.expires_at = utc_now() - timedelta(seconds=1)
    await test_session.commit()

    response = await client.get("/api/auth/me")

    assert response.status_code == 401


async def test_telegram_api_failure_fails_closed(
    client_with_required_channel,
    fake_telegram_client,
) -> None:
    fake_telegram_client.fail = True

    response = await client_with_required_channel.post(
        "/api/auth/telegram-webapp",
        json={"init_data": signed_init_data()},
    )

    assert response.status_code == 403


async def test_stale_membership_cache_refreshes_and_updates_membership(
    client_with_required_channel,
    fake_telegram_client,
    test_session,
) -> None:
    auth_response = await client_with_required_channel.post(
        "/api/auth/telegram-webapp",
        json={"init_data": signed_init_data()},
    )
    assert auth_response.status_code == 200

    membership = (await test_session.execute(select(UserChannelMembership))).scalar_one()
    membership.expires_at = utc_now() - timedelta(seconds=1)
    await test_session.commit()
    fake_telegram_client.status_by_chat_id["@required"] = "left"

    response = await client_with_required_channel.get("/api/auth/me")

    assert response.status_code == 200
    body = response.json()
    assert body["access"]["allowed"] is False
    assert body["access"]["missing_channels"][0]["chat_id"] == "@required"
    await test_session.refresh(membership)
    assert membership.is_member is False
    assert membership.telegram_status == "left"
    assert fake_telegram_client.calls == [("@required", 123), ("@required", 123)]


async def test_product_policy_rejects_restricted_left_and_kicked_statuses(
    client_with_required_channel,
    fake_telegram_client,
    test_session,
) -> None:
    fake_telegram_client.raw_by_chat_id["@required"] = {"is_member": True}
    for status in ("restricted", "left", "kicked"):
        fake_telegram_client.status_by_chat_id["@required"] = status
        response = await client_with_required_channel.post(
            "/api/auth/telegram-webapp",
            json={
                "init_data": signed_init_data(
                    telegram_id=1000 + len(fake_telegram_client.calls)
                )
            },
        )
        assert response.status_code == 403

    memberships = (await test_session.execute(select(UserChannelMembership))).scalars().all()
    assert {membership.telegram_status for membership in memberships} == {
        "restricted",
        "left",
        "kicked",
    }
    assert all(not membership.is_member for membership in memberships)
    restricted_membership = next(
        membership for membership in memberships if membership.telegram_status == "restricted"
    )
    assert json.loads(restricted_membership.raw_response_json)["is_member"] is True


async def test_removed_required_channel_is_deactivated_and_not_enforced(
    client_with_required_channel,
    test_settings,
    test_session,
) -> None:
    auth_response = await client_with_required_channel.post(
        "/api/auth/telegram-webapp",
        json={"init_data": signed_init_data()},
    )
    assert auth_response.status_code == 200

    test_settings.telegram_required_channels = ""
    response = await client_with_required_channel.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json()["access"] == {
        "allowed": True,
        "required_channels": [],
        "missing_channels": [],
    }
    channel = (await test_session.execute(select(RequiredChannel))).scalar_one()
    assert channel.is_active is False
