# FX Board Bot MVP Design

Date: 2026-05-22
Status: Approved design draft for implementation planning

## Scope

Build a full MVP of FX Board Bot in one monorepo. The project is a Telegram Mini App / WebApp currency classifieds board where Telegram users can publish buy/sell ads for USD, EUR, RUB, USDT, and USDC.

The MVP includes:

- FastAPI backend API.
- Nuxt Vue 3 SSR frontend.
- SQLite persistence.
- aiogram 3.x Telegram bot worker.
- Telegram Mini App `initData` authentication only.
- Required Telegram channel membership checks.
- Dark Telegram-oriented UI.
- Ads, reports, moderation, admin API/UI.
- Google Sheet based reference rates.
- Contact follow-up flow after a user opens chat with an ad author.
- Docker Compose deployment layout for one-domain reverse proxy.

The MVP excludes:

- Payments, escrow, KYC, AML checks, automatic trade execution.
- PostgreSQL, Redis, WebSocket/SSE, ratings, file attachments, multilingual UI.
- Legacy Telegram Login Widget or any auth based on untrusted frontend identity.

## Monorepo Shape

The repository will be organized by runtime boundary:

- `backend/`: FastAPI app, domain services, repositories, SQLite migrations, Telegram Bot API client, webhook endpoint, tests.
- `frontend/`: Nuxt Vue 3 SSR application, Telegram auth gate, dark board UI, admin UI, frontend tests.
- `bot/`: aiogram 3.x worker for commands, WebApp launch buttons, menu button setup, notifications, follow-up jobs.
- `docker/`: Dockerfiles, compose files, reverse-proxy examples, deployment notes.
- `docs/`: design, implementation plans, API contracts, operational notes.
- `data/`: local SQLite volume, ignored by git.

The backend is the only trusted authority for identity, access, ads, reports, rates, and moderation. Frontend code never treats `initDataUnsafe`, `telegram_id`, `username`, or arbitrary frontend-provided identity fields as trusted.

## Implementation Strategy

Use vertical MVP slices:

1. Auth and access: Telegram `initData` verification, session cookie, user upsert, channel membership cache.
2. Board and ads: create/list/detail/edit/revoke ads, active limits, expiry filtering.
3. Reports and admin: reports, auto-hide, admin actions, audit log.
4. Rates, bot, and deploy: lazy daily rates refresh, bot commands, notifications, Docker Compose.
5. Frontend polish and smoke validation: mobile/desktop layout, dark mode, auth/access states.

Each slice should be runnable and testable end-to-end before adding the next one.

## Backend Architecture

Use FastAPI with explicit internal boundaries:

- `routers`: HTTP request/response handling only.
- `services`: business rules and orchestration.
- `repositories`: SQLite persistence.
- `core`: config, security, time utilities, errors, logging.
- `telegram`: Telegram Bot API client, webhook validation, notification helpers.

The bot worker must not duplicate domain rules or write directly to SQLite. It should call backend APIs or shared backend service boundaries so command behavior and WebApp behavior cannot drift.

