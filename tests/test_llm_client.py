from types import SimpleNamespace

import pytest
from httpx import Request
from openai import APIError

from app.clients.llm_client import LLMCallError, LLMClient, LLMResponseError
from app.core.config import Settings


class FakeResponses:
    def __init__(self, output_text: str = "mock answer") -> None:
        self.kwargs = None
        self.output_text = output_text

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(output_text=self.output_text)


class FakeClient:
    def __init__(self, output_text: str = "mock answer") -> None:
        self.responses = FakeResponses(output_text)


class FailingResponses:
    async def create(self, **kwargs):
        raise APIError(
            "upstream failed",
            request=Request("POST", "https://api.deepseek.com/v1/responses"),
            body=None,
        )


class FailingClient:
    responses = FailingResponses()


@pytest.mark.asyncio
async def test_generate_returns_output_text_and_uses_settings():
    settings = Settings(
        deepseek_api_key="test-key-not-used",
        deepseek_model="test-model",
        llm_timeout_seconds=12.5,
    )
    fake_client = FakeClient()
    llm_client = LLMClient(client=fake_client, settings=settings)
    history = [
        {
            "role": "user",
            "content": [{"type": "input_text", "text": "hello"}],
        }
    ]

    answer = await llm_client.generate(history)

    assert answer == "mock answer"
    assert fake_client.responses.kwargs == {
        "model": "test-model",
        "input": history,
        "timeout": 12.5,
    }


@pytest.mark.asyncio
async def test_generate_rejects_empty_output():
    settings = Settings(deepseek_api_key="test-key-not-used")
    llm_client = LLMClient(client=FakeClient("   "), settings=settings)

    with pytest.raises(LLMResponseError, match="empty output"):
        await llm_client.generate([])


@pytest.mark.asyncio
async def test_generate_wraps_upstream_api_error_and_preserves_cause():
    settings = Settings(deepseek_api_key="test-key-not-used")
    llm_client = LLMClient(client=FailingClient(), settings=settings)

    with pytest.raises(LLMCallError, match="LLM request failed") as error:
        await llm_client.generate([])

    assert isinstance(error.value.__cause__, APIError)
