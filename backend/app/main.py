from contextlib import asynccontextmanager

from fastapi import FastAPI
from openai import AsyncOpenAI

from app.api.auth import router as auth_router
from app.api.conversation import router as conversations_router
from app.api.health import router as health_router
from app.clients.llm_client import LLMClient
from app.core.config import get_settings
from app.db.database import close_database, init_db
from app.db.redis import close_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    if not settings.deepseek_api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")

    openai_client = AsyncOpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        timeout=settings.llm_timeout_seconds,
    )
    app.state.llm_client = LLMClient(
        client=openai_client,
        settings=settings,
    )

    await init_db()

    try:
        yield
    finally:
        await openai_client.close()
        await close_database()
        await close_redis()


app = FastAPI(
    title=get_settings().app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(conversations_router)