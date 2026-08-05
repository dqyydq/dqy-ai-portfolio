from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, status

from app.core.config import get_settings


def _cipher() -> Fernet:
    secret = get_settings().key_encryption_secret
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API key storage is not configured",
        )
    try:
        return Fernet(secret.encode())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API key storage is not configured",
        ) from exc


def encrypt_api_key(api_key: str) -> str:
    return _cipher().encrypt(api_key.encode()).decode()


def decrypt_api_key(encrypted_key: str) -> str:
    try:
        return _cipher().decrypt(encrypted_key.encode()).decode()
    except (InvalidToken, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Stored API key cannot be read; save a new key",
        ) from exc


def api_key_hint(api_key: str) -> str:
    return f"••••{api_key[-4:]}" if len(api_key) >= 4 else "••••"
