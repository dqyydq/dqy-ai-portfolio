from openai import APIError

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
            response = await self._client.responses.create(
                model=self._settings.deepseek_model,
                input=history,
                timeout=self._settings.llm_timeout_seconds,
            )
        except APIError as exc:
            raise LLMCallError("LLM request failed") from exc

        text = response.output_text.strip()
        if not text:
            raise LLMResponseError("LLM returned empty output")
        return text
