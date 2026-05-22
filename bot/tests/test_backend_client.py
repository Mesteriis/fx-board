import httpx
import pytest

from fx_board_bot.backend_client import BackendClient


@pytest.mark.asyncio
async def test_claim_due_followups_sends_internal_secret_header() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"items": [{"contact_attempt_id": 10}]})

    client = BackendClient(
        base_url="https://backend.test/",
        internal_secret="secret",
        transport=httpx.MockTransport(handler),
    )

    items = await client.claim_due_followups(limit=3)

    assert items == [{"contact_attempt_id": 10}]
    assert len(requests) == 1
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/api/internal/contact-followups/claim"
    assert requests[0].url.params["limit"] == "3"
    assert requests[0].headers["X-Internal-Bot-Secret"] == "secret"


@pytest.mark.asyncio
async def test_answer_followup_sends_actor_answer_and_internal_secret_header() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"status": "INITIATOR_NO_DEAL"})

    client = BackendClient(
        base_url="https://backend.test",
        internal_secret="secret",
        transport=httpx.MockTransport(handler),
    )

    result = await client.answer_followup(
        contact_attempt_id=15,
        actor_telegram_id=99,
        answer="no",
    )

    assert result == {"status": "INITIATOR_NO_DEAL"}
    assert len(requests) == 1
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/api/internal/contact-followups/15/answer"
    assert requests[0].headers["X-Internal-Bot-Secret"] == "secret"
    assert requests[0].read() == b'{"actor_telegram_id":99,"answer":"no"}'


@pytest.mark.asyncio
async def test_mark_followup_prompt_sent_sends_prompt_type_and_secret_header() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"action": "prompt_recorded"})

    client = BackendClient(
        base_url="https://backend.test",
        internal_secret="secret",
        transport=httpx.MockTransport(handler),
    )

    result = await client.mark_followup_prompt_sent(
        contact_attempt_id=16,
        prompt_type="author",
    )

    assert result == {"action": "prompt_recorded"}
    assert len(requests) == 1
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/api/internal/contact-followups/16/prompt-sent"
    assert requests[0].headers["X-Internal-Bot-Secret"] == "secret"
    assert requests[0].read() == b'{"prompt_type":"author"}'
