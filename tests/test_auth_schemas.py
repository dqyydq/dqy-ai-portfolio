import uuid
from datetime import datetime, timezone

from app.api.auth_schemas import UserResponse
from app.models.user import User


def test_user_response_reads_orm_attributes_without_password_hash() -> None:
    user = User(
        id=uuid.uuid4(),
        email="alice@example.com",
        user_name="alice",
        password_hash="not-exposed",
        created_at=datetime.now(timezone.utc),
    )

    response = UserResponse.model_validate(user)

    assert response.email == user.email
    assert response.user_name == user.user_name
    assert "password_hash" not in response.model_dump()
