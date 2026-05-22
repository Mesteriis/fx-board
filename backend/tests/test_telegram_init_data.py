import hashlib
import hmac
import json
from datetime import UTC, datetime
from urllib.parse import urlencode

import pytest

from app.services.auth import InitDataError, verify_telegram_init_data


def signed_init_data(bot_token: str, payload: dict[str, str]) -> str:
    data_check_string = "\n".join(f"{key}={payload[key]}" for key in sorted(payload))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    digest = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode({**payload, "hash": digest})


def test_valid_init_data_returns_user() -> None:
    bot_token = "123456:secret"
    auth_date = int(datetime(2026, 5, 22, tzinfo=UTC).timestamp())
    init_data = signed_init_data(
        bot_token,
        {
            "auth_date": str(auth_date),
            "query_id": "AAEAAAE",
            "user": json.dumps(
                {
                    "id": 123,
                    "username": "ivan",
                    "first_name": "Ivan",
                    "last_name": "Ivanov",
                    "language_code": "en",
                    "photo_url": "https://example.com/photo.jpg",
                },
                separators=(",", ":"),
            ),
        },
    )

    result = verify_telegram_init_data(
        init_data=init_data,
        bot_token=bot_token,
        now=datetime(2026, 5, 22, 0, 10, tzinfo=UTC),
        max_age_seconds=86400,
    )

    assert result.telegram_id == 123
    assert result.username == "ivan"
    assert result.first_name == "Ivan"
    assert result.last_name == "Ivanov"
    assert result.language_code == "en"
    assert result.photo_url == "https://example.com/photo.jpg"


def test_tampered_init_data_is_rejected() -> None:
    bot_token = "123456:secret"
    auth_date = int(datetime(2026, 5, 22, tzinfo=UTC).timestamp())
    init_data = signed_init_data(
        bot_token,
        {
            "auth_date": str(auth_date),
            "query_id": "AAEAAAE",
            "user": json.dumps({"id": 123, "username": "ivan"}, separators=(",", ":")),
        },
    ).replace("ivan", "admin")

    with pytest.raises(InitDataError):
        verify_telegram_init_data(
            init_data=init_data,
            bot_token=bot_token,
            now=datetime(2026, 5, 22, 0, 10, tzinfo=UTC),
            max_age_seconds=86400,
        )


def test_expired_init_data_is_rejected() -> None:
    bot_token = "123456:secret"
    init_data = signed_init_data(
        bot_token,
        {
            "auth_date": "1000",
            "user": json.dumps({"id": 123}, separators=(",", ":")),
        },
    )

    with pytest.raises(InitDataError):
        verify_telegram_init_data(
            init_data=init_data,
            bot_token=bot_token,
            now=datetime(2026, 5, 22, tzinfo=UTC),
            max_age_seconds=86400,
        )


def test_missing_user_is_rejected() -> None:
    bot_token = "123456:secret"
    auth_date = int(datetime(2026, 5, 22, tzinfo=UTC).timestamp())
    init_data = signed_init_data(bot_token, {"auth_date": str(auth_date)})

    with pytest.raises(InitDataError):
        verify_telegram_init_data(
            init_data=init_data,
            bot_token=bot_token,
            now=datetime(2026, 5, 22, 0, 10, tzinfo=UTC),
            max_age_seconds=86400,
        )
