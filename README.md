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
