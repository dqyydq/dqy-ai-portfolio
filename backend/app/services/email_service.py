import asyncio
import hashlib
import os
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
    # Render injects secrets through the process environment. Prefer that source
    # here so email delivery remains independent of any cached settings instance.
    smtp_host = os.getenv("SMTP_HOST") or settings.smtp_host
    smtp_username = os.getenv("SMTP_USERNAME") or settings.smtp_username
    smtp_password = os.getenv("SMTP_PASSWORD") or settings.smtp_password
    smtp_from_email = os.getenv("SMTP_FROM_EMAIL") or settings.smtp_from_email
    smtp_port = int(os.getenv("SMTP_PORT") or settings.smtp_port)
    smtp_use_ssl = (os.getenv("SMTP_USE_SSL") or str(settings.smtp_use_ssl)).lower() in {"1", "true", "yes", "on"}
    missing = [name for name, value in {
        "SMTP_HOST": smtp_host,
        "SMTP_USERNAME": smtp_username,
        "SMTP_PASSWORD": smtp_password,
        "SMTP_FROM_EMAIL": smtp_from_email,
    }.items() if not value]
    if missing:
        raise RuntimeError(f"SMTP is not configured; missing {', '.join(missing)}")
    message = EmailMessage()
    message["Subject"] = "AI Assistant email verification"
    message["From"] = smtp_from_email
    message["To"] = recipient
    message.set_content(
        f"Your verification code is {code}. It expires in {VERIFICATION_CODE_TTL_MINUTES} minutes."
    )
    if smtp_use_ssl:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15) as client:
            client.login(smtp_username, smtp_password)
            client.send_message(message)
    else:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as client:
            client.starttls()
            client.login(smtp_username, smtp_password)
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
