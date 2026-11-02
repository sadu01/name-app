import os
from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

password_hasher = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

SECRET_KEY = os.environ["JWT_SECRET_KEY"]


def hash_password(password: str):
    return password_hasher.hash(password)


def verify_password(password: str, stored_hash: str):
    return password_hasher.verify(password, stored_hash)


def create_access_token(user_id: int):
    expiration = datetime.now(timezone.utc) + timedelta(minutes=30)

    return jwt.encode(
        {"sub": str(user_id), "exp": expiration},
        SECRET_KEY,
        algorithm="HS256",
    )


def decode_user_id(token: str) -> int:
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=["HS256"],
            options={"require": ["sub", "exp"]},
        )
        return int(payload["sub"])
    except (InvalidTokenError, KeyError, ValueError, TypeError):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )