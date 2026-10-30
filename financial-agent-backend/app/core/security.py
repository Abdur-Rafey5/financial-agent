"""
Security utilities: password hashing (Argon2id) and JWT token management.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from jose import JWTError, jwt

from app.core.config import settings

from argon2.low_level import Type

# ── Password Hashing ────────────────────────────────────────────────────
_ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,   # 64 MiB
    parallelism=4,
    hash_len=32,
    salt_len=16,
    type=Type.ID,  # Argon2id
)


def hash_password(password: str) -> str:
    """Hash a plain-text password with Argon2id."""
    return _ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against an Argon2id hash."""
    try:
        return _ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError):
        return False


def check_needs_rehash(hashed_password: str) -> bool:
    """Check if a hash needs to be updated to current parameters."""
    return _ph.check_needs_rehash(hashed_password)


# ── JWT Token Management ────────────────────────────────────────────────
def create_access_token(
    subject: str,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[dict] = None,
) -> str:
    """
    Create a signed JWT access token.

    Args:
        subject: The token subject, typically the user ID as a string.
        expires_delta: Custom expiry duration. Defaults to config value.
        extra_claims: Additional claims to include in the payload.

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta
        or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    payload = {
        "sub": subject,
        "iat": now,
        "exp": expire,
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and validate a JWT access token.

    Returns:
        Decoded payload dict, or None if the token is invalid/expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError:
        return None
