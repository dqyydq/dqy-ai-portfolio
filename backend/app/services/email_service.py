import asyncio
import hashlib
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.email_verification import EmailVerificationCode
from app.models.user import User


VERIFICATION_CODE_TTL_MINUTES = 10


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def _send_message(recipient: str, code: str) -> None:
    settings = get_settings()
    if not all([settings.smtp_host, settings.smtp_username, settings.smtp_password, settings.smtp_from_email]):
        raise RuntimeError("SMTP is not configured")
    message = EmailMessage()
    message["Subject"] = "AI Assistant email verification"
    message["From"] = settings.smtp_from_email
    message["To"] = recipient
    message.set_content(
        f"Your verification code is {code}. It expires in {VERIFICATION_CODE_TTL_MINUTES} minutes."
    )
    if settings.smtp_use_ssl:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15) as client:
            client.login(settings.smtp_username, settings.smtp_password)
            client.send_message(message)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as client:
            client.starttls()
            client.login(settings.smtp_username, settings.smtp_password)
            client.send_message(message)


async def issue_verification_code(session: AsyncSession, user: User) -> None:
    code = f"{secrets.randbelow(1_000_000):06d}"
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(EmailVerificationCode).where(
            EmailVerificationCode.user_id == user.id,
            EmailVerificationCode.consumed_at.is_(None),
        )
    )
    for old_code in result.scalars():
        old_code.consumed_at = now
    session.add(EmailVerificationCode(
        user_id=user.id,
        code_hash=_hash_code(code),
        expires_at=now + timedelta(minutes=VERIFICATION_CODE_TTL_MINUTES),
    ))
    await session.commit()
    await asyncio.to_thread(_send_message, user.email, code)


async def verify_code(session: AsyncSession, user: User, code: str) -> bool:
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(EmailVerificationCode)
        .where(
            EmailVerificationCode.user_id == user.id,
            EmailVerificationCode.consumed_at.is_(None),
        )
        .order_by(EmailVerificationCode.created_at.desc())
        .limit(1)
    )
    record = result.scalar_one_or_none()
    if record is None or record.expires_at < now or not secrets.compare_digest(record.code_hash, _hash_code(code)):
        return False
    record.consumed_at = now
    user.is_email_verified = True
    await session.commit()
    return True
