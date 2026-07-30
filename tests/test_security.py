from app.core.security import get_password_hash, verify_password


def test_password_hashing_and_verification() -> None:
    plain_password = "correct horse battery staple"

    hashed_password = get_password_hash(plain_password)

    assert hashed_password != plain_password
    assert verify_password(plain_password, hashed_password)
    assert not verify_password("wrong-password", hashed_password)
