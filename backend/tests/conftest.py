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
        self.calls: list[tuple[str, int]] = []
        self.fail = False

    async def get_chat_member(self, *, chat_id: str, user_id: int) -> ChatMemberResult:
        self.calls.append((chat_id, user_id))
        if self.fail:
            raise TelegramApiError("test telegram failure")
        status = self.status_by_chat_id.get(chat_id, "member")
        return ChatMemberResult(status=status, raw={"status": status})


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
