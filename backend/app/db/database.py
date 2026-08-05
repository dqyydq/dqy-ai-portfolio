from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.base import Base
from app.models.user import User  # 只为触发模型注册
from app.models.conversation import Conversation, Message
from app.models.email_verification import EmailVerificationCode


settings = get_settings()
engine: AsyncEngine = create_async_engine(settings.database_url, pool_pre_ping=True)
session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator:
    async with session_factory() as session:
        yield session


async def check_database() -> bool:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def close_database() -> None:
    await engine.dispose()



async def init_db() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.execute(text("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS is_email_verified BOOLEAN NOT NULL DEFAULT FALSE
        """))
        await connection.execute(text("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS deepseek_api_key_encrypted TEXT
        """))
        await connection.execute(text("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS deepseek_api_key_hint VARCHAR(16)
        """))
