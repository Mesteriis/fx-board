# Contributing

Thanks for helping improve FX Board.

## Ground Rules

- Do not commit real secrets, bot tokens, production URLs, private chat IDs, or personal data.
- Keep the service a classifieds board. Do not add payment custody, escrow, or exchange execution flows.
- Do not add text or features that encourage users to misrepresent transaction facts.
- Keep backend business logic out of FastAPI route handlers when a service layer exists.
- Add or update tests for behavior changes.

## Development Setup

Backend:

```bash
docker compose --env-file .env -f docker/compose.yml up -d db
cd backend
uv sync --extra dev
uv run --extra dev ruff check .
uv run --extra dev pytest -q
```

Bot:

```bash
cd bot
uv sync --extra dev
uv run --extra dev ruff check .
uv run --extra dev pytest -q
```

Frontend:

```bash
cd frontend
npm ci
npm test
npm run build
```

## Pull Request Checklist

- Explain what changed and why.
- Include validation commands and results.
- Update README or docs when behavior, config, deployment, or public API changes.
- Keep unrelated refactors out of the PR.
- Confirm that `rg -n "TELEGRAM_BOT_TOKEN=|SESSION_SECRET=|WEBHOOK_SECRET=|DEV_AUTH_TOKEN="`
  does not show real secrets.
