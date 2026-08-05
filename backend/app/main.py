from contextlib import asynccontextmanager

from fastapi import FastAPI
from openai import AsyncOpenAI
from app.api.interview_review import router as interview_review_router
from app.api.auth import router as auth_router
from app.api.conversation import router as conversations_router
from app.api.health import router as health_router
from app.clients.llm_client import LLMClient
from app.core.config import get_settings
from app.db.database import close_database, init_db
from app.db.redis import create_redis_client
from app.clients.cached_llm_client import CachedLLMClient
from app.api.realtime import router as realtime_router

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

    base_llm_client = LLMClient(
        client=openai_client,
        settings=settings,
    )

    redis_client = create_redis_client()

    app.state.llm_client = CachedLLMClient(
        llm_client=base_llm_client,
        redis_client=redis_client,
        model=settings.deepseek_model,
    )
    app.state.redis_client = redis_client

    try:
        await init_db()
        yield
    finally:
        await openai_client.close()
        await close_database()
        await redis_client.aclose()


app = FastAPI(
    title=get_settings().app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(conversations_router)
app.include_router(interview_review_router)
app.include_router(realtime_router)