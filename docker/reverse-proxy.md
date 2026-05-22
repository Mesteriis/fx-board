# Reverse Proxy

Use one public domain for the Telegram WebApp and API. Keeping both under one origin simplifies cookies, CSRF, Telegram WebView behavior, and reverse proxy rules.

Example public routes:

- `https://exchange.example.com/` -> `web:3000`
- `https://exchange.example.com/api` -> `api:8000`

Production requirements:

- Enable HTTPS before registering the Telegram WebApp URL.
- Forward `X-Forwarded-Proto`, `X-Forwarded-For`, and `Host`.
- Do not expose the SQLite data volume directly.
- Keep `TELEGRAM_BOT_TOKEN`, `SESSION_SECRET`, `TELEGRAM_WEBHOOK_SECRET`, and `TELEGRAM_INTERNAL_BOT_SECRET` only in environment variables.
- Add the bot as administrator to every required channel used by `TELEGRAM_REQUIRED_CHANNELS`.
- Route `/api/telegram/webhook` only through HTTPS and configure Telegram with the same `TELEGRAM_WEBHOOK_SECRET`.

For Traefik or Nginx Proxy Manager, point the frontend service at `web:3000` and add an `/api` location/router to `api:8000`.
