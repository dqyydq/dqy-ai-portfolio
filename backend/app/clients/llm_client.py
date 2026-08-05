import logging

from openai import APIError
from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

class LLMResponseError(Exception):
    pass

class LLMCallError(Exception):
    pass

class LLMClient:
    def __init__(self, client, settings):
        self._client=client
        self._settings=settings

    async def generate(self, history) -> str:
        try:
            response = await self._client.chat.completions.create(
                model=self._settings.deepseek_model,
                messages=history,
                timeout=self._settings.llm_timeout_seconds,
            )
        except APIError as exc:
            logger.warning(
                "DeepSeek request failed (status=%s): %s",
                getattr(exc, "status_code", None),
                exc,
            )
            raise LLMCallError("LLM request failed") from exc

        text = (response.choices[0].message.content or "").strip()
        if not text:
            raise LLMResponseError("LLM returned empty output")
        return text



    async def stream_generate(
        self,
        history: list[dict[str, str]],
    ) -> AsyncIterator[str]:
        try:
            stream = await self._client.chat.completions.create(
                model=self._settings.deepseek_model,
                messages=history,
                timeout=self._settings.llm_timeout_seconds,
                stream=True,
            )
        except APIError as exc:
            logger.warning(
                "DeepSeek stream request failed (status=%s): %s",
                getattr(exc, "status_code", None),
                exc,
            )
            raise LLMCallError("LLM stream request failed") from exc

        async for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                yield delta
