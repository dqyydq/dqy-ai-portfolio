import uuid

from sqlalchemy import delete

from app.api.auth_schemas import LoginRequest, RegisterRequest
from app.core.security import verify_password
from app.db.database import close_database, init_db, session_factory
from app.models.user import User
from app.services.auth_service import authenticate_user, create_user


async def test_create_user_persists_hashed_password() -> None:
    email = f"test-{uuid.uuid4()}@example.com"
    user_name = f"user_{uuid.uuid4().hex[:12]}"
    password = "correct horse battery staple"

    await init_db()
    user_id = None

    try:
        async with session_factory() as session:
            user = await create_user(
                session,
                RegisterRequest(
                    email=email,
                    user_name=user_name,
                    password=password,
                ),
            )
            user_id = user.id

        async with session_factory() as session:
            persisted_user = await session.get(User, user_id)

        assert persisted_user is not None
        assert persisted_user.email == email
        assert persisted_user.user_name == user_name
        assert persisted_user.password_hash != password
        assert verify_password(password, persisted_user.password_hash)
    finally:
        async with session_factory() as session:
            await session.execute(delete(User).where(User.email == email))
            await session.commit()
        await close_database()


async def test_authenticate_user_returns_user_only_for_valid_credentials() -> None:
    email = f"login-{uuid.uuid4()}@example.com"
    user_name = f"user_{uuid.uuid4().hex[:12]}"
    password = "correct horse battery staple"

    await init_db()

    try:
        async with session_factory() as session:
            created_user = await create_user(
                session,
                RegisterRequest(
                    email=email,
                    user_name=user_name,
                    password=password,
                ),
            )

        async with session_factory() as session:
            authenticated_user = await authenticate_user(
                session,
                LoginRequest(email=email, password=password),
            )
            wrong_password_user = await authenticate_user(
                session,
                LoginRequest(email=email, password="wrong-password"),
            )
            missing_user = await authenticate_user(
                session,
                LoginRequest(email="missing@example.com", password=password),
            )

        assert authenticated_user is not None
        assert authenticated_user.id == created_user.id
        assert wrong_password_user is None
        assert missing_user is None
    finally:
        async with session_factory() as session:
            await session.execute(delete(User).where(User.email == email))
            await session.commit()
        await close_database()
