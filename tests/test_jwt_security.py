from datetime import datetime, timezone

import jwt
import pytest
from jwt.exceptions import InvalidSignatureError

from app.core.config import get_settings
from app.core.security import ALGORITHM, create_access_token


def test_access_token_contains_subject_expiry_and_valid_signature() -> None:
    subject = "user-123"
    token = create_access_token(subject)

    payload = jwt.decode(
        token,
        get_settings().jwt_secret_key,
        algorithms=[ALGORITHM],
    )

    assert payload["sub"] == subject
    assert payload["exp"] > datetime.now(timezone.utc).timestamp()

    with pytest.raises(InvalidSignatureError):
        jwt.decode(
            token,
            "not-the-real-secret-but-long-enough-for-hs256",
            algorithms=[ALGORITHM],
        )