Use `SQLAlchemy 2.x async + aiosqlite` and Alembic migrations from the first slice. SQLite must be configured with:

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;
```

## Authentication And Sessions

Authentication uses only Telegram Mini App / WebApp `initData`.

Flow:

1. Nuxt renders a dark SSR shell without private user data.
2. Client-only `TelegramAuthGate` reads `window.Telegram.WebApp.initData`.
3. Frontend posts raw `initData` to `POST /api/auth/telegram-webapp`.
4. Backend parses query string, extracts `hash`, sorts remaining fields, builds `data_check_string`, derives the HMAC secret from bot token and `WebAppData`, and compares signatures with constant-time comparison.
5. Backend validates `auth_date` using `MAX_INIT_DATA_AGE_SECONDS=86400`.
6. Backend extracts Telegram user data from the verified payload.
7. Backend creates or updates `users`.
8. Backend sets `is_admin` based on `ADMIN_TELEGRAM_IDS`.
9. Backend rejects banned users.
10. Backend checks required Telegram channels.
11. Backend creates an opaque server-side session in `sessions`.
12. Backend sets `HttpOnly Secure SameSite=Lax Path=/` cookie.
13. Frontend calls `GET /api/auth/me` and renders the allowed or denied state.

Invalid, tampered, missing, or expired `initData` returns `401`. Banned users or missing channel membership return `403`. Telegram API failures must be logged without leaking tokens or raw internal errors to the user.

All mutating endpoints require:

- Valid session.
- CSRF token.
- Relevant access check.
- Relevant rate limit.

## Channel Access

Required channels come from:

```env
TELEGRAM_REQUIRED_CHANNELS=@channel_one,@channel_two
```

or private channel IDs:

```env
TELEGRAM_REQUIRED_CHANNELS=-1001234567890,-1009876543210
```

Membership checks use Telegram Bot API `getChatMember`. Member statuses are `creator`, `administrator`, and `member`. Non-member statuses are `left`, `kicked`, and `restricted`.

Membership results are cached in `user_channel_memberships` for 10 minutes. Checks run on:

- Telegram auth.
- `GET /api/auth/me` when cache is stale.
- Ad creation.
- Ad revoke.
- Report creation.
- Explicit “check access again” action from access denied UI.

The bot must be an administrator in required channels where Telegram requires it for reliable membership checks.

## Database Model

Use the schema from the product requirements, with these MVP additions:

- `rate_limit_events` for SQLite-backed rate limits.
- `contact_attempts` for tracked chat openings and deal follow-ups.
- `ads.status` includes `COMPLETED` in addition to `ACTIVE`, `REVOKED`, `HIDDEN`, and `EXPIRED`.

Core tables:

- `users`
- `sessions`
- `required_channels`
- `user_channel_memberships`
- `ads`
- `reports`
- `rates`
- `audit_log`
- `rate_limit_events`
- `contact_attempts`

`ads` are never physically deleted by normal user or follow-up flows. User revoke sets `REVOKED`. Moderator hide sets `HIDDEN`. Mutual deal confirmation sets `COMPLETED`. Expired listings are hidden from active listings by status or expiry filtering.

`contact_attempts.status` values:

- `OPENED`: user opened contact for an ad and follow-up is pending.
- `CANCELED_BY_NEW_CONTACT`: user opened another ad before the follow-up question was sent.
- `ASKED_INITIATOR`: bot has asked the initiating user whether the deal happened.
- `INITIATOR_NO_DEAL`: initiating user answered that no deal happened.
- `WAITING_AUTHOR_CONFIRMATION`: initiating user said yes and the bot is waiting for the ad author.
- `COMPLETED_CONFIRMED`: both sides confirmed completion and the ad was marked `COMPLETED`.
- `AUTHOR_REJECTED`: ad author rejected completion.
- `EXPIRED`: confirmation flow timed out.

## Ads

Ads support sides:

- `SELL`
- `BUY`

Allowed currencies:

- `USD`
- `EUR`
- `RUB`
- `USDT`
- `USDC`

Validation rules:

- `base_currency != quote_currency`.
- `amount > 0`.
- `rate > 0`.
- `comment` length is at most 500.
- String fields have explicit maximum lengths.
- One user can have at most `MAX_ACTIVE_ADS_PER_USER=10` active ads.
- Default ad lifetime is `AD_DEFAULT_TTL_HOURS=24`.

Only the author can edit or revoke an ad. Editable fields are:

- `amount`
- `min_amount`
- `max_amount`
- `rate`
- `payment_method`
- `location`
- `comment`
- `expires_at`

Immutable fields are:

- `side`
- `base_currency`
- `quote_currency`
- `user_id`

Active board queries show only active, non-expired ads. Desktop UI shows two columns: sale and buy. Mobile UI shows a segmented sale/buy switch and one selected list.

## Contact And Deal Follow-Up

Clicking “Написать” is a tracked backend action, not only a raw link.

Flow:

1. User clicks “Написать” on an active ad.
2. Frontend calls `POST /api/ads/{ad_id}/contact`.
3. Backend verifies the session, access, non-banned status, channel membership, active ad status, and that the user is not the ad author.
4. Backend verifies the ad author has a Telegram username. If not, the API returns a contact-unavailable response.
5. Backend cancels any previous pending contact follow-up for the same initiator if the previous follow-up has not yet asked the initiator. This implements the rule: if the user clicks another ad later, the first ad must not trigger a follow-up question.
6. Backend creates `contact_attempts` with `status=OPENED`, the initiator user, ad author, ad ID, and `followup_due_at = now + DEAL_FOLLOWUP_DELAY_HOURS`.
7. Frontend opens `https://t.me/<username>` using `Telegram.WebApp.openTelegramLink` when available, with normal link fallback.
8. Bot worker periodically claims due `contact_attempts`.
9. Bot asks the initiator: “Сделка состоялась?”
10. If the initiator answers no, the contact attempt closes without changing the ad.
11. If the initiator answers yes, the bot asks the ad author to confirm.
12. If the author confirms, backend sets `ads.status = COMPLETED`, records audit data, notifies participants, and removes the ad from the active board.
13. If the author rejects or does not answer before timeout, the ad remains active and the contact attempt closes as rejected or expired.

