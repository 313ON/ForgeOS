from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from enum import StrEnum

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..domain.models import User


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    VIEW = "VIEW"


@dataclass(frozen=True)
class AuthenticatedUser:
    id: int
    username: str
    role: UserRole


bearer_scheme = HTTPBearer(auto_error=False)
_RUNTIME_SECRET = os.getenv("FORGEOS_AUTH_SECRET") or secrets.token_urlsafe(32)


def hash_password(password: str) -> str:
    if len(password) < 10:
        raise ValueError("Password must contain at least 10 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${_encode(salt)}${_encode(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt, expected = encoded.split("$", 2)
        if algorithm != "scrypt":
            return False
        actual = hashlib.scrypt(password.encode(), salt=_decode(salt), n=2**14, r=8, p=1)
        return hmac.compare_digest(actual, _decode(expected))
    except (ValueError, TypeError):
        return False


def create_access_token(user: User, expires_seconds: int = 8 * 60 * 60) -> str:
    payload = {"sub": str(user.id), "username": user.username, "role": user.role, "exp": int(time.time()) + expires_seconds}
    encoded = _encode(json.dumps(payload, separators=(",", ":")).encode())
    signature = hmac.new(_secret().encode(), encoded.encode(), hashlib.sha256).digest()
    return f"{encoded}.{_encode(signature)}"


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> AuthenticatedUser:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    payload = _decode_token(credentials.credentials)
    user_id = int(payload["sub"])
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User is inactive or missing")
    return AuthenticatedUser(user.id, user.username, UserRole(user.role))


def require_admin(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    if user.role is not UserRole.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator role required")
    return user


def _decode_token(token: str) -> dict[str, object]:
    try:
        encoded, signature = token.split(".", 1)
        expected = hmac.new(_secret().encode(), encoded.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _decode(signature)):
            raise ValueError
        payload = json.loads(_decode(encoded))
        if int(payload["exp"]) < int(time.time()):
            raise ValueError
        return payload
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from None


def _secret() -> str:
    return _RUNTIME_SECRET


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
