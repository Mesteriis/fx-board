import hashlib
import hmac
import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from urllib.parse import urlencode

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import Settings, get_settings
from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.session import create_engine, get_session
from app.main import create_app
from app.telegram.client import ChatMemberResult, TelegramApiError


@pytest.fixture
async def test_session():
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


class FakeTelegramClient:
    def __init__(self) -> None:
        self.status_by_chat_id: dict[str, str] = {}
        self.raw_by_chat_id: dict[str, dict[str, object]] = {}
        self.calls: list[tuple[str, int]] = []
        self.fail = False

    async def get_chat_member(self, *, chat_id: str, user_id: int) -> ChatMemberResult:
        self.calls.append((chat_id, user_id))
        if self.fail:
            raise TelegramApiError("test telegram failure")
        status = self.status_by_chat_id.get(chat_id, "member")
        raw = {"status": status, **self.raw_by_chat_id.get(chat_id, {})}
        return ChatMemberResult(status=status, raw=raw)


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        app_env="development",
        session_secret="test_session_secret_that_is_long_enough",
        telegram_bot_token="123456:test",
        telegram_bot_username="test_bot",
        telegram_webhook_secret="test_webhook_secret",
        telegram_required_channels="",
        admin_telegram_ids="123",
    )


@pytest.fixture
def fake_telegram_client() -> FakeTelegramClient:
    return FakeTelegramClient()


@pytest.fixture
def make_init_data(test_settings) -> Callable[..., str]:
    def _make_init_data(
        *,
        telegram_id: int = 123,
        username: str | None = "ivan",
        auth_date: datetime | None = None,
    ) -> str:
        timestamp = int((auth_date or datetime.now(UTC)).timestamp())
        user: dict[str, object] = {
            "id": telegram_id,
            "first_name": "Test",
            "last_name": "User",
            "language_code": "en",
        }
        if username is not None:
            user["username"] = username
        payload = {
            "auth_date": str(timestamp),
            "query_id": "AAEAAAE",
            "user": json.dumps(user, separators=(",", ":")),
        }
        data_check_string = "\n".join(f"{key}={payload[key]}" for key in sorted(payload))
        bot_token = test_settings.telegram_bot_token.get_secret_value()
        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        digest = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        return urlencode({**payload, "hash": digest})

    return _make_init_data


@pytest.fixture
def authenticate(make_init_data) -> Callable[..., Awaitable[str]]:
    async def _authenticate(
        client: AsyncClient,
        *,
        telegram_id: int = 123,
        username: str | None = "ivan",
    ) -> str:
        response = await client.post(
            "/api/auth/telegram-webapp",
            json={"init_data": make_init_data(telegram_id=telegram_id, username=username)},
        )
        assert response.status_code == 200
        return str(response.json()["csrf_token"])

    return _authenticate


@pytest.fixture
async def client(test_session, test_settings, fake_telegram_client) -> AsyncClient:
    from app.routers.auth import get_telegram_client

    app = create_app()

    async def override_session():
        yield test_session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_telegram_client] = lambda: fake_telegram_client

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as async_client:
        yield async_client


@pytest.fixture
async def client_with_required_channel(
    test_session,
    test_settings,
    fake_telegram_client,
) -> AsyncClient:
    from app.routers.auth import get_telegram_client

    test_settings.telegram_required_channels = "@required"
    app = create_app()

    async def override_session():
        yield test_session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_telegram_client] = lambda: fake_telegram_client

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as async_client:
        yield async_client