Configuration:

```env
DEAL_FOLLOWUP_DELAY_HOURS=2
```

Important Telegram boundary: the bot cannot close an ordinary private user-to-user chat that it does not own. “Close the chat” in this MVP means closing the app’s deal/contact process and removing the confirmed ad from the active board. The Mini App may close itself, and the bot may send its own messages, but it cannot forcibly close another private chat.

## Reports And Moderation

Users can report ads and users for:

- `SCAM`
- `SPAM`
- `WRONG_RATE`
- `OFFENSIVE`
- `DUPLICATE`
- `FAKE_CONTACT`
- `OTHER`

Report creation rules:

- User must be authenticated.
- User must not be banned.
- User must satisfy required channel access.
- User cannot report themselves.
- User cannot report the same ad twice.

After each report, backend counts unique reporters for the ad. When unique reports reach `REPORTS_TO_AUTO_HIDE=3`, backend sets `ads.status = HIDDEN`, writes `audit_log`, and notifies admins.

Admin actions include:

- View reports.
- Update report status.
- Ban and unban users.
- Hide and restore ads.
- Restore manually hidden or auto-hidden ads.
- View dashboard counts, rates status, and audit log.

All admin endpoints require `is_admin=true`. All admin and automatic moderation actions write `audit_log`.

## Rates

Rates use a published Google Sheet CSV backed by `GOOGLEFINANCE`.

`GET /api/rates` performs lazy daily refresh:

1. Determine current date in `RATES_REFRESH_TIMEZONE`.
2. If successful rates already exist for that date, return them.
3. Otherwise fetch `GOOGLE_RATES_CSV_URL`.
4. Validate expected columns: `pair`, `rate`, `source`, `updated_at`.
5. Parse rates as decimals.
6. Save fetched rates in `rates`.
7. Derive stablecoin MVP rates:
   - `USDT/USD = 1.0000`
   - `USDC/USD = 1.0000`
   - `USDT/RUB = USD/RUB`
   - `USDC/RUB = USD/RUB`
   - `USDT/EUR = USD/EUR`
   - `USDC/EUR = USD/EUR`
8. Return `is_stale=false`.

If Google fetch or validation fails, backend returns the latest saved rates with `is_stale=true` and sends an admin technical notification. If no saved rates exist, the API returns an explicit service error rather than fabricating values.

## Frontend

Use Nuxt Vue 3 SSR with TypeScript. Nuxt 3 is the default target for MVP stability. Nuxt 4 can be considered during implementation only if current tooling is stable and does not increase delivery risk.

Required pages:

- `/`
- `/app`
- `/app/new`
- `/app/my`
- `/app/ad/:id`
- `/app/report/:id`
- `/app/rates`
- `/app/rules`
- `/app/access-denied`
- `/app/admin`

Required components:

- `AppShell`
- `TelegramAuthGate`
- `AccessDeniedScreen`
- `RatesWidget`
- `AdsBoard`
- `AdsColumn`
- `AdCard`
- `AdCreateForm`
- `MyAdsList`
- `ReportModal`
- `CurrencySelector`
- `AmountInput`
- `RateInput`
- `ChannelJoinCard`
- `BottomNavigation`
- `AdminReportList`

Dark mode is the default and must be applied through CSS variables at document/root level to avoid white SSR hydration flash.

Base palette:

- Primary background: `#0B0F14`
- Secondary background: `#111827`
- Cards: `#161F2C`
- Border: `#263244`
- Primary text: `#E5E7EB`
- Secondary text: `#9CA3AF`
- Accent: `#38BDF8`
- Success: `#22C55E`
- Danger: `#EF4444`
- Warning: `#F59E0B`

Telegram `themeParams`, safe areas, and WebApp buttons may be mapped to system UI affordances, but the service remains dark even when Telegram reports a light theme.

If opened outside Telegram, the app shows “Откройте сервис через Telegram-бота” and a deep link:

```text
https://t.me/<bot_username>?startapp
```

No fallback to Telegram Login Widget is allowed.

## Bot Worker

Use aiogram 3.x.

Bot responsibilities:

- Register bot commands via `setMyCommands`.
- Configure menu button with WebApp URL.
- Handle `/start`, `/app`, `/new`, `/sell`, `/buy`, `/my_ads`, `/rates`, `/channels`, `/rules`, `/help`, `/support`, `/report`.
- Handle admin commands `/admin`, `/reports`, `/ban`, `/unban`, `/stats` only for `ADMIN_TELEGRAM_IDS`.
- Send user notifications.
- Send admin notifications.
- Process contact follow-up jobs.
- Process inline callback buttons for deal confirmations and admin shortcuts.

