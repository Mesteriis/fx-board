async def test_webhook_rejects_missing_secret(client) -> None:
    response = await client.post("/api/telegram/webhook", json={})

    assert response.status_code == 403


async def test_webhook_rejects_wrong_secret(client) -> None:
    response = await client.post(
        "/api/telegram/webhook",
        json={"update_id": 1},
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
    )

    assert response.status_code == 403


async def test_webhook_accepts_valid_secret(client, test_settings) -> None:
    response = await client.post(
        "/api/telegram/webhook",
        json={"update_id": 1, "message": {"text": "/start"}},
        headers={
            "X-Telegram-Bot-Api-Secret-Token": (
                test_settings.telegram_webhook_secret.get_secret_value()
            )
        },
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
