# Security Policy

## Reporting A Vulnerability

Do not open a public issue for a vulnerability.

Use GitHub private vulnerability reporting or contact the repository owner
through a private channel. Include:

- affected component;
- reproduction steps;
- expected impact;
- relevant logs or requests with secrets removed.

## Scope

Security-sensitive areas include:

- Telegram Mini App `initData` validation;
- session cookies and CSRF handling;
- Telegram webhook secret validation;
- required channel membership checks;
- admin endpoints;
- rate limits;
- user-provided text and report handling.

## Secrets

Never commit real Telegram bot tokens, session secrets, webhook secrets,
database passwords, API keys, or production `.env` files.