The bot should use backend APIs or backend service contracts for domain actions, rather than implementing duplicate database logic.

## Webhook

Backend exposes:

```http
POST /api/telegram/webhook
```

It must verify Telegram secret token header against:

```env
TELEGRAM_WEBHOOK_SECRET=...
```

Long-running work must not run inside the webhook request path. Production may use webhook mode. MVP Docker local/dev may use bot long polling, while keeping the webhook endpoint implemented and tested.

## Security

Required controls:

- HTTPS in production.
- Bot token only in environment variables.
- Bot token never exposed to frontend.
- No trust in `initDataUnsafe`.
- Constant-time compare for Telegram auth hash.
- `auth_date` TTL validation.
- Opaque server-side session cookie.
- CSRF token for mutating endpoints.
- SQLite-backed rate limits.
- Admin audit log.
- No public Telegram ID exposure.
- No self-report.
- No HTML rendering from user text.
- Explicit string length limits.
- Webhook secret token validation.

Minimum rate limits:

- Auth: 10/min per IP.
- Ad creation: 5/hour per user.
- Report creation: 10/day per user.
- Ad update: 30/hour per user.
- Channel checks: 10/10 min per user.
- Contact attempts: 20/hour per user.

## Deployment

Docker Compose services:

- `api`
- `web`
- `bot`

Use one public domain:

```text
https://exchange.example.com
```

Routing:

- `/` to `web:3000`
- `/api` to `api:8000`

Backend owns the SQLite volume:

```yaml
volumes:
  - ./data:/app/data
```

The project will include `.env.example` with all required configuration keys and deployment notes for Dokploy / Traefik / Nginx Proxy Manager.

## Validation Strategy

Backend tests:

- Telegram `initData` HMAC validation.
- Tampered data rejection.
- Expired `auth_date` rejection.
- User upsert and session creation.
- Channel membership cache behavior.
- Access denial for banned or missing-channel users.
- Ad validation and active limit.
- Revoke ownership checks.
- Contact attempt creation and cancellation of previous pending follow-ups.
- Deal confirmation sets `COMPLETED`.
- Report self-report and duplicate-report rejection.
- Auto-hide after 3 unique reports.
- Rates parsing, daily cache, stablecoin derivation, stale fallback.
- Admin authorization and audit logging.
- Rate limits.

Frontend tests:

- Outside-Telegram auth state.
- Auth success and access denied states.
- Desktop two-column board layout.
- Mobile segmented board layout.
- Form validation.
- Contact button behavior for available and unavailable usernames.

Bot tests:

- Command routing.
- Admin command authorization.
- WebApp buttons.
- Follow-up callback handling.
- Notification formatting without leaking sensitive data.

Operational validation:

- Docker Compose boots all services.
- API health endpoint responds.
- Web app SSR shell responds without white flash.
- Bot can register commands in a configured environment.

## Assumptions

Assumption: Nuxt 3 is the default Nuxt version for implementation.
Reason: It satisfies Vue 3 SSR and is a stable MVP target.
Risk: If the project later mandates Nuxt 4 specifically, some project scaffolding and config may need adjustment.

Assumption: “Close chat” after confirmed deal means closing the app’s deal process and removing the ad from active board, not forcibly closing a Telegram private chat.
Reason: Telegram Bot API does not provide ownership or control over ordinary user-to-user private chats.
Risk: If the required product behavior is a mediated in-bot chat instead of direct user chat, the contact flow must be redesigned.

Assumption: A new contact click by the same initiator cancels only previous pending follow-ups that have not yet asked the initiator.
Reason: This directly implements “if the user clicked another ad later, do not ask about the first one” without altering already-started confirmation conversations.
Risk: If the desired behavior is to cancel even already-started confirmation prompts, the bot callback state machine must ignore or expire older prompts after a newer contact attempt.

## References

- Telegram Mini Apps: https://core.telegram.org/bots/webapps
- Telegram Bot API: https://core.telegram.org/bots/api
- FastAPI security tools: https://fastapi.tiangolo.com/reference/security/
- FastAPI security tutorial: https://fastapi.tiangolo.com/tutorial/security/
- Nuxt introduction: https://nuxt.com/docs/getting-started/introduction
- Google Sheets `GOOGLEFINANCE`: https://support.google.com/docs/answer/3093281
- Google publish to web: https://support.google.com/docs/answer/183965
