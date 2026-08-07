import logging
import time

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
            started_at = time.monotonic()
            stream = await self._client.chat.completions.create(
                model=self._settings.deepseek_model,
                messages=history,
                timeout=self._settings.llm_timeout_seconds,
                stream=True,
                max_tokens=800,
                extra_body={"thinking": {"type": "disabled"}},
            )
            logger.info("DeepSeek stream connected in %.2fs", time.monotonic() - started_at)
            saw_reasoning = False
            saw_content = False
            async for chunk in stream:
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                if getattr(choice.delta, "reasoning_content", None) and not saw_reasoning:
                    saw_reasoning = True
                    logger.info("DeepSeek returned reasoning chunks despite thinking being disabled")
                delta = choice.delta.content or ""
                if delta:
                    if not saw_content:
                        saw_content = True
                        logger.info("DeepSeek first content chunk in %.2fs", time.monotonic() - started_at)
                    yield delta
        except APIError as exc:
            logger.warning(
                "DeepSeek stream request failed (status=%s): %s",
                getattr(exc, "status_code", None),
                exc,
            )
            raise LLMCallError("LLM stream request failed") from exc
