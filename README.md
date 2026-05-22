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
npm ci
npm test
npm run build
```

E2E smoke:

```bash
cd frontend
npm run test:e2e
```

## Docker Compose

For production, create `.env` from `.env.example` and replace all secrets. API/web smoke runs can use built-in development defaults; the bot worker requires a real Telegram token.

```bash
docker compose --env-file .env -f docker/compose.yml build
API_PORT=18000 WEB_PORT=13000 docker compose --env-file .env -f docker/compose.yml up -d api web
curl -fsS http://localhost:18000/api/health
curl -fsS http://localhost:13000/
docker compose --env-file .env -f docker/compose.yml down
```

The compose file exposes the API on `API_PORT` (`8000` by default), Nuxt on `WEB_PORT` (`3000` by default), and runs the bot worker against `http://api:8000` inside the Docker network. Start `bot` only with a real Telegram token. See `docker/reverse-proxy.md` for one-domain proxy notes.
