from pwdlib import PasswordHash
from datetime import datetime, timedelta, timezone
import jwt
from app.core.config import get_settings
ALGORITHM = "HS256"
password_hash = PasswordHash.recommended()

def get_password_hash(password: str) -> str:
    return password_hash.hash(password)

def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_access_token(subject:str)->str:
    settings=get_settings()
    expires_at=datetime.now(timezone.utc)+timedelta(
        minutes=settings.access_token_expire_minutes,
    )
    payload={"sub":subject,"exp":expires_at}
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=ALGORITHM
    )