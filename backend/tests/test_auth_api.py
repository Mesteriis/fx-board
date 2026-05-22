import hashlib
import hmac
import json
from datetime import UTC, datetime
from urllib.parse import urlencode

from sqlalchemy import select

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
    assert client.cookies.get("csrf_token") == body["csrf_token"]

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
