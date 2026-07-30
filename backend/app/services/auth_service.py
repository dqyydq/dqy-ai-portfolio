from app.models.user import User
from app.core.security import get_password_hash,verify_password
from app.api.auth_schemas import RegisterRequest,LoginRequest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

async def create_user(
        session:AsyncSession,
        data:RegisterRequest
)->User:
    user=User(
        email=data.email,
        user_name=data.user_name,
        password_hash=get_password_hash(data.password)

    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    return user

async def authenticate_user(
    session: AsyncSession,
    data: LoginRequest,
) -> User | None:
    
    result=await session.execute(
        select(User).where(User.email==data.email)
    )
    user=result.scalar_one_or_none()

    if user is None or not verify_password(data.password,user.password_hash):
        return None
    return user 