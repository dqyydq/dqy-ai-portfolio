from uuid import UUID

import jwt
from jwt.exceptions import InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import ALGORITHM
from app.models.user import User


async def get_websocket_user(
    token: str | None,
    session: AsyncSession,
) -> User | None:
    if token is None:
        return None

    try:
        payload = jwt.decode(
            token,
            get_settings().jwt_secret_key,
            algorithms=[ALGORITHM],
        )
        user_id = UUID(payload["sub"])
    except (InvalidTokenError, KeyError, ValueError):
        return None

    return await session.get(User, user_id)