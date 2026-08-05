from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth_schemas import DeepSeekKeyRequest, LoginRequest, RegisterRequest, ResendVerificationRequest, TokenResponse, UserResponse, VerificationRequest
from app.api.deps import get_current_user
from app.core.security import create_access_token
from app.db.database import get_session
from app.models.user import User
from app.services.api_key_service import api_key_hint, encrypt_api_key
from app.services.auth_service import authenticate_user, create_user, user_response_payload
from app.services.email_service import issue_verification_code, verify_code

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, session: Annotated[AsyncSession, Depends(get_session)]) -> UserResponse:
    try:
        user = await create_user(session, data)
        await issue_verification_code(session, user)
        return user_response_payload(user)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email or user name already registered") from exc


@router.post("/verify-email")
async def verify_email(data: VerificationRequest, session: Annotated[AsyncSession, Depends(get_session)]) -> dict[str, str]:
    user = (await session.execute(select(User).where(User.email == data.email))).scalar_one_or_none()
    if user is None or not await verify_code(session, user, data.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification code")
    return {"detail": "Email verified. You can now sign in."}


@router.post("/resend-verification")
async def resend_verification(data: ResendVerificationRequest, session: Annotated[AsyncSession, Depends(get_session)]) -> dict[str, str]:
    user = (await session.execute(select(User).where(User.email == data.email))).scalar_one_or_none()
    if user is not None and not user.is_email_verified:
        await issue_verification_code(session, user)
    return {"detail": "If the account needs verification, a code has been sent."}


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, session: Annotated[AsyncSession, Depends(get_session)]) -> TokenResponse:
    user = await authenticate_user(session, data)
    if user is None or not user.is_email_verified:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password, or email is unverified")
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=UserResponse)
async def read_current_user(current_user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return user_response_payload(current_user)


@router.put("/deepseek-key", response_model=UserResponse)
async def save_deepseek_key(data: DeepSeekKeyRequest, current_user: Annotated[User, Depends(get_current_user)], session: Annotated[AsyncSession, Depends(get_session)]) -> UserResponse:
    api_key = data.api_key.strip()
    current_user.deepseek_api_key_encrypted = encrypt_api_key(api_key)
    current_user.deepseek_api_key_hint = api_key_hint(api_key)
    await session.commit()
    await session.refresh(current_user)
    return user_response_payload(current_user)


@router.delete("/deepseek-key", response_model=UserResponse)
async def delete_deepseek_key(current_user: Annotated[User, Depends(get_current_user)], session: Annotated[AsyncSession, Depends(get_session)]) -> UserResponse:
    current_user.deepseek_api_key_encrypted = None
    current_user.deepseek_api_key_hint = None
    await session.commit()
    await session.refresh(current_user)
    return user_response_payload(current_user)
