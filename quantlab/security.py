import os
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from pwdlib import PasswordHash


ALGORITHM = "HS256"
PASSWORD_HASH = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = PASSWORD_HASH.hash("not-a-real-user-password")


class SecurityConfigurationError(Exception):
    pass


def hash_password(password: str) -> str:
    return PASSWORD_HASH.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    try:
        return PASSWORD_HASH.verify(password, encoded)
    except Exception:
        return False


def _secret() -> str:
    secret = os.getenv("JWT_SECRET", "")
    if len(secret) < 32:
        raise SecurityConfigurationError("JWT_SECRET must contain at least 32 characters")
    return secret


def create_access_token(user_id: UUID) -> str:
    now = datetime.now(timezone.utc)
    minutes = int(os.getenv("JWT_EXPIRE_MINUTES", "30"))
    if minutes <= 0:
        raise SecurityConfigurationError("JWT_EXPIRE_MINUTES must be positive")
    return jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=minutes)},
        _secret(), algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> UUID:
    try:
        payload = jwt.decode(token, _secret(), algorithms=[ALGORITHM], options={"require": ["sub", "iat", "exp"]})
        return UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, TypeError, KeyError) as exc:
        raise ValueError("Invalid authentication token") from exc
