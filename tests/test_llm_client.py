from types import SimpleNamespace

import pytest
from httpx import Request
from openai import APIError

from app.clients.llm_client import LLMCallError, LLMClient, LLMResponseError
from app.core.config import Settings


class FakeChatCompletions:
    def __init__(self, output_text: str = "mock answer") -> None:
        self.kwargs = None
        self.output_text = output_text

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.output_text))],
        )


class FakeClient:
    def __init__(self, output_text: str = "mock answer") -> None:
        self.chat = SimpleNamespace(completions=FakeChatCompletions(output_text))


class FailingChatCompletions:
    async def create(self, **kwargs):
        raise APIError(
            "upstream failed",
            request=Request("POST", "https://api.deepseek.com/chat/completions"),
            body=None,
        )


class FailingClient:
    chat = SimpleNamespace(completions=FailingChatCompletions())


@pytest.mark.asyncio
async def test_generate_returns_chat_completion_text_and_uses_settings():
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
            "content": "hello",
        }
    ]

    answer = await llm_client.generate(history)

    assert answer == "mock answer"
    assert fake_client.chat.completions.kwargs == {
        "model": "test-model",
        "messages": history,
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
