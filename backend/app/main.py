from contextlib import asynccontextmanager

from fastapi import FastAPI
from app.api.auth import router as auth_router
from app.api.conversation import router as conversations_router
from app.api.health import router as health_router
from app.core.config import get_settings
from app.db.database import close_database, init_db
from app.db.redis import create_redis_client
from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    redis_client = create_redis_client()
    app.state.redis_client = redis_client

    try:
        await init_db()
        yield
    finally:
        await close_database()
        await redis_client.aclose()


app = FastAPI(
    title=get_settings().app_name,
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(conversations_router)
