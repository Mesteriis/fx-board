# FX Board MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete FX Board Bot MVP as a monorepo with FastAPI, Nuxt SSR, SQLite, aiogram bot worker, Telegram Mini App auth, ads, reports, rates, admin UI, and Docker Compose deployment.

**Architecture:** Implement vertical slices with backend as the trusted boundary. Frontend renders a dark SSR shell and authenticates through Telegram `initData`; bot worker handles Telegram commands and scheduled follow-ups through backend contracts, never direct SQLite writes.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.x async, aiosqlite, Alembic, Pydantic v2, pytest, httpx, aiogram 3.x, Nuxt 3, Vue 3, TypeScript, Vitest, Playwright, Docker Compose.

---

## Source Spec

Primary design file:

- `docs/superpowers/specs/2026-05-22-fx-board-mvp-design.md`

This plan intentionally keeps the whole MVP in one implementation plan because the repository is empty and the approved design uses vertical slices. Execute tasks in order and commit after each task.

## Target File Structure

```text
.
├── .env.example
├── .gitignore
├── README.md
├── backend/
│   ├── alembic.ini
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── errors.py
│   │   │   ├── limits.py
│   │   │   ├── security.py
│   │   │   └── time.py
│   │   ├── db/
│   │   │   ├── base.py
│   │   │   ├── models.py
│   │   │   └── session.py
│   │   ├── routers/
│   │   │   ├── admin.py
│   │   │   ├── ads.py
│   │   │   ├── auth.py
│   │   │   ├── rates.py
│   │   │   ├── reports.py
│   │   │   └── telegram.py
│   │   ├── schemas/
│   │   │   ├── ads.py
│   │   │   ├── auth.py
│   │   │   ├── rates.py
│   │   │   ├── reports.py
│   │   │   └── shared.py
│   │   ├── services/
│   │   │   ├── access.py
│   │   │   ├── ads.py
│   │   │   ├── audit.py
│   │   │   ├── auth.py
│   │   │   ├── contacts.py
│   │   │   ├── rates.py
│   │   │   ├── reports.py
│   │   │   └── sessions.py
│   │   └── telegram/
│   │       ├── client.py
│   │       └── notifications.py
│   ├── migrations/
│   │   ├── env.py
│   │   └── versions/
│   │       └── 0001_initial.py
│   └── tests/
├── bot/
│   ├── pyproject.toml
│   ├── fx_board_bot/
│   │   ├── app.py
│   │   ├── backend_client.py
│   │   ├── callbacks.py
│   │   ├── commands.py
│   │   ├── config.py
│   │   └── followups.py
│   └── tests/
├── docker/
│   ├── backend.Dockerfile
│   ├── bot.Dockerfile
│   ├── compose.yml
│   ├── frontend.Dockerfile
│   └── reverse-proxy.md
├── docs/
│   └── superpowers/
│       ├── plans/
│       └── specs/
└── frontend/
    ├── app.vue
    ├── nuxt.config.ts
    ├── package.json
    ├── playwright.config.ts
    ├── tsconfig.json
    ├── assets/css/main.css
    ├── components/
    ├── composables/
    ├── pages/
    └── tests/
```

## Shared Domain Constants

Use these exact enum values across backend, frontend, and bot payloads:

```text
Currency: USD, EUR, RUB, USDT, USDC
AdSide: BUY, SELL
AdStatus: ACTIVE, REVOKED, HIDDEN, EXPIRED, COMPLETED
ReportReason: SCAM, SPAM, WRONG_RATE, OFFENSIVE, DUPLICATE, FAKE_CONTACT, OTHER
ReportStatus: NEW, IN_REVIEW, RESOLVED, REJECTED
ContactAttemptStatus: OPENED, CANCELED_BY_NEW_CONTACT, ASKED_INITIATOR, INITIATOR_NO_DEAL, WAITING_AUTHOR_CONFIRMATION, COMPLETED_CONFIRMED, AUTHOR_REJECTED, EXPIRED
```

---

### Task 1: Monorepo Tooling And Service Skeleton

**Files:**
- Create: `README.md`
- Create: `.env.example`
- Create: `backend/pyproject.toml`
- Create: `backend/app/main.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/core/time.py`
- Create: `backend/tests/test_health.py`
- Create: `bot/pyproject.toml`
- Create: `bot/fx_board_bot/config.py`
- Create: `bot/fx_board_bot/app.py`
- Create: `bot/tests/test_config.py`
- Create: `frontend/package.json`
- Create: `frontend/nuxt.config.ts`
- Create: `frontend/app.vue`
- Create: `frontend/assets/css/main.css`
- Create: `frontend/tests/basic.spec.ts`

- [ ] **Step 1: Create backend package skeleton**

Create `backend/pyproject.toml`:

```toml
[project]
name = "fx-board-backend"
version = "0.1.0"
requires-python = ">=3.11,<3.13"
dependencies = [
  "aiosqlite>=0.20.0",
  "alembic>=1.13.2",
  "fastapi>=0.115.0",
  "httpx>=0.27.0",
  "pydantic>=2.8.0",
  "pydantic-settings>=2.4.0",
  "python-multipart>=0.0.9",
  "sqlalchemy[asyncio]>=2.0.32",
  "uvicorn[standard]>=0.30.0"
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3.0",
  "pytest-asyncio>=0.23.8",
  "ruff>=0.6.0"
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM"]
```

Create `backend/app/core/time.py`:

```python
from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)
```

Create `backend/app/core/config.py`:

```python
from functools import lru_cache
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_base_url: str = "http://localhost:3000"
    database_url: str = "sqlite+aiosqlite:///./data/app.db"

    session_secret: SecretStr = Field(min_length=32)
    session_cookie_name: str = "session"
    session_ttl_seconds: int = 604800

    telegram_bot_token: SecretStr
    telegram_bot_username: str
    telegram_webhook_secret: SecretStr
    telegram_required_channels: str = ""
    admin_telegram_ids: str = ""

    google_rates_csv_url: str = ""
    rates_refresh_timezone: str = "Europe/Madrid"

    max_init_data_age_seconds: int = 86400
    max_active_ads_per_user: int = 10
    ad_default_ttl_hours: int = 24
    reports_to_auto_hide: int = 3
    deal_followup_delay_hours: int = 2

    @property
    def required_channels(self) -> list[str]:
        return [value.strip() for value in self.telegram_required_channels.split(",") if value.strip()]

    @property
    def admin_ids(self) -> set[int]:
        ids: set[int] = set()
        for raw in self.admin_telegram_ids.split(","):
            value = raw.strip()
            if value:
                ids.add(int(value))
        return ids


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

Create `backend/app/main.py`:

```python
from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="FX Board API")

    @app.get("/api/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
```

- [ ] **Step 2: Write backend health test**

Create `backend/tests/test_health.py`:

```python
from fastapi.testclient import TestClient
from app.main import create_app


def test_health_endpoint_returns_ok() -> None:
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 3: Run backend test**

Run:

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest tests/test_health.py -v
```

Expected: `1 passed`.

- [ ] **Step 4: Create bot package skeleton**

Create `bot/pyproject.toml`:

```toml
[project]
name = "fx-board-bot"
version = "0.1.0"
requires-python = ">=3.11,<3.13"
dependencies = [
  "aiogram>=3.12.0",
  "httpx>=0.27.0",
  "pydantic>=2.8.0",
  "pydantic-settings>=2.4.0"
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3.0",
  "pytest-asyncio>=0.23.8",
  "ruff>=0.6.0"
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py311"
```

Create `bot/fx_board_bot/config.py`:

```python
from functools import lru_cache
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: SecretStr
    app_base_url: str = "http://localhost:3000"
    backend_base_url: str = "http://localhost:8000"
    admin_telegram_ids: str = ""

    @property
    def admin_ids(self) -> set[int]:
        return {int(raw.strip()) for raw in self.admin_telegram_ids.split(",") if raw.strip()}


@lru_cache
def get_bot_settings() -> BotSettings:
    return BotSettings()
```

Create `bot/fx_board_bot/app.py`:

```python
import asyncio
from aiogram import Bot, Dispatcher
from .config import get_bot_settings


async def run_bot() -> None:
    settings = get_bot_settings()
    bot = Bot(token=settings.telegram_bot_token.get_secret_value())
    dispatcher = Dispatcher()
    await dispatcher.start_polling(bot)


def main() -> None:
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
```

Create `bot/tests/test_config.py`:

```python
from fx_board_bot.config import BotSettings


def test_admin_ids_are_parsed() -> None:
    settings = BotSettings(
        telegram_bot_token="123456:token",
        admin_telegram_ids="123, 456",
    )

    assert settings.admin_ids == {123, 456}
```

- [ ] **Step 5: Run bot test**

Run:

```bash
cd bot
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest tests/test_config.py -v
```

Expected: `1 passed`.

- [ ] **Step 6: Create frontend skeleton**

Create `frontend/package.json`:

```json
{
  "name": "fx-board-frontend",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "nuxt dev --host 0.0.0.0",
    "build": "nuxt build",
    "preview": "nuxt preview --host 0.0.0.0",
    "test": "vitest run",
    "test:e2e": "playwright test"
  },
  "dependencies": {
    "@nuxt/test-utils": "^3.14.0",
    "nuxt": "^3.13.0",
    "vue": "^3.5.0"
  },
  "devDependencies": {
    "@playwright/test": "^1.47.0",
    "typescript": "^5.5.0",
    "vitest": "^2.0.0"
  }
}
```

Create `frontend/nuxt.config.ts`:

```ts
export default defineNuxtConfig({
  compatibilityDate: '2026-05-22',
  css: ['~/assets/css/main.css'],
  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || '/api',
      botUsername: process.env.NUXT_PUBLIC_TELEGRAM_BOT_USERNAME || ''
    }
  },
  typescript: {
    strict: true
  }
})
```

Create `frontend/app.vue`:

```vue
<template>
  <NuxtPage />
</template>
```

Create `frontend/assets/css/main.css`:

```css
:root {
  color-scheme: dark;
  --color-bg: #0b0f14;
  --color-bg-secondary: #111827;
  --color-card: #161f2c;
  --color-border: #263244;
  --color-text: #e5e7eb;
  --color-text-muted: #9ca3af;
  --color-accent: #38bdf8;
  --color-success: #22c55e;
  --color-danger: #ef4444;
  --color-warning: #f59e0b;
}

html,
body,
#__nuxt {
  min-height: 100%;
  margin: 0;
  background: var(--color-bg);
  color: var(--color-text);
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

* {
  box-sizing: border-box;
}
```

Create `frontend/tests/basic.spec.ts`:

```ts
import { describe, expect, it } from 'vitest'

describe('frontend test setup', () => {
  it('runs vitest', () => {
    expect(true).toBe(true)
  })
})
```

- [ ] **Step 7: Run frontend test and build**

Run:

```bash
cd frontend
npm install
npm test
npm run build
```

Expected: Vitest passes and Nuxt build completes.

- [ ] **Step 8: Create environment and README**

Create `.env.example`:

```env
APP_ENV=development
APP_BASE_URL=http://localhost:3000
BACKEND_BASE_URL=http://localhost:8000

DATABASE_URL=sqlite+aiosqlite:///./data/app.db

SESSION_SECRET=change_me_very_long_random_secret_at_least_32_chars
SESSION_COOKIE_NAME=session
SESSION_TTL_SECONDS=604800

TELEGRAM_BOT_TOKEN=123456:secret
TELEGRAM_BOT_USERNAME=your_bot
TELEGRAM_WEBHOOK_SECRET=change_me
TELEGRAM_REQUIRED_CHANNELS=@channel_one,@channel_two
ADMIN_TELEGRAM_IDS=123456789,987654321

GOOGLE_RATES_CSV_URL=https://docs.google.com/spreadsheets/d/example/pub?gid=0&single=true&output=csv
RATES_REFRESH_TIMEZONE=Europe/Madrid

MAX_INIT_DATA_AGE_SECONDS=86400
MAX_ACTIVE_ADS_PER_USER=10
AD_DEFAULT_TTL_HOURS=24
REPORTS_TO_AUTO_HIDE=3
DEAL_FOLLOWUP_DELAY_HOURS=2

NUXT_PUBLIC_API_BASE=/api
NUXT_PUBLIC_TELEGRAM_BOT_USERNAME=your_bot
```

Create `README.md`:

````markdown
# FX Board Bot

Telegram Mini App currency classifieds board.

## Services

- `backend/`: FastAPI API and SQLite persistence.
- `frontend/`: Nuxt Vue 3 SSR WebApp.
- `bot/`: aiogram bot worker.
- `docker/`: deployment files.

## Local validation

Backend:

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

Bot:

```bash
cd bot
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

Frontend:

```bash
cd frontend
npm install
npm test
npm run build
```
````

- [ ] **Step 9: Run format/lint baseline**

Run:

```bash
cd backend && .venv/bin/ruff check app tests
cd ../bot && .venv/bin/ruff check fx_board_bot tests
cd ../frontend && npm test
```

Expected: all commands pass.

- [ ] **Step 10: Commit skeleton**

Run:

```bash
git add README.md .env.example backend bot frontend
git commit -m "chore: scaffold fx board monorepo"
```

Expected: commit created.

---

### Task 2: Backend Database Models, Migration, And Test Database

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/app/db/base.py`
- Create: `backend/app/db/models.py`
- Create: `backend/app/db/session.py`
- Create: `backend/migrations/env.py`
- Create: `backend/migrations/versions/0001_initial.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_schema.py`

- [ ] **Step 1: Write schema test first**

Create `backend/tests/test_schema.py`:

```python
from sqlalchemy import text


async def test_sqlite_pragmas_and_tables(test_session) -> None:
    result = await test_session.execute(text("PRAGMA foreign_keys"))
    assert result.scalar_one() == 1

    result = await test_session.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    )
    tables = {row[0] for row in result.all()}

    assert {
        "ads",
        "audit_log",
        "contact_attempts",
        "rate_limit_events",
        "rates",
        "reports",
        "required_channels",
        "sessions",
        "user_channel_memberships",
        "users",
    }.issubset(tables)
```

- [ ] **Step 2: Create database session support**

Create `backend/app/db/session.py`:

```python
from collections.abc import AsyncIterator
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from .base import Base
from app.core.config import get_settings


def create_engine(database_url: str | None = None) -> AsyncEngine:
    settings = get_settings()
    engine = create_async_engine(database_url or settings.database_url, future=True)

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    return engine


engine = create_engine()
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def create_all_for_tests(test_engine: AsyncEngine) -> None:
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
```

Create `backend/app/db/base.py`:

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

- [ ] **Step 3: Create SQLAlchemy models**

Create `backend/app/db/models.py` with all tables and enum constraints. Use `Numeric(18, 8)` for money/rates and timezone-aware `DateTime`.

```python
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    last_name: Mapped[str | None] = mapped_column(String(128))
    language_code: Mapped[str | None] = mapped_column(String(16))
    photo_url: Mapped[str | None] = mapped_column(String(512))
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    banned_reason: Mapped[str | None] = mapped_column(String(500))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(500))
    ip_hash: Mapped[str | None] = mapped_column(String(128))


class RequiredChannel(Base):
    __tablename__ = "required_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    title: Mapped[str | None] = mapped_column(String(255))
    public_url: Mapped[str | None] = mapped_column(String(512))
    invite_url: Mapped[str | None] = mapped_column(String(512))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UserChannelMembership(Base):
    __tablename__ = "user_channel_memberships"
    __table_args__ = (UniqueConstraint("user_id", "channel_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    channel_id: Mapped[int] = mapped_column(ForeignKey("required_channels.id"), nullable=False)
    telegram_status: Mapped[str | None] = mapped_column(String(64))
    is_member: Mapped[bool] = mapped_column(Boolean, nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_response_json: Mapped[str | None] = mapped_column(Text)


class Ad(Base):
    __tablename__ = "ads"
    __table_args__ = (
        CheckConstraint("side IN ('BUY', 'SELL')"),
        CheckConstraint("base_currency IN ('USD', 'EUR', 'RUB', 'USDT', 'USDC')"),
        CheckConstraint("quote_currency IN ('USD', 'EUR', 'RUB', 'USDT', 'USDC')"),
        CheckConstraint("status IN ('ACTIVE', 'REVOKED', 'HIDDEN', 'EXPIRED', 'COMPLETED')"),
        CheckConstraint("base_currency != quote_currency"),
        CheckConstraint("amount > 0"),
        CheckConstraint("rate > 0"),
        Index("idx_ads_status_side_created", "status", "side", "created_at"),
        Index("idx_ads_pair", "base_currency", "quote_currency"),
        Index("idx_ads_user_status", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(8), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(8), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    min_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    max_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    payment_method: Mapped[str | None] = mapped_column(String(120))
    location: Mapped[str | None] = mapped_column(String(120))
    comment: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    report_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hidden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

Add the remaining models to `backend/app/db/models.py`:

```python
class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        CheckConstraint("reason IN ('SCAM', 'SPAM', 'WRONG_RATE', 'OFFENSIVE', 'DUPLICATE', 'FAKE_CONTACT', 'OTHER')"),
        CheckConstraint("status IN ('NEW', 'IN_REVIEW', 'RESOLVED', 'REJECTED')"),
        Index("idx_reports_unique_user_ad", "reporter_user_id", "ad_id", unique=True, sqlite_where="ad_id IS NOT NULL"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reporter_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    target_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    ad_id: Mapped[int | None] = mapped_column(ForeignKey("ads.id"))
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    comment: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    resolved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Rate(Base):
    __tablename__ = "rates"
    __table_args__ = (UniqueConstraint("pair", "rate_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pair: Mapped[str] = mapped_column(String(16), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    rate_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_payload: Mapped[str | None] = mapped_column(Text)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(Integer)
    payload_json: Mapped[str | None] = mapped_column(Text)
    ip_hash: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RateLimitEvent(Base):
    __tablename__ = "rate_limit_events"
    __table_args__ = (Index("idx_rate_limit_key_action_created", "key", "action", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(160), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ContactAttempt(Base):
    __tablename__ = "contact_attempts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('OPENED', 'CANCELED_BY_NEW_CONTACT', 'ASKED_INITIATOR', 'INITIATOR_NO_DEAL', "
            "'WAITING_AUTHOR_CONFIRMATION', 'COMPLETED_CONFIRMED', 'AUTHOR_REJECTED', 'EXPIRED')"
        ),
        Index("idx_contact_attempts_due", "status", "followup_due_at"),
        Index("idx_contact_attempts_initiator_status", "initiator_user_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    initiator_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    author_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    ad_id: Mapped[int] = mapped_column(ForeignKey("ads.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    followup_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    initiator_answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    author_answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

- [ ] **Step 4: Create test fixture**

Create `backend/tests/conftest.py`:

```python
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.db.base import Base
from app.db.session import create_engine


@pytest.fixture
async def test_session():
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()
```

- [ ] **Step 5: Add Alembic files**

Create `backend/alembic.ini`:

```ini
[alembic]
script_location = migrations
prepend_sys_path = .
sqlalchemy.url = sqlite+aiosqlite:///./data/app.db

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
```

Create `backend/migrations/env.py`:

```python
from logging.config import fileConfig
from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from app.core.config import get_settings
from app.db.base import Base
from app.db import models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=get_settings().database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(
            lambda sync_connection: context.configure(
                connection=sync_connection,
                target_metadata=target_metadata,
            )
        )
        await connection.run_sync(lambda _connection: context.run_migrations())
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio

    asyncio.run(run_migrations_online())
```

Generate `backend/migrations/versions/0001_initial.py` from the models and inspect it before committing:

```bash
cd backend
mkdir -p data migrations/versions
.venv/bin/alembic revision --autogenerate -m "initial"
mv migrations/versions/*_initial.py migrations/versions/0001_initial.py
rg "create_table\\('users'|create_table\\('ads'|create_table\\('reports'|create_table\\('contact_attempts'|create_index" migrations/versions/0001_initial.py
```

Expected: the generated migration creates all tables from `models.py` and includes the indexes for users, ads, reports, rates, rate limits, and contact attempts.

- [ ] **Step 6: Run schema test**

Run:

```bash
cd backend
.venv/bin/pytest tests/test_schema.py -v
.venv/bin/ruff check app tests migrations
```

Expected: schema test passes and Ruff passes.

- [ ] **Step 7: Commit database foundation**

Run:

```bash
git add backend/alembic.ini backend/app/db backend/migrations backend/tests
git commit -m "feat: add sqlite schema and migrations"
```

Expected: commit created.

---

### Task 3: Telegram WebApp Auth, Sessions, CSRF, And Access

**Files:**
- Create: `backend/app/core/security.py`
- Create: `backend/app/core/errors.py`
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/services/auth.py`
- Create: `backend/app/services/sessions.py`
- Create: `backend/app/services/access.py`
- Create: `backend/app/telegram/client.py`
- Create: `backend/app/routers/auth.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_telegram_init_data.py`
- Create: `backend/tests/test_auth_api.py`

- [ ] **Step 1: Write Telegram initData verifier tests**

Create `backend/tests/test_telegram_init_data.py`:

```python
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
            "user": json.dumps({"id": 123, "username": "ivan", "first_name": "Ivan"}, separators=(",", ":")),
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
```

- [ ] **Step 2: Implement verifier**

Create `backend/app/services/auth.py`:

```python
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import parse_qsl


class InitDataError(ValueError):
    pass


@dataclass(frozen=True)
class TelegramUserPayload:
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    language_code: str | None
    photo_url: str | None


def verify_telegram_init_data(
    *,
    init_data: str,
    bot_token: str,
    now: datetime,
    max_age_seconds: int,
) -> TelegramUserPayload:
    pairs = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise InitDataError("missing hash")

    auth_date_raw = pairs.get("auth_date")
    if not auth_date_raw:
        raise InitDataError("missing auth_date")

    try:
        auth_timestamp = int(auth_date_raw)
    except ValueError as exc:
        raise InitDataError("invalid auth_date") from exc

    age_seconds = int(now.timestamp()) - auth_timestamp
    if age_seconds < 0 or age_seconds > max_age_seconds:
        raise InitDataError("expired auth_date")

    data_check_string = "\n".join(f"{key}={pairs[key]}" for key in sorted(pairs))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated_hash, received_hash):
        raise InitDataError("invalid hash")

    try:
        user_data = json.loads(pairs["user"])
    except (KeyError, json.JSONDecodeError) as exc:
        raise InitDataError("invalid user") from exc

    telegram_id = user_data.get("id")
    if not isinstance(telegram_id, int):
        raise InitDataError("invalid user id")

    return TelegramUserPayload(
        telegram_id=telegram_id,
        username=user_data.get("username"),
        first_name=user_data.get("first_name"),
        last_name=user_data.get("last_name"),
        language_code=user_data.get("language_code"),
        photo_url=user_data.get("photo_url"),
    )
```

- [ ] **Step 3: Run verifier tests**

Run:

```bash
cd backend
.venv/bin/pytest tests/test_telegram_init_data.py -v
```

Expected: all tests pass.

- [ ] **Step 4: Implement auth API schemas and errors**

Create `backend/app/core/errors.py`:

```python
class AppError(Exception):
    status_code = 400
    code = "app_error"

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"
```

Create `backend/app/schemas/auth.py`:

```python
from pydantic import BaseModel, Field


class TelegramWebAppAuthRequest(BaseModel):
    init_data: str = Field(min_length=1)


class UserResponse(BaseModel):
    id: int
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    is_admin: bool
    is_banned: bool


class RequiredChannelResponse(BaseModel):
    chat_id: str
    title: str | None
    is_member: bool


class AccessResponse(BaseModel):
    allowed: bool
    required_channels: list[RequiredChannelResponse] = []
    missing_channels: list[RequiredChannelResponse] = []


class AuthResponse(BaseModel):
    user: UserResponse
    access: AccessResponse
    csrf_token: str
```

- [ ] **Step 5: Implement session and CSRF helpers**

Create `backend/app/core/security.py`:

```python
import hashlib
import secrets


def new_session_id() -> str:
    return secrets.token_urlsafe(48)


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def hash_ip(ip_address: str | None, secret: str) -> str | None:
    if not ip_address:
        return None
    return hashlib.sha256(f"{secret}:{ip_address}".encode()).hexdigest()
```

Create `backend/app/services/sessions.py` with functions:

```python
from datetime import timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import new_csrf_token, new_session_id
from app.core.time import utc_now
from app.db.models import Session as DbSession


async def create_session(db: AsyncSession, *, user_id: int, ttl_seconds: int, user_agent: str | None, ip_hash: str | None) -> tuple[str, str]:
    now = utc_now()
    session_id = new_session_id()
    csrf_token = new_csrf_token()
    db.add(
        DbSession(
            id=session_id,
            user_id=user_id,
            expires_at=now + timedelta(seconds=ttl_seconds),
            created_at=now,
            last_used_at=now,
            user_agent=user_agent,
            ip_hash=ip_hash,
        )
    )
    await db.flush()
    return session_id, csrf_token
```

Store the CSRF token in a signed, readable cookie named `csrf_token` and require clients to echo it in `X-CSRF-Token` for mutating endpoints. Do not store CSRF token in `sessions` unless the implementation adds a `csrf_token_hash` migration.

- [ ] **Step 6: Implement access service with Telegram client protocol**

Create `backend/app/telegram/client.py`:

```python
from dataclasses import dataclass
import httpx


@dataclass(frozen=True)
class ChatMemberResult:
    status: str
    raw: dict


class TelegramBotApiClient:
    def __init__(self, *, token: str, timeout_seconds: float = 10.0) -> None:
        self._base_url = f"https://api.telegram.org/bot{token}"
        self._timeout_seconds = timeout_seconds

    async def get_chat_member(self, *, chat_id: str, user_id: int) -> ChatMemberResult:
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            response = await client.post(
                f"{self._base_url}/getChatMember",
                json={"chat_id": chat_id, "user_id": user_id},
            )
            response.raise_for_status()
            payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError("telegram getChatMember returned not ok")
        result = payload["result"]
        return ChatMemberResult(status=result["status"], raw=result)
```

Create `backend/app/services/access.py` with `ensure_required_channels(db, user, settings, telegram_client)` returning `AccessResponse`. It must seed `required_channels` from env when missing, use cache while `expires_at > now`, and write cache rows after Telegram checks.

- [ ] **Step 7: Write auth API tests**

Create `backend/tests/test_auth_api.py` with tests:

```python
def test_auth_rejects_tampered_init_data(client) -> None:
    response = client.post("/api/auth/telegram-webapp", json={"init_data": "auth_date=1&hash=bad"})
    assert response.status_code == 401


def test_me_requires_session(client) -> None:
    response = client.get("/api/auth/me")
    assert response.status_code == 401
```

Add this `client` fixture to `backend/tests/conftest.py`:

```python
from fastapi.testclient import TestClient
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.main import create_app


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        session_secret="test_session_secret_that_is_long_enough",
        telegram_bot_token="123456:test",
        telegram_bot_username="test_bot",
        telegram_webhook_secret="test_webhook_secret",
        telegram_required_channels="",
        admin_telegram_ids="123",
    )


@pytest.fixture
def client(test_session, test_settings):
    app = create_app()

    async def override_session():
        yield test_session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings] = lambda: test_settings
    return TestClient(app)
```

- [ ] **Step 8: Implement auth router and wire app**

Create `backend/app/routers/auth.py`:

```python
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import Settings, get_settings
from app.core.errors import UnauthorizedError
from app.core.security import hash_ip
from app.core.time import utc_now
from app.db.session import get_session
from app.schemas.auth import AuthResponse, TelegramWebAppAuthRequest
from app.services.auth import InitDataError, verify_telegram_init_data

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/telegram-webapp", response_model=AuthResponse)
async def telegram_webapp_auth(
    payload: TelegramWebAppAuthRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    try:
        telegram_user = verify_telegram_init_data(
            init_data=payload.init_data,
            bot_token=settings.telegram_bot_token.get_secret_value(),
            now=utc_now(),
            max_age_seconds=settings.max_init_data_age_seconds,
        )
    except InitDataError as exc:
        raise UnauthorizedError("invalid telegram init data") from exc

    ip_hash = hash_ip(request.client.host if request.client else None, settings.session_secret.get_secret_value())
    user = await upsert_telegram_user(db, telegram_user=telegram_user, admin_ids=settings.admin_ids)
    access = await build_access_response(db, user=user, settings=settings)
    session_id, csrf_token = await create_session(
        db,
        user_id=user.id,
        ttl_seconds=settings.session_ttl_seconds,
        user_agent=request.headers.get("user-agent"),
        ip_hash=ip_hash,
    )
    await db.commit()
    response.set_cookie(
        settings.session_cookie_name,
        session_id,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
        path="/",
        max_age=settings.session_ttl_seconds,
    )
    response.set_cookie(
        "csrf_token",
        csrf_token,
        httponly=False,
        secure=settings.app_env == "production",
        samesite="lax",
        path="/",
        max_age=settings.session_ttl_seconds,
    )
    return AuthResponse(user=to_user_response(user), access=access, csrf_token=csrf_token)
```

Create `upsert_telegram_user`, `to_user_response`, `build_access_response`, and `create_session` in the service modules named earlier in this task. Wire router in `backend/app/main.py` and add an exception handler for `AppError`.

- [ ] **Step 9: Run auth tests and full backend tests**

Run:

```bash
cd backend
.venv/bin/pytest tests/test_telegram_init_data.py tests/test_auth_api.py -v
.venv/bin/pytest -v
.venv/bin/ruff check app tests
```

Expected: all backend tests pass and Ruff passes.

- [ ] **Step 10: Commit auth slice**

Run:

```bash
git add backend/app backend/tests
git commit -m "feat: add telegram webapp auth and sessions"
```

Expected: commit created.

---

### Task 4: Ads API And Contact Attempt Flow

**Files:**
- Create: `backend/app/schemas/ads.py`
- Create: `backend/app/services/ads.py`
- Create: `backend/app/services/contacts.py`
- Create: `backend/app/routers/ads.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_ads_api.py`
- Create: `backend/tests/test_contact_attempts.py`

- [ ] **Step 1: Write ad validation and ownership tests**

Create `backend/tests/test_ads_api.py` with tests that create authenticated users through fixtures:

```python
async def test_create_ad_rejects_same_currency(auth_client) -> None:
    response = await auth_client.post(
        "/api/ads",
        json={
            "side": "SELL",
            "base_currency": "USD",
            "quote_currency": "USD",
            "amount": "1000",
            "rate": "92.50",
        },
        headers={"X-CSRF-Token": auth_client.csrf_token},
    )
    assert response.status_code == 422


async def test_user_cannot_revoke_other_users_ad(auth_client, other_user_ad) -> None:
    response = await auth_client.post(
        f"/api/ads/{other_user_ad.id}/revoke",
        headers={"X-CSRF-Token": auth_client.csrf_token},
    )
    assert response.status_code == 403
```

- [ ] **Step 2: Create ad schemas**

Create `backend/app/schemas/ads.py`:

```python
from decimal import Decimal
from pydantic import BaseModel, Field, model_validator
from typing import Literal

Currency = Literal["USD", "EUR", "RUB", "USDT", "USDC"]
AdSide = Literal["BUY", "SELL"]
AdStatus = Literal["ACTIVE", "REVOKED", "HIDDEN", "EXPIRED", "COMPLETED"]


class AdCreateRequest(BaseModel):
    side: AdSide
    base_currency: Currency
    quote_currency: Currency
    amount: Decimal = Field(gt=0)
    min_amount: Decimal | None = Field(default=None, gt=0)
    max_amount: Decimal | None = Field(default=None, gt=0)
    rate: Decimal = Field(gt=0)
    payment_method: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=120)
    comment: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_pair_and_limits(self) -> "AdCreateRequest":
        if self.base_currency == self.quote_currency:
            raise ValueError("base_currency and quote_currency must differ")
        if self.min_amount is not None and self.max_amount is not None and self.min_amount > self.max_amount:
            raise ValueError("min_amount cannot exceed max_amount")
        return self


class AdResponse(BaseModel):
    id: int
    user_id: int
    side: AdSide
    base_currency: Currency
    quote_currency: Currency
    amount: str
    min_amount: str | None
    max_amount: str | None
    rate: str
    payment_method: str | None
    location: str | None
    comment: str | None
    status: AdStatus
    author_username: str | None
    is_own: bool


class AdCreateResponse(BaseModel):
    id: int
    status: AdStatus
```

- [ ] **Step 3: Implement ads service**

Create `backend/app/services/ads.py` with functions:

```python
from datetime import timedelta
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.errors import ForbiddenError
from app.core.time import utc_now
from app.db.models import Ad
from app.schemas.ads import AdCreateRequest


async def create_ad(db: AsyncSession, *, user_id: int, payload: AdCreateRequest, max_active: int, ttl_hours: int) -> Ad:
    active_count = await db.scalar(
        select(func.count()).select_from(Ad).where(Ad.user_id == user_id, Ad.status == "ACTIVE")
    )
    if int(active_count or 0) >= max_active:
        raise ForbiddenError("active ad limit reached")
    now = utc_now()
    ad = Ad(
        user_id=user_id,
        side=payload.side,
        base_currency=payload.base_currency,
        quote_currency=payload.quote_currency,
        amount=payload.amount,
        min_amount=payload.min_amount,
        max_amount=payload.max_amount,
        rate=payload.rate,
        payment_method=payload.payment_method,
        location=payload.location,
        comment=payload.comment,
        status="ACTIVE",
        expires_at=now + timedelta(hours=ttl_hours),
        created_at=now,
        updated_at=now,
    )
    db.add(ad)
    await db.flush()
    return ad


async def revoke_ad(db: AsyncSession, *, ad_id: int, user_id: int) -> Ad:
    ad = await db.get(Ad, ad_id)
    if ad is None:
        raise ForbiddenError("ad is not available")
    if ad.user_id != user_id:
        raise ForbiddenError("cannot revoke another user's ad")
    now = utc_now()
    ad.status = "REVOKED"
    ad.revoked_at = now
    ad.updated_at = now
    await db.flush()
    return ad
```

- [ ] **Step 4: Write contact cancellation tests**

Create `backend/tests/test_contact_attempts.py`:

```python
async def test_new_contact_cancels_previous_pending_followup(test_session, user, author, first_ad, second_ad) -> None:
    from app.services.contacts import create_contact_attempt

    first = await create_contact_attempt(test_session, initiator=user, ad=first_ad, delay_hours=2)
    second = await create_contact_attempt(test_session, initiator=user, ad=second_ad, delay_hours=2)

    await test_session.refresh(first)
    assert first.status == "CANCELED_BY_NEW_CONTACT"
    assert second.status == "OPENED"
```

- [ ] **Step 5: Implement contact service**

Create `backend/app/services/contacts.py`:

```python
from datetime import timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.errors import ForbiddenError
from app.core.time import utc_now
from app.db.models import Ad, ContactAttempt, User


async def create_contact_attempt(db: AsyncSession, *, initiator: User, ad: Ad, delay_hours: int) -> ContactAttempt:
    if ad.user_id == initiator.id:
        raise ForbiddenError("cannot contact yourself")
    if ad.status != "ACTIVE":
        raise ForbiddenError("ad is not active")

    author = await db.get(User, ad.user_id)
    if author is None or not author.username:
        raise ForbiddenError("contact unavailable")

    now = utc_now()
    previous_attempts = await db.scalars(
        select(ContactAttempt).where(
            ContactAttempt.initiator_user_id == initiator.id,
            ContactAttempt.status == "OPENED",
        )
    )
    for attempt in previous_attempts:
        attempt.status = "CANCELED_BY_NEW_CONTACT"
        attempt.updated_at = now

    contact = ContactAttempt(
        initiator_user_id=initiator.id,
        author_user_id=author.id,
        ad_id=ad.id,
        status="OPENED",
        followup_due_at=now + timedelta(hours=delay_hours),
        created_at=now,
        updated_at=now,
    )
    db.add(contact)
    await db.flush()
    return contact
```

- [ ] **Step 6: Implement ads router**

Create `backend/app/routers/ads.py` with these route signatures and service calls:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import Settings, get_settings
from app.core.limits import check_rate_limit
from app.db.session import get_session
from app.schemas.ads import AdCreateRequest, AdCreateResponse
from app.services.ads import create_ad, revoke_ad
from app.services.auth import require_current_user, require_csrf
from app.services.contacts import create_contact_attempt

router = APIRouter(prefix="/api/ads", tags=["ads"])


@router.post("", response_model=AdCreateResponse)
async def create_ad_endpoint(
    payload: AdCreateRequest,
    db: AsyncSession = Depends(get_session),
    user=Depends(require_current_user),
    _csrf=Depends(require_csrf),
    settings: Settings = Depends(get_settings),
) -> AdCreateResponse:
    await check_rate_limit(db, key=f"user:{user.id}", action="ad_create", limit=5, window_seconds=3600)
    ad = await create_ad(db, user_id=user.id, payload=payload, max_active=settings.max_active_ads_per_user, ttl_hours=settings.ad_default_ttl_hours)
    await db.commit()
    return AdCreateResponse(id=ad.id, status=ad.status)


@router.post("/{ad_id}/revoke")
async def revoke_ad_endpoint(
    ad_id: int,
    db: AsyncSession = Depends(get_session),
    user=Depends(require_current_user),
    _csrf=Depends(require_csrf),
):
    ad = await revoke_ad(db, ad_id=ad_id, user_id=user.id)
    await db.commit()
    return {"id": ad.id, "status": ad.status}


@router.post("/{ad_id}/contact")
async def contact_ad_endpoint(
    ad_id: int,
    db: AsyncSession = Depends(get_session),
    user=Depends(require_current_user),
    _csrf=Depends(require_csrf),
    settings: Settings = Depends(get_settings),
):
    ad = await get_active_ad_or_404(db, ad_id=ad_id)
    contact = await create_contact_attempt(db, initiator=user, ad=ad, delay_hours=settings.deal_followup_delay_hours)
    author = await db.get(User, ad.user_id)
    await check_rate_limit(db, key=f"user:{user.id}", action="contact", limit=20, window_seconds=3600)
    await db.commit()
    return {"id": contact.id, "url": f"https://t.me/{author.username}"}
```

Add list/detail/my/update endpoints in the same router using `select(Ad)` queries that return only `ACTIVE` and non-expired ads for public board calls, and all current user's ads for `/my`.

- [ ] **Step 7: Run ads/contact tests**

Run:

```bash
cd backend
.venv/bin/pytest tests/test_ads_api.py tests/test_contact_attempts.py -v
.venv/bin/pytest -v
.venv/bin/ruff check app tests
```

Expected: all tests pass and Ruff passes.

- [ ] **Step 8: Commit ads slice**

Run:

```bash
git add backend/app backend/tests
git commit -m "feat: add ads and contact attempts"
```

Expected: commit created.

---

### Task 5: Reports, Admin Actions, Audit Log, And Rate Limits

**Files:**
- Create: `backend/app/core/limits.py`
- Create: `backend/app/schemas/reports.py`
- Create: `backend/app/services/audit.py`
- Create: `backend/app/services/reports.py`
- Create: `backend/app/routers/reports.py`
- Create: `backend/app/routers/admin.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_reports.py`
- Create: `backend/tests/test_admin.py`
- Create: `backend/tests/test_rate_limits.py`

- [ ] **Step 1: Write report behavior tests**

Create `backend/tests/test_reports.py`:

```python
async def test_user_cannot_report_self(auth_client, own_ad) -> None:
    response = await auth_client.post(
        "/api/reports",
        json={"ad_id": own_ad.id, "target_user_id": auth_client.user_id, "reason": "SCAM"},
        headers={"X-CSRF-Token": auth_client.csrf_token},
    )
    assert response.status_code == 400


async def test_three_unique_reports_hide_ad(reporter_clients, active_ad) -> None:
    for client in reporter_clients[:3]:
        response = await client.post(
            "/api/reports",
            json={"ad_id": active_ad.id, "target_user_id": active_ad.user_id, "reason": "SCAM"},
            headers={"X-CSRF-Token": client.csrf_token},
        )
        assert response.status_code == 200

    response = await reporter_clients[0].get(f"/api/ads/{active_ad.id}")
    assert response.status_code == 404
```

- [ ] **Step 2: Implement report schemas**

Create `backend/app/schemas/reports.py`:

```python
from typing import Literal
from pydantic import BaseModel, Field

ReportReason = Literal["SCAM", "SPAM", "WRONG_RATE", "OFFENSIVE", "DUPLICATE", "FAKE_CONTACT", "OTHER"]
ReportStatus = Literal["NEW", "IN_REVIEW", "RESOLVED", "REJECTED"]


class ReportCreateRequest(BaseModel):
    ad_id: int | None = None
    target_user_id: int
    reason: ReportReason
    comment: str | None = Field(default=None, max_length=500)


class ReportResponse(BaseModel):
    id: int
    status: ReportStatus
```

- [ ] **Step 3: Implement audit service**

Create `backend/app/services/audit.py`:

```python
import json
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.time import utc_now
from app.db.models import AuditLog


async def write_audit(
    db: AsyncSession,
    *,
    actor_user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | None,
    payload: dict,
    ip_hash: str | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            payload_json=json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
            ip_hash=ip_hash,
            created_at=utc_now(),
        )
    )
```

- [ ] **Step 4: Implement report service**

Create `backend/app/services/reports.py` with:

```python
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.errors import AppError
from app.core.time import utc_now
from app.db.models import Ad, Report
from app.schemas.reports import ReportCreateRequest
from app.services.audit import write_audit


async def create_report(db: AsyncSession, *, reporter_user_id: int, payload: ReportCreateRequest, auto_hide_threshold: int) -> Report:
    if reporter_user_id == payload.target_user_id:
        raise AppError("cannot report yourself")
    now = utc_now()
    report = Report(
        reporter_user_id=reporter_user_id,
        target_user_id=payload.target_user_id,
        ad_id=payload.ad_id,
        reason=payload.reason,
        comment=payload.comment,
        status="NEW",
        created_at=now,
        updated_at=now,
    )
    db.add(report)
    await db.flush()

    if payload.ad_id is not None:
        unique_count = await db.scalar(
            select(func.count(func.distinct(Report.reporter_user_id))).where(Report.ad_id == payload.ad_id)
        )
        ad = await db.get(Ad, payload.ad_id)
        if ad is not None:
            ad.report_count = int(unique_count or 0)
            if ad.status == "ACTIVE" and ad.report_count >= auto_hide_threshold:
                ad.status = "HIDDEN"
                ad.hidden_at = now
                ad.updated_at = now
                await write_audit(
                    db,
                    actor_user_id=None,
                    action="auto_hide_ad",
                    entity_type="ad",
                    entity_id=ad.id,
                    payload={"report_count": ad.report_count},
                )
    return report
```

- [ ] **Step 5: Implement rate limit service**

Create `backend/app/core/limits.py`:

```python
from datetime import timedelta
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.errors import ForbiddenError
from app.core.time import utc_now
from app.db.models import RateLimitEvent


async def check_rate_limit(
    db: AsyncSession,
    *,
    key: str,
    action: str,
    limit: int,
    window_seconds: int,
) -> None:
    now = utc_now()
    window_start = now - timedelta(seconds=window_seconds)
    await db.execute(delete(RateLimitEvent).where(RateLimitEvent.created_at < window_start))
    count = await db.scalar(
        select(func.count()).select_from(RateLimitEvent).where(
            RateLimitEvent.key == key,
            RateLimitEvent.action == action,
            RateLimitEvent.created_at >= window_start,
        )
    )
    if int(count or 0) >= limit:
        raise ForbiddenError("rate limit exceeded")
    db.add(RateLimitEvent(key=key, action=action, created_at=now))
```

- [ ] **Step 6: Implement reports and admin routers**

Create `backend/app/routers/reports.py` for `POST /api/reports`.

Create `backend/app/routers/admin.py` with:

```python
GET /api/admin/reports
PATCH /api/admin/reports/{id}
POST /api/admin/users/{id}/ban
POST /api/admin/users/{id}/unban
POST /api/admin/ads/{id}/hide
POST /api/admin/ads/{id}/restore
GET /api/admin/dashboard
GET /api/admin/audit-log
```

Each endpoint must require current user with `is_admin=true` and write `audit_log` for mutating actions.

- [ ] **Step 7: Run moderation tests**

Run:

```bash
cd backend
.venv/bin/pytest tests/test_reports.py tests/test_admin.py tests/test_rate_limits.py -v
.venv/bin/pytest -v
.venv/bin/ruff check app tests
```

Expected: all tests pass and Ruff passes.

- [ ] **Step 8: Commit moderation slice**

Run:

```bash
git add backend/app backend/tests
git commit -m "feat: add reports admin audit and rate limits"
```

Expected: commit created.

---

### Task 6: Rates, Telegram Webhook, And Notification Contracts

**Files:**
- Create: `backend/app/schemas/rates.py`
- Create: `backend/app/services/rates.py`
- Create: `backend/app/telegram/notifications.py`
- Create: `backend/app/routers/rates.py`
- Create: `backend/app/routers/telegram.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_rates.py`
- Create: `backend/tests/test_telegram_webhook.py`

- [ ] **Step 1: Write rates tests**

Create `backend/tests/test_rates.py`:

```python
async def test_rates_derives_stablecoin_pairs(test_session) -> None:
    from app.services.rates import derive_stablecoin_rates

    derived = derive_stablecoin_rates({"USD/RUB": "92.5000", "USD/EUR": "0.9200"})

    assert derived["USDT/USD"] == "1.0000"
    assert derived["USDC/USD"] == "1.0000"
    assert derived["USDT/RUB"] == "92.5000"
    assert derived["USDC/RUB"] == "92.5000"
    assert derived["USDT/EUR"] == "0.9200"
    assert derived["USDC/EUR"] == "0.9200"
```

- [ ] **Step 2: Implement rates service**

Create `backend/app/services/rates.py`:

```python
import csv
from decimal import Decimal, InvalidOperation
from io import StringIO


def parse_rates_csv(csv_text: str) -> dict[str, str]:
    reader = csv.DictReader(StringIO(csv_text))
    if reader.fieldnames is None or {"pair", "rate", "source", "updated_at"} - set(reader.fieldnames):
        raise ValueError("rates csv has invalid columns")
    rates: dict[str, str] = {}
    for row in reader:
        pair = row["pair"].strip().upper()
        try:
            rate = Decimal(row["rate"].strip())
        except InvalidOperation as exc:
            raise ValueError(f"invalid rate for {pair}") from exc
        if rate <= 0:
            raise ValueError(f"non-positive rate for {pair}")
        rates[pair] = f"{rate:.4f}"
    return rates


def derive_stablecoin_rates(base_rates: dict[str, str]) -> dict[str, str]:
    derived = {
        "USDT/USD": "1.0000",
        "USDC/USD": "1.0000",
    }
    if "USD/RUB" in base_rates:
        derived["USDT/RUB"] = base_rates["USD/RUB"]
        derived["USDC/RUB"] = base_rates["USD/RUB"]
    if "USD/EUR" in base_rates:
        derived["USDT/EUR"] = base_rates["USD/EUR"]
        derived["USDC/EUR"] = base_rates["USD/EUR"]
    return derived
```

Add async `get_rates(db, settings)` to `backend/app/services/rates.py`:

```python
from datetime import date
from zoneinfo import ZoneInfo
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.time import utc_now
from app.db.models import Rate
from app.schemas.rates import RateItem, RatesResponse


async def get_rates(db: AsyncSession, *, settings) -> RatesResponse:
    today = utc_now().astimezone(ZoneInfo(settings.rates_refresh_timezone)).date()
    existing = await db.scalars(select(Rate).where(Rate.rate_date == today).order_by(Rate.pair))
    rows = list(existing)
    if rows:
        return RatesResponse(
            date=today.isoformat(),
            source="googlefinance",
            is_stale=False,
            updated_at=max(row.fetched_at for row in rows).isoformat(),
            rates=[RateItem(pair=row.pair, rate=f"{row.rate:.4f}") for row in rows],
        )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(settings.google_rates_csv_url)
            response.raise_for_status()
        parsed = parse_rates_csv(response.text)
        parsed.update(derive_stablecoin_rates(parsed))
        now = utc_now()
        for pair, rate in parsed.items():
            db.add(Rate(pair=pair, rate=Decimal(rate), source="googlefinance", rate_date=today, fetched_at=now, raw_payload=response.text))
        await db.commit()
        return RatesResponse(
            date=today.isoformat(),
            source="googlefinance",
            is_stale=False,
            updated_at=now.isoformat(),
            rates=[RateItem(pair=pair, rate=rate) for pair, rate in sorted(parsed.items())],
        )
    except (httpx.HTTPError, ValueError):
        latest_date = await db.scalar(select(Rate.rate_date).order_by(Rate.rate_date.desc()).limit(1))
        if latest_date is None:
            raise
        stale_rows = list(await db.scalars(select(Rate).where(Rate.rate_date == latest_date).order_by(Rate.pair)))
        return RatesResponse(
            date=latest_date.isoformat(),
            source="googlefinance",
            is_stale=True,
            updated_at=max(row.fetched_at for row in stale_rows).isoformat(),
            rates=[RateItem(pair=row.pair, rate=f"{row.rate:.4f}") for row in stale_rows],
        )
```

- [ ] **Step 3: Implement rates schema/router**

Create `backend/app/schemas/rates.py`:

```python
from pydantic import BaseModel


class RateItem(BaseModel):
    pair: str
    rate: str


class RatesResponse(BaseModel):
    date: str
    source: str
    is_stale: bool
    updated_at: str
    rates: list[RateItem]
```

Create `backend/app/routers/rates.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.schemas.rates import RatesResponse
from app.services.rates import get_rates

router = APIRouter(prefix="/api/rates", tags=["rates"])


@router.get("", response_model=RatesResponse)
async def rates(db: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)) -> RatesResponse:
    return await get_rates(db, settings=settings)
```

- [ ] **Step 4: Write webhook secret test**

Create `backend/tests/test_telegram_webhook.py`:

```python
def test_webhook_rejects_missing_secret(client) -> None:
    response = client.post("/api/telegram/webhook", json={})
    assert response.status_code == 403
```

- [ ] **Step 5: Implement webhook router**

Create `backend/app/routers/telegram.py`:

```python
from fastapi import APIRouter, Depends, Header
from app.core.config import Settings, get_settings
from app.core.errors import ForbiddenError

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


@router.post("/webhook")
async def telegram_webhook(
    update: dict,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> dict[str, bool]:
    expected = settings.telegram_webhook_secret.get_secret_value()
    if x_telegram_bot_api_secret_token != expected:
        raise ForbiddenError("invalid telegram webhook secret")
    return {"ok": True}
```

- [ ] **Step 6: Run rates/webhook tests**

Run:

```bash
cd backend
.venv/bin/pytest tests/test_rates.py tests/test_telegram_webhook.py -v
.venv/bin/pytest -v
.venv/bin/ruff check app tests
```

Expected: all tests pass and Ruff passes.

- [ ] **Step 7: Commit rates/webhook slice**

Run:

```bash
git add backend/app backend/tests
git commit -m "feat: add rates and telegram webhook"
```

Expected: commit created.

---

### Task 7: Bot Commands, WebApp Buttons, And Deal Follow-Ups

**Files:**
- Create: `bot/fx_board_bot/backend_client.py`
- Create: `bot/fx_board_bot/callbacks.py`
- Create: `bot/fx_board_bot/commands.py`
- Create: `bot/fx_board_bot/followups.py`
- Modify: `bot/fx_board_bot/app.py`
- Create: `bot/tests/test_commands.py`
- Create: `bot/tests/test_callbacks.py`

- [ ] **Step 1: Write command config tests**

Create `bot/tests/test_commands.py`:

```python
from fx_board_bot.commands import public_commands, admin_commands


def test_public_commands_include_app_entrypoints() -> None:
    names = {command.command for command in public_commands()}
    assert {"/start", "/app", "/new", "/sell", "/buy", "/my_ads", "/rates", "/channels", "/rules", "/help", "/support", "/report"} <= names


def test_admin_commands_are_separate() -> None:
    names = {command.command for command in admin_commands()}
    assert {"/admin", "/reports", "/ban", "/unban", "/stats"} <= names
```

- [ ] **Step 2: Implement command definitions and keyboards**

Create `bot/fx_board_bot/commands.py`:

```python
from aiogram.types import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo


def public_commands() -> list[BotCommand]:
    return [
        BotCommand(command="start", description="Открыть FX Board"),
        BotCommand(command="app", description="Открыть приложение"),
        BotCommand(command="new", description="Создать объявление"),
        BotCommand(command="sell", description="Создать продажу"),
        BotCommand(command="buy", description="Создать покупку"),
        BotCommand(command="my_ads", description="Мои объявления"),
        BotCommand(command="rates", description="Курсы валют"),
        BotCommand(command="channels", description="Обязательные каналы"),
        BotCommand(command="rules", description="Правила"),
        BotCommand(command="help", description="Помощь"),
        BotCommand(command="support", description="Поддержка"),
        BotCommand(command="report", description="Жалобы"),
    ]


def admin_commands() -> list[BotCommand]:
    return [
        BotCommand(command="admin", description="Админ-панель"),
        BotCommand(command="reports", description="Новые репорты"),
        BotCommand(command="ban", description="Заблокировать пользователя"),
        BotCommand(command="unban", description="Разблокировать пользователя"),
        BotCommand(command="stats", description="Статистика"),
    ]


def webapp_keyboard(*, base_url: str, start_param: str | None = None) -> InlineKeyboardMarkup:
    url = f"{base_url.rstrip('/')}/app"
    if start_param:
        url = f"{url}?startapp={start_param}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть доску", web_app=WebAppInfo(url=url))]
        ]
    )
```

- [ ] **Step 3: Implement backend client**

Create `bot/fx_board_bot/backend_client.py`:

```python
import httpx


class BackendClient:
    def __init__(self, *, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    async def claim_due_followups(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(f"{self._base_url}/api/internal/contact-followups/claim")
            response.raise_for_status()
            return response.json()["items"]

    async def answer_followup(self, *, contact_attempt_id: int, actor_telegram_id: int, answer: str) -> dict:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self._base_url}/api/internal/contact-followups/{contact_attempt_id}/answer",
                json={"actor_telegram_id": actor_telegram_id, "answer": answer},
            )
            response.raise_for_status()
            return response.json()
```

Add internal backend endpoints in `backend/app/routers/telegram.py` guarded by `X-Internal-Bot-Secret`:

```python
@router.post("/internal/contact-followups/claim")
async def claim_contact_followups(
    x_internal_bot_secret: str | None = Header(default=None),
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    if x_internal_bot_secret != settings.telegram_webhook_secret.get_secret_value():
        raise ForbiddenError("invalid internal bot secret")
    items = await claim_due_contact_attempts(db)
    await db.commit()
    return {"items": items}


@router.post("/internal/contact-followups/{contact_attempt_id}/answer")
async def answer_contact_followup(
    contact_attempt_id: int,
    payload: dict,
    x_internal_bot_secret: str | None = Header(default=None),
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    if x_internal_bot_secret != settings.telegram_webhook_secret.get_secret_value():
        raise ForbiddenError("invalid internal bot secret")
    result = await apply_contact_answer(
        db,
        contact_attempt_id=contact_attempt_id,
        actor_telegram_id=int(payload["actor_telegram_id"]),
        answer=str(payload["answer"]),
    )
    await db.commit()
    return result
```

- [ ] **Step 4: Implement follow-up callback payloads**

Create `bot/fx_board_bot/callbacks.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class DealCallback:
    contact_attempt_id: int
    answer: str


def encode_deal_callback(*, contact_attempt_id: int, answer: str) -> str:
    return f"deal:{contact_attempt_id}:{answer}"


def decode_deal_callback(value: str) -> DealCallback:
    prefix, raw_id, answer = value.split(":", 2)
    if prefix != "deal" or answer not in {"yes", "no"}:
        raise ValueError("invalid deal callback")
    return DealCallback(contact_attempt_id=int(raw_id), answer=answer)
```

Create `bot/tests/test_callbacks.py`:

```python
from fx_board_bot.callbacks import decode_deal_callback, encode_deal_callback


def test_deal_callback_round_trip() -> None:
    encoded = encode_deal_callback(contact_attempt_id=55, answer="yes")
    decoded = decode_deal_callback(encoded)
    assert decoded.contact_attempt_id == 55
    assert decoded.answer == "yes"
```

- [ ] **Step 5: Wire bot handlers**

Modify `bot/fx_board_bot/app.py` so it:

```python
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from .callbacks import decode_deal_callback
from .commands import public_commands, webapp_keyboard
from .config import get_bot_settings


WELCOME_TEXT = (
    "Добро пожаловать в FX Board.\n\n"
    "Здесь можно размещать объявления о покупке и продаже USD, EUR, RUB, USDT и USDC.\n\n"
    "Для доступа нужно состоять в обязательных каналах.\n"
    "Нажмите кнопку ниже, чтобы открыть приложение."
)


async def start_handler(message: Message) -> None:
    settings = get_bot_settings()
    await message.answer(WELCOME_TEXT, reply_markup=webapp_keyboard(base_url=settings.app_base_url))


async def deal_callback_handler(callback: CallbackQuery) -> None:
    payload = decode_deal_callback(callback.data or "")
    await callback.answer("Ответ принят")
```

Register all public commands and admin command guards. Add a background polling loop in `followups.py` that claims due follow-ups every 60 seconds and sends inline yes/no buttons to the correct Telegram user.

- [ ] **Step 6: Run bot tests**

Run:

```bash
cd bot
.venv/bin/pytest -v
.venv/bin/ruff check fx_board_bot tests
```

Expected: all tests pass and Ruff passes.

- [ ] **Step 7: Commit bot slice**

Run:

```bash
git add bot backend/app/routers/telegram.py backend/app/services/contacts.py backend/tests
git commit -m "feat: add bot commands and deal followups"
```

Expected: commit created.

---

### Task 8: Nuxt Auth Gate, Board UI, Forms, Reports, Rates, And Admin UI

**Files:**
- Create: `frontend/types/api.ts`
- Create: `frontend/composables/useApi.ts`
- Create: `frontend/composables/useTelegram.ts`
- Create: `frontend/components/AppShell.vue`
- Create: `frontend/components/TelegramAuthGate.vue`
- Create: `frontend/components/AccessDeniedScreen.vue`
- Create: `frontend/components/RatesWidget.vue`
- Create: `frontend/components/AdsBoard.vue`
- Create: `frontend/components/AdsColumn.vue`
- Create: `frontend/components/AdCard.vue`
- Create: `frontend/components/AdCreateForm.vue`
- Create: `frontend/components/MyAdsList.vue`
- Create: `frontend/components/ReportModal.vue`
- Create: `frontend/components/CurrencySelector.vue`
- Create: `frontend/components/AmountInput.vue`
- Create: `frontend/components/RateInput.vue`
- Create: `frontend/components/ChannelJoinCard.vue`
- Create: `frontend/components/BottomNavigation.vue`
- Create: `frontend/components/AdminReportList.vue`
- Create: `frontend/pages/index.vue`
- Create: `frontend/pages/app/index.vue`
- Create: `frontend/pages/app/new.vue`
- Create: `frontend/pages/app/my.vue`
- Create: `frontend/pages/app/ad/[id].vue`
- Create: `frontend/pages/app/report/[id].vue`
- Create: `frontend/pages/app/rates.vue`
- Create: `frontend/pages/app/rules.vue`
- Create: `frontend/pages/app/access-denied.vue`
- Create: `frontend/pages/app/admin.vue`
- Create: `frontend/playwright.config.ts`
- Create: `frontend/tests/e2e/app-shell.spec.ts`
- Create: `frontend/tests/auth-gate.spec.ts`

- [ ] **Step 1: Create frontend API types**

Create `frontend/types/api.ts`:

```ts
export type Currency = 'USD' | 'EUR' | 'RUB' | 'USDT' | 'USDC'
export type AdSide = 'BUY' | 'SELL'
export type AdStatus = 'ACTIVE' | 'REVOKED' | 'HIDDEN' | 'EXPIRED' | 'COMPLETED'

export interface UserResponse {
  id: number
  telegram_id?: number
  username: string | null
  first_name?: string | null
  last_name?: string | null
  is_admin?: boolean
  is_banned?: boolean
}

export interface AccessResponse {
  allowed: boolean
  required_channels: Array<{ chat_id: string; title: string | null; is_member: boolean }>
  missing_channels: Array<{ chat_id: string; title: string | null; is_member: boolean }>
}

export interface AuthResponse {
  user: UserResponse
  access: AccessResponse
  csrf_token: string
}

export interface AdResponse {
  id: number
  user_id: number
  side: AdSide
  base_currency: Currency
  quote_currency: Currency
  amount: string
  min_amount: string | null
  max_amount: string | null
  rate: string
  payment_method: string | null
  location: string | null
  comment: string | null
  status: AdStatus
  author_username: string | null
  is_own: boolean
}
```

- [ ] **Step 2: Implement API composable**

Create `frontend/composables/useApi.ts`:

```ts
export function useApi() {
  const config = useRuntimeConfig()
  const csrfToken = useState<string | null>('csrf-token', () => null)

  async function apiFetch<T>(path: string, options: Parameters<typeof $fetch<T>>[1] = {}) {
    const headers = new Headers(options.headers as HeadersInit | undefined)
    if (csrfToken.value) {
      headers.set('X-CSRF-Token', csrfToken.value)
    }
    return await $fetch<T>(`${config.public.apiBase}${path}`, {
      credentials: 'include',
      ...options,
      headers
    })
  }

  return { apiFetch, csrfToken }
}
```

- [ ] **Step 3: Implement Telegram composable**

Create `frontend/composables/useTelegram.ts`:

```ts
declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        initData: string
        startParam?: string
        colorScheme?: 'light' | 'dark'
        themeParams?: Record<string, string>
        ready: () => void
        expand: () => void
        openTelegramLink?: (url: string) => void
        close?: () => void
      }
    }
  }
}

export function useTelegram() {
  const webApp = computed(() => import.meta.client ? window.Telegram?.WebApp ?? null : null)

  function openTelegramLink(url: string) {
    const tg = window.Telegram?.WebApp
    if (tg?.openTelegramLink) {
      tg.openTelegramLink(url)
      return
    }
    window.location.href = url
  }

  return { webApp, openTelegramLink }
}
```

- [ ] **Step 4: Implement TelegramAuthGate**

Create `frontend/components/TelegramAuthGate.vue`:

```vue
<script setup lang="ts">
import type { AuthResponse } from '~/types/api'

const { webApp } = useTelegram()
const { apiFetch, csrfToken } = useApi()
const auth = useState<AuthResponse | null>('auth', () => null)
const loading = ref(true)
const outsideTelegram = ref(false)
const error = ref<string | null>(null)

onMounted(async () => {
  const tg = webApp.value
  if (!tg?.initData) {
    outsideTelegram.value = true
    loading.value = false
    return
  }
  tg.ready()
  tg.expand()
  try {
    const response = await apiFetch<AuthResponse>('/auth/telegram-webapp', {
      method: 'POST',
      body: { init_data: tg.initData }
    })
    csrfToken.value = response.csrf_token
    auth.value = response
    if (!response.access.allowed) {
      await navigateTo('/app/access-denied')
    }
  } catch {
    error.value = 'Не удалось авторизоваться через Telegram'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div v-if="loading" class="auth-state">Загрузка...</div>
  <AccessDeniedScreen v-else-if="outsideTelegram" mode="outside-telegram" />
  <div v-else-if="error" class="auth-state auth-state--error">{{ error }}</div>
  <slot v-else />
</template>
```

- [ ] **Step 5: Implement shell and board components**

Create `frontend/components/AppShell.vue`, `AdsBoard.vue`, `AdsColumn.vue`, `AdCard.vue`, and `BottomNavigation.vue`. `AdsBoard.vue` must use a two-column CSS grid above `768px` and a segmented control below `768px`.

Use this core board CSS in `frontend/assets/css/main.css`:

```css
.board-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.mobile-segments {
  display: none;
}

@media (max-width: 767px) {
  .board-grid {
    grid-template-columns: 1fr;
  }

  .mobile-segments {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }

  .desktop-only {
    display: none;
  }
}
```

- [ ] **Step 6: Implement pages**

Create all pages listed in the files section. `frontend/pages/index.vue` redirects to `/app`:

```vue
<script setup lang="ts">
await navigateTo('/app')
</script>
```

Wrap `/app` pages in `TelegramAuthGate` and `AppShell`. `frontend/pages/app/index.vue` must fetch `/api/ads` and `/api/rates` on mount.

- [ ] **Step 7: Implement contact button behavior**

In `AdCard.vue`, call:

```ts
const response = await apiFetch<{ url: string }>(`/ads/${props.ad.id}/contact`, { method: 'POST' })
openTelegramLink(response.url)
```

If API returns contact unavailable, render `Контакт недоступен` and do not open a link.

- [ ] **Step 8: Run frontend tests/build**

Create `frontend/playwright.config.ts`:

```ts
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  webServer: {
    command: 'npm run dev -- --port 3000',
    url: 'http://127.0.0.1:3000',
    reuseExistingServer: true
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 900 } } },
    { name: 'mobile', use: { ...devices['Pixel 7'] } }
  ]
})
```

Create `frontend/tests/e2e/app-shell.spec.ts`:

```ts
import { expect, test } from '@playwright/test'

test('renders dark shell outside Telegram', async ({ page }) => {
  await page.goto('/app')
  await expect(page.locator('body')).toHaveCSS('background-color', 'rgb(11, 15, 20)')
  await expect(page.getByText('Откройте сервис через Telegram-бота')).toBeVisible()
})
```

Run:

```bash
cd frontend
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

Expected: Vitest passes, Nuxt build completes, and Playwright verifies the dark outside-Telegram shell on desktop and mobile projects.

- [ ] **Step 9: Commit frontend slice**

Run:

```bash
git add frontend
git commit -m "feat: add telegram webapp frontend"
```

Expected: commit created.

---

### Task 9: Docker Compose, Deployment Docs, And Smoke Checks

**Files:**
- Create: `docker/backend.Dockerfile`
- Create: `docker/bot.Dockerfile`
- Create: `docker/frontend.Dockerfile`
- Create: `docker/compose.yml`
- Create: `docker/reverse-proxy.md`
- Modify: `README.md`

- [ ] **Step 1: Create backend Dockerfile**

Create `docker/backend.Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY backend/pyproject.toml /app/backend/pyproject.toml
RUN pip install --no-cache-dir -e /app/backend
COPY backend /app/backend
WORKDIR /app/backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Create bot Dockerfile**

Create `docker/bot.Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY bot/pyproject.toml /app/bot/pyproject.toml
RUN pip install --no-cache-dir -e /app/bot
COPY bot /app/bot
WORKDIR /app/bot
CMD ["python", "-m", "fx_board_bot.app"]
```

- [ ] **Step 3: Create frontend Dockerfile**

Create `docker/frontend.Dockerfile`:

```dockerfile
FROM node:22-slim AS build
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend .
RUN npm run build

FROM node:22-slim
WORKDIR /app
COPY --from=build /app/.output ./.output
CMD ["node", ".output/server/index.mjs"]
```

- [ ] **Step 4: Create Compose file**

Create `docker/compose.yml`:

```yaml
services:
  api:
    build:
      context: ..
      dockerfile: docker/backend.Dockerfile
    env_file:
      - ../.env
    volumes:
      - ../data:/app/backend/data
    ports:
      - "8000:8000"

  web:
    build:
      context: ..
      dockerfile: docker/frontend.Dockerfile
    environment:
      - NUXT_PUBLIC_API_BASE=/api
      - NUXT_PUBLIC_TELEGRAM_BOT_USERNAME=${TELEGRAM_BOT_USERNAME}
    ports:
      - "3000:3000"
    depends_on:
      - api

  bot:
    build:
      context: ..
      dockerfile: docker/bot.Dockerfile
    env_file:
      - ../.env
    depends_on:
      - api
```

- [ ] **Step 5: Create reverse proxy docs**

Create `docker/reverse-proxy.md`:

```markdown
# Reverse Proxy

Use one public domain for Telegram WebApp compatibility and cookie simplicity.

Example:

- `https://exchange.example.com/` -> `web:3000`
- `https://exchange.example.com/api` -> `api:8000`

Production requirements:

- HTTPS enabled.
- Forward `X-Forwarded-Proto` and `X-Forwarded-For`.
- Do not expose SQLite volume.
- Keep `TELEGRAM_BOT_TOKEN`, `SESSION_SECRET`, and `TELEGRAM_WEBHOOK_SECRET` only in environment variables.
```

- [ ] **Step 6: Run Docker smoke**

Run:

```bash
cp .env.example .env
docker compose -f docker/compose.yml build
docker compose -f docker/compose.yml up -d
curl -fsS http://localhost:8000/api/health
curl -fsS http://localhost:3000/
docker compose -f docker/compose.yml down
```

Expected: API health returns `{"status":"ok"}` and frontend returns HTML.

- [ ] **Step 7: Commit deployment slice**

Run:

```bash
git add docker README.md
git commit -m "chore: add docker compose deployment"
```

Expected: commit created.

---

### Task 10: Final Integration Verification

**Files:**
- Modify: files discovered by failed verification only
- Create: `docs/operations.md`

- [ ] **Step 1: Run backend full validation**

Run:

```bash
cd backend
.venv/bin/pytest -v
.venv/bin/ruff check app tests migrations
```

Expected: all tests pass and Ruff passes.

- [ ] **Step 2: Run bot full validation**

Run:

```bash
cd bot
.venv/bin/pytest -v
.venv/bin/ruff check fx_board_bot tests
```

Expected: all tests pass and Ruff passes.

- [ ] **Step 3: Run frontend full validation**

Run:

```bash
cd frontend
npm test
npm run build
```

Expected: tests pass and Nuxt build completes.

- [ ] **Step 4: Run Docker smoke validation**

Run:

```bash
docker compose -f docker/compose.yml build
docker compose -f docker/compose.yml up -d
curl -fsS http://localhost:8000/api/health
curl -fsS http://localhost:3000/
docker compose -f docker/compose.yml down
```

Expected: services build, boot, respond, and shut down cleanly.

- [ ] **Step 5: Create operational notes**

Create `docs/operations.md`:

```markdown
# Operations

## Required Telegram setup

- Create bot with BotFather.
- Configure Main Mini App URL.
- Configure menu button URL.
- Add bot as administrator to every required channel used in `TELEGRAM_REQUIRED_CHANNELS`.
- Set production webhook secret if webhook mode is enabled.

## Required Google Sheets setup

- Create a sheet named `rates`.
- Columns: `pair`, `rate`, `source`, `updated_at`.
- Publish sheet as CSV.
- Set `GOOGLE_RATES_CSV_URL`.

## Deployment

- Use one public HTTPS domain.
- Route `/` to frontend.
- Route `/api` to backend.
- Persist `./data` for SQLite.
- Keep secrets in environment variables only.
```

- [ ] **Step 6: Commit final docs**

Run:

```bash
git add docs/operations.md
git commit -m "docs: add operations guide"
```

Expected: commit created.

- [ ] **Step 7: Confirm clean worktree**

Run:

```bash
git status --short
```

Expected: no output.

## Self-Review Checklist

- Auth requirements map to Task 3.
- Channel membership requirements map to Task 3.
- Ads and contact follow-up requirements map to Task 4 and Task 7.
- Reports, moderation, audit, and rate limits map to Task 5.
- Rates and webhook security map to Task 6.
- Bot commands and follow-up callbacks map to Task 7.
- Nuxt SSR dark UI and TelegramAuthGate map to Task 8.
- Docker/Dokploy-style deployment map to Task 9.
- Final verification and operational docs map to Task 10.
