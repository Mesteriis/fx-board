import httpx


class BackendClient:
    def __init__(
        self,
        *,
        base_url: str,
        internal_secret: str,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._internal_secret = internal_secret
        self._timeout = timeout
        self._transport = transport

    async def claim_due_followups(self, *, limit: int = 25) -> list[dict[str, object]]:
        async with self._client() as client:
            response = await client.post(
                f"{self._base_url}/api/internal/contact-followups/claim",
                params={"limit": limit},
                headers=self._internal_headers(),
            )
            response.raise_for_status()
            body = response.json()
            items = body.get("items")
            if not isinstance(items, list):
                raise ValueError("backend response missing items")
            return list(items)

    async def answer_followup(
        self,
        *,
        contact_attempt_id: int,
        actor_telegram_id: int,
        answer: str,
    ) -> dict[str, object]:
        async with self._client() as client:
            response = await client.post(
                f"{self._base_url}/api/internal/contact-followups/{contact_attempt_id}/answer",
                json={"actor_telegram_id": actor_telegram_id, "answer": answer},
                headers=self._internal_headers(),
            )
            response.raise_for_status()
            body = response.json()
            if not isinstance(body, dict):
                raise ValueError("backend response must be an object")
            return dict(body)

    async def mark_followup_prompt_sent(
        self,
        *,
        contact_attempt_id: int,
        prompt_type: str,
    ) -> dict[str, object]:
        async with self._client() as client:
            response = await client.post(
                f"{self._base_url}/api/internal/contact-followups/"
                f"{contact_attempt_id}/prompt-sent",
                json={"prompt_type": prompt_type},
                headers=self._internal_headers(),
            )
            response.raise_for_status()
            body = response.json()
            if not isinstance(body, dict):
                raise ValueError("backend response must be an object")
            return dict(body)

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self._timeout, transport=self._transport)

    def _internal_headers(self) -> dict[str, str]:
        return {"X-Internal-Bot-Secret": self._internal_secret}
