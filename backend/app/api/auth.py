from typing import Annotated
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.auth_schemas import LoginRequest, TokenResponse
from app.core.security import create_access_token
from app.services.auth_service import authenticate_user
from app.api.auth_schemas import RegisterRequest, UserResponse
from app.db.database import get_session
from app.services.auth_service import create_user
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    data: RegisterRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserResponse:
    try:
        return await create_user(session, data)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email or user name already registered",
        ) from exc

@router.post(
    "/login",
    response_model=TokenResponse
)
async def login(
    data:LoginRequest,
    session:Annotated[AsyncSession,Depends(get_session)],
)->TokenResponse:
    user=await authenticate_user(session,data)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    return TokenResponse(
        access_token=create_access_token(str(user.id))
    )

@router.get("/me",response_model=UserResponse)
async def read_current_user(
    current_user:Annotated[User,Depends(get_current_user)]
)->UserResponse:
    return current_user