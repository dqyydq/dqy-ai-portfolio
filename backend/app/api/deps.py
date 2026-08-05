from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import ALGORITHM
from app.db.database import get_session
from app.models.user import User

from app.clients.llm_client import LLMClient
from redis.asyncio import Redis
from openai import AsyncOpenAI
from app.services.api_key_service import decrypt_api_key


bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise credentials_exception
    try:
        payload = jwt.decode(
            credentials.credentials,
            get_settings().jwt_secret_key,
            algorithms=[ALGORITHM],
        )
        user_id = UUID(payload["sub"])
    except (InvalidTokenError, KeyError, ValueError):
        raise credentials_exception

    user = await session.get(User, user_id)
    if user is None or not user.is_email_verified:
        raise credentials_exception

    return user


async def get_llm_client(
    current_user: Annotated[User, Depends(get_current_user)],
) -> LLMClient:
    if not current_user.deepseek_api_key_encrypted:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Configure your DeepSeek API key before chatting")
    settings = get_settings()
    return LLMClient(
        AsyncOpenAI(api_key=decrypt_api_key(current_user.deepseek_api_key_encrypted), base_url=settings.deepseek_base_url, timeout=settings.llm_timeout_seconds),
        settings,
    )


def get_redis_client(request: Request) -> Redis:
    return request.app.state.redis_client
