from dataclasses import dataclass
from typing import Any

import httpx


class TelegramApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChatMemberResult:
    status: str
    raw: dict[str, Any]


class TelegramBotApiClient:
    def __init__(self, *, token: str, timeout_seconds: float = 10.0) -> None:
        self._base_url = f"https://api.telegram.org/bot{token}"
        self._timeout_seconds = timeout_seconds

    async def get_chat_member(self, *, chat_id: str, user_id: int) -> ChatMemberResult:
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(
                    f"{self._base_url}/getChatMember",
                    json={"chat_id": chat_id, "user_id": user_id},
                )
            if response.status_code >= 400:
                raise TelegramApiError("telegram getChatMember http error")
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            raise TelegramApiError("telegram getChatMember request failed") from None

        if not payload.get("ok"):
            raise TelegramApiError("telegram getChatMember returned not ok")

        try:
            result = payload["result"]
            status = result["status"]
        except (KeyError, TypeError) as exc:
            raise TelegramApiError("telegram getChatMember returned malformed payload") from exc

        return ChatMemberResult(status=status, raw=result)
