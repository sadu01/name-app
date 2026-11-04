import hashlib
import os
import secrets
import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Deque, Dict, Optional, Tuple

import jwt
from fastapi import HTTPException
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

password_hasher = PasswordHash.recommended()
JWT_ALGORITHM = "HS256"
JWT_ISSUER = "name-app"
ACCESS_TOKEN_MINUTES = 30
REFRESH_TOKEN_DAYS = 14
SESSION_DAYS = 30


def _secret_key() -> str:
    secret = os.getenv("JWT_SECRET_KEY", "")
    if len(secret.encode("utf-8")) < 32:
        raise HTTPException(
            status_code=503,
            detail="Authentication is not configured. Set a strong JWT_SECRET_KEY.",
        )
    return secret


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, stored_hash: Optional[str]) -> bool:
    if not stored_hash:
        return False
    try:
        return password_hasher.verify(password, stored_hash)
    except (UnknownHashError, ValueError, TypeError):
        return False


def create_access_token(user_id: int, session_id: str) -> Tuple[str, int]:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=ACCESS_TOKEN_MINUTES)
    token = jwt.encode(
        {
            "sub": str(user_id),
            "sid": session_id,
            "jti": str(uuid.uuid4()),
            "iat": now,
            "exp": expires_at,
            "typ": "access",
            "iss": JWT_ISSUER,
        },
        _secret_key(),
        algorithm=JWT_ALGORITHM,
    )
    return token, ACCESS_TOKEN_MINUTES * 60


def decode_access_token(token: str) -> Tuple[int, str]:
    try:
        payload = jwt.decode(
            token,
            _secret_key(),
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            options={
                "require": ["sub", "sid", "jti", "iat", "exp", "typ", "iss"],
            },
        )
        if payload.get("typ") != "access":
            raise InvalidTokenError("Unexpected token type")
        user_id = int(payload["sub"])
        session_id = str(uuid.UUID(payload["sid"]))
        uuid.UUID(payload["jti"])
        return user_id, session_id
    except (InvalidTokenError, KeyError, ValueError, TypeError):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


class LoginRateLimiter:
    def __init__(
        self,
        max_attempts: int = 10,
        window_seconds: int = 300,
        max_keys: int = 10000,
    ) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._attempts: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            attempts = self._attempts[key]
            while attempts and now - attempts[0] >= self.window_seconds:
                attempts.popleft()
            if len(attempts) >= self.max_attempts:
                raise HTTPException(
                    status_code=429,
                    detail="Too many authentication attempts. Try again later.",
                    headers={"Retry-After": str(self.window_seconds)},
                )
            attempts.append(now)
            if len(self._attempts) > self.max_keys:
                oldest_key = min(
                    self._attempts,
                    key=lambda item: self._attempts[item][0]
                    if self._attempts[item]
                    else now,
                )
                self._attempts.pop(oldest_key, None)

    def reset(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)


login_rate_limiter = LoginRateLimiter()
