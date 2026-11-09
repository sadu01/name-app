import hmac
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    UniqueConstraint,
    func,
    or_,
    text,
)
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, relationship
from starlette.middleware.base import RequestResponseEndpoint

from auth import (
    REFRESH_TOKEN_DAYS,
    SESSION_DAYS,
    create_access_token,
    decode_access_token,
    generate_csrf_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    login_rate_limiter,
    verify_password,
)
from database import Base, get_db


logger = logging.getLogger(__name__)


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    username: str = Field(min_length=3, max_length=30)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    mobile_number: Optional[str] = Field(default=None, max_length=20)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or not all(char.isalpha() or char.isspace() for char in normalized):
            raise ValueError("Name must contain only letters and spaces")
        return normalized

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{2,29}", normalized):
            raise ValueError(
                "Username must be 3-30 characters using letters, numbers, '.', '_' or '-'"
            )
        return normalized

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if "\x00" in value or len(value.encode("utf-8")) > 128:
            raise ValueError("Password must be at most 128 bytes")
        return value

    @field_validator("mobile_number", mode="before")
    @classmethod
    def validate_mobile_number(cls, value: Any) -> Optional[str]:
        return normalize_mobile_number(value)


class MobileNumberUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mobile_number: Optional[str] = Field(max_length=20)

    @field_validator("mobile_number", mode="before")
    @classmethod
    def validate_mobile_number(cls, value: Any) -> Optional[str]:
        return normalize_mobile_number(value)


def normalize_mobile_number(value: Any) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Mobile number must be a string")
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > 20:
        raise ValueError("Mobile number must be at most 20 characters")
    if not re.fullmatch(r"\+?[0-9]+", normalized):
        raise ValueError("Mobile number must contain digits and an optional leading '+'")
    return normalized


class BlogCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=20000)
    city: str = Field(min_length=1, max_length=100)
    email: EmailStr
    author: str = Field(min_length=1, max_length=100)
    tag_ids: list[int] = Field(default_factory=list, max_length=100)

    @field_validator("title", "city", "author")
    @classmethod
    def validate_letters(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or any(not char.isalpha() and char != " " for char in normalized):
            raise ValueError("Only letters and spaces are allowed")
        return normalized

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Description cannot be empty")
        return normalized

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class BlogUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, min_length=1, max_length=20000)
    city: Optional[str] = Field(default=None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    author: Optional[str] = Field(default=None, min_length=1, max_length=100)
    tag_ids: Optional[list[int]] = Field(default=None, max_length=100)

    @field_validator("title", "city", "author")
    @classmethod
    def validate_letters(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized or any(not char.isalpha() and char != " " for char in normalized):
            raise ValueError("Only letters and spaces are allowed")
        return normalized

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("Description cannot be empty")
        return normalized

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: Optional[EmailStr]) -> Optional[str]:
        return str(value).strip().lower() if value is not None else None


blog_tags = Table(
    "blog_tags",
    Base.metadata,
    Column("blog_id", Integer, ForeignKey("blogs.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True),
)


class Blog(Base):
    __tablename__ = "blogs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=False, default="")
    city = Column(String, nullable=False)
    email = Column(String, nullable=False)
    author = Column(String, nullable=False)
    date_created = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    tags = relationship("Tag", secondary=blog_tags, back_populates="blogs")
    user = relationship("User", back_populates="blogs")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index(
            "uq_users_username",
            "username",
            unique=True,
            postgresql_where=text("username IS NOT NULL"),
        ),
        Index(
            "uq_users_email",
            "email",
            unique=True,
            postgresql_where=text("email IS NOT NULL"),
        ),
    )

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    username = Column(String(30), nullable=True)
    email = Column(String(254), nullable=True)
    password_hash = Column(String(255), nullable=True)
    role = Column(String(20), nullable=False, default="user", server_default="user")
    mobile_number = Column(String(20), nullable=True)
    profile = relationship("Profile", back_populates="user", uselist=False)
    blogs = relationship("Blog", back_populates="user")


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    city = Column(String, nullable=False)

    user = relationship("User", back_populates="profile")


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)

    blogs = relationship("Blog", secondary=blog_tags, back_populates="tags")


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    refresh_tokens = relationship(
        "RefreshToken", back_populates="session", cascade="all, delete-orphan"
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
        Index("ix_refresh_tokens_session_id", "session_id"),
    )

    id = Column(Integer, primary_key=True)
    session_id = Column(
        String(36), ForeignKey("auth_sessions.id", ondelete="CASCADE"), nullable=False
    )
    token_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    replaced_by_id = Column(Integer, ForeignKey("refresh_tokens.id"), nullable=True)

    session = relationship("AuthSession", back_populates="refresh_tokens")


def row_to_blog(blog: Blog) -> dict:
    return {
        "id": blog.id,
        "title": blog.title,
        "description": blog.description,
        "city": blog.city,
        "email": blog.email,
        "author": blog.author,
        "date_created": blog.date_created,
        "user_id": blog.user_id,
        "user_name": blog.user.name if blog.user else None,
        "tags": [tag.name for tag in blog.tags],
        "tag_ids": [tag.id for tag in blog.tags],
    }


def _allowed_origins() -> list[str]:
    configured = os.getenv("FRONTEND_ORIGINS")
    if configured:
        return [origin.strip().rstrip("/") for origin in configured.split(",") if origin.strip()]
    return [
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:5501",
        "http://127.0.0.1:5501",
        "http://127.0.0.1:8001",
        "http://localhost:8001",
        "https://name-app-frontend.onrender.com",
        "https://name-app-yj19.onrender.com",
    ]


def _require_allowed_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") not in _allowed_origins():
        raise HTTPException(status_code=403, detail="Request origin is not allowed")


def _require_csrf(request: Request) -> None:
    _require_allowed_origin(request)
    cookie_token = request.cookies.get("blog_csrf")
    header_token = request.headers.get("x-csrf-token")
    if not cookie_token or not header_token or not hmac.compare_digest(cookie_token, header_token):
        raise HTTPException(status_code=403, detail="CSRF validation failed")


def _client_rate_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def enforce_auth_rate_limit(request: Request) -> None:
    login_rate_limiter.check(f"{_client_rate_key(request)}:{request.url.path}")


def _set_auth_cookies(response: Response, refresh_token: str, csrf_token: str, max_age: int) -> None:
    secure = os.getenv("AUTH_COOKIE_SECURE", "true").lower() in {"1", "true", "yes"}
    same_site = os.getenv("AUTH_COOKIE_SAMESITE", "none").lower()
    if same_site not in {"lax", "strict", "none"}:
        raise HTTPException(status_code=503, detail="Invalid authentication cookie configuration")
    response.set_cookie(
        "blog_refresh",
        refresh_token,
        max_age=max_age,
        httponly=True,
        secure=secure,
        samesite=same_site,
        path="/",
    )
    response.set_cookie(
        "blog_csrf",
        csrf_token,
        max_age=max_age,
        httponly=False,
        secure=secure,
        samesite=same_site,
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    secure = os.getenv("AUTH_COOKIE_SECURE", "true").lower() in {"1", "true", "yes"}
    same_site = os.getenv("AUTH_COOKIE_SAMESITE", "none").lower()
    response.delete_cookie(
        "blog_refresh", path="/", httponly=True, secure=secure, samesite=same_site
    )
    response.delete_cookie(
        "blog_csrf", path="/", httponly=False, secure=secure, samesite=same_site
    )


def _set_csrf_cookie(response: Response, csrf_token: str, max_age: int = SESSION_DAYS * 86400) -> None:
    secure = os.getenv("AUTH_COOKIE_SECURE", "true").lower() in {"1", "true", "yes"}
    same_site = os.getenv("AUTH_COOKIE_SAMESITE", "none").lower()
    if same_site not in {"lax", "strict", "none"}:
        raise HTTPException(status_code=503, detail="Invalid authentication cookie configuration")
    response.set_cookie(
        "blog_csrf",
        csrf_token,
        max_age=max_age,
        httponly=False,
        secure=secure,
        samesite=same_site,
        path="/",
    )


def _safe_user(user: User) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "username": user.username,
        "email": user.email,
        "role": user.role,
    }


def _private_user(user: User) -> dict:
    return {**_safe_user(user), "mobile_number": user.mobile_number}


def _issue_access_token(user: User, session_id: str) -> dict:
    token, expires_in = create_access_token(user.id, session_id)
    return {"access_token": token, "token_type": "bearer", "expires_in": expires_in}


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    user_id, session_id = decode_access_token(token)
    session = (
        db.query(AuthSession)
        .filter(
            AuthSession.id == session_id,
            AuthSession.user_id == user_id,
            AuthSession.revoked_at.is_(None),
        )
        .first()
    )
    now = datetime.now(timezone.utc)
    if session is None or _as_utc(session.expires_at) <= now:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


app = FastAPI(title="Blog API", description="API for managing blogs", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
)


@app.middleware("http")
async def disable_auth_response_caching(
    request: Request, call_next: RequestResponseEndpoint
) -> Response:
    response = await call_next(request)
    if request.url.path in {"/register", "/login", "/refresh", "/logout", "/me", "/csrf"}:
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
    return response


@app.exception_handler(RequestValidationError)
async def sanitized_validation_error(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    del _request
    errors = [
        {
            "loc": error.get("loc", ()),
            "msg": error.get("msg", "Invalid input"),
            "type": error.get("type", "value_error"),
        }
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": errors})


@app.exception_handler(SQLAlchemyError)
async def database_error(
    _request: Request, exc: SQLAlchemyError
) -> JSONResponse:
    logger.error(
        "Database operation failed",
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return JSONResponse(
        status_code=503,
        content={"detail": "Database operation failed"},
    )


@app.get("/")
def home() -> dict:
    return {"message": "API"}


@app.get("/db-check")
def db_check(db: Session = Depends(get_db)) -> dict:
    try:
        database_name = db.execute(text("SELECT current_database()")).scalar_one()
        return {"status": "connected", "database": database_name}
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database connection failed") from exc


@app.get("/blogs")
def get_blogs(db: Session = Depends(get_db)) -> list[dict]:
    blogs = db.query(Blog).order_by(Blog.id).all()
    return [row_to_blog(blog) for blog in blogs]


@app.get("/blogs/{blog_id}")
def get_blog_by_id(blog_id: int, db: Session = Depends(get_db)) -> dict:
    blog = db.query(Blog).filter(Blog.id == blog_id).first()
    if blog is None:
        raise HTTPException(status_code=404, detail="Blog not found")
    return row_to_blog(blog)


@app.post("/register", status_code=201, dependencies=[Depends(enforce_auth_rate_limit)])
def register(
    data: RegisterRequest, request: Request, db: Session = Depends(get_db)
) -> dict:
    _require_allowed_origin(request)
    existing = (
        db.query(User.id)
        .filter(or_(User.username == data.username, User.email == data.email))
        .first()
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Username or email is already registered")

    user = User(
        name=data.name,
        username=data.username,
        email=data.email,
        password_hash=hash_password(data.password),
        role="user",
        mobile_number=data.mobile_number,
    )
    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Username or email is already registered"
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Unable to create account") from exc
    return _safe_user(user)


@app.post("/login", dependencies=[Depends(enforce_auth_rate_limit)])
def login(
    request: Request,
    response: Response,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> dict:
    _require_allowed_origin(request)
    identifier = form.username.strip().lower()
    if len(identifier) > 254 or len(form.password.encode("utf-8")) > 128:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username/email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = (
        db.query(User)
        .filter(or_(User.username == identifier, User.email == identifier))
        .first()
    )
    if user is None or not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username/email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    now = datetime.now(timezone.utc)
    session_id = str(uuid.uuid4())
    session_expiry = now + timedelta(days=SESSION_DAYS)
    refresh_expiry = min(now + timedelta(days=REFRESH_TOKEN_DAYS), session_expiry)
    refresh_token = generate_refresh_token()
    csrf_token = generate_csrf_token()
    auth_session = AuthSession(
        id=session_id, user_id=user.id, created_at=now, expires_at=session_expiry
    )
    auth_session.refresh_tokens.append(
        RefreshToken(
            token_hash=hash_refresh_token(refresh_token),
            created_at=now,
            expires_at=refresh_expiry,
        )
    )
    try:
        db.add(auth_session)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Unable to start session") from exc

    _set_auth_cookies(
        response,
        refresh_token,
        csrf_token,
        int((refresh_expiry - now).total_seconds()),
    )
    return {
        **_issue_access_token(user, session_id),
        "user": _safe_user(user),
        "csrf_token": csrf_token,
    }


@app.get("/csrf")
def get_csrf_token(request: Request, response: Response) -> dict:
    _require_allowed_origin(request)
    csrf_token = request.cookies.get("blog_csrf") or generate_csrf_token()
    _set_csrf_cookie(response, csrf_token)
    return {
        "csrf_token": csrf_token,
        "has_refresh_session": bool(request.cookies.get("blog_refresh")),
    }


@app.post("/refresh")
def refresh(
    request: Request, response: Response, db: Session = Depends(get_db)
) -> dict:
    _require_csrf(request)
    token = request.cookies.get("blog_refresh")
    if not token:
        raise HTTPException(status_code=401, detail="Refresh session is missing")

    stored_token = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == hash_refresh_token(token))
        .with_for_update()
        .first()
    )
    if stored_token is None:
        _clear_auth_cookies(response)
        raise HTTPException(status_code=401, detail="Refresh session is invalid")

    now = datetime.now(timezone.utc)
    session = db.query(AuthSession).filter(AuthSession.id == stored_token.session_id).first()
    if session is None:
        _clear_auth_cookies(response)
        raise HTTPException(status_code=401, detail="Refresh session is invalid")

    if stored_token.revoked_at is not None:
        session.revoked_at = session.revoked_at or now
        db.query(RefreshToken).filter(
            RefreshToken.session_id == session.id, RefreshToken.revoked_at.is_(None)
        ).update({RefreshToken.revoked_at: now}, synchronize_session=False)
        db.commit()
        _clear_auth_cookies(response)
        raise HTTPException(status_code=401, detail="Refresh token reuse detected")

    if (
        session.revoked_at is not None
        or _as_utc(session.expires_at) <= now
        or _as_utc(stored_token.expires_at) <= now
    ):
        _clear_auth_cookies(response)
        raise HTTPException(status_code=401, detail="Refresh session has expired")

    user = db.query(User).filter(User.id == session.user_id).first()
    if user is None:
        session.revoked_at = now
        db.commit()
        _clear_auth_cookies(response)
        raise HTTPException(status_code=401, detail="Refresh session is invalid")

    new_refresh_token = generate_refresh_token()
    new_refresh_expiry = min(now + timedelta(days=REFRESH_TOKEN_DAYS), _as_utc(session.expires_at))
    new_row = RefreshToken(
        session_id=session.id,
        token_hash=hash_refresh_token(new_refresh_token),
        created_at=now,
        expires_at=new_refresh_expiry,
    )
    try:
        db.add(new_row)
        db.flush()
        stored_token.revoked_at = now
        stored_token.replaced_by_id = new_row.id
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Unable to refresh session") from exc

    csrf_token = request.cookies["blog_csrf"]
    _set_auth_cookies(
        response,
        new_refresh_token,
        csrf_token,
        max(0, int((new_refresh_expiry - now).total_seconds())),
    )
    return {**_issue_access_token(user, session.id), "csrf_token": csrf_token}


@app.post("/logout")
def logout(
    request: Request,
    response: Response,
    token: str = Depends(oauth2_scheme),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_csrf(request)
    auth_session_id = decode_access_token(token)[1]
    now = datetime.now(timezone.utc)
    session = (
        db.query(AuthSession)
        .filter(AuthSession.id == auth_session_id, AuthSession.user_id == user.id)
        .first()
    )
    if session is not None:
        session.revoked_at = session.revoked_at or now
        db.query(RefreshToken).filter(
            RefreshToken.session_id == session.id, RefreshToken.revoked_at.is_(None)
        ).update({RefreshToken.revoked_at: now}, synchronize_session=False)
        db.commit()
    _clear_auth_cookies(response)
    return {"message": "Logged out"}


@app.get("/me")
def get_me(user: User = Depends(get_current_user)) -> dict:
    return _private_user(user)


@app.patch("/me")
def update_me(
    data: MobileNumberUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    user.mobile_number = data.mobile_number
    try:
        db.commit()
        db.refresh(user)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Unable to update mobile number") from exc
    return _private_user(user)


def _require_blog_owner(blog: Blog, user: User) -> None:
    if blog.user_id != user.id:
        raise HTTPException(status_code=403, detail="You may manage only your own blogs")


@app.post("/blogs", status_code=201)
def add_blog(
    blog: BlogCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    db_blog = Blog(
        title=blog.title,
        description=blog.description,
        city=blog.city,
        email=str(blog.email),
        author=blog.author,
        user_id=user.id,
    )
    tag_ids = set(blog.tag_ids)
    if tag_ids:
        tags = db.query(Tag).filter(Tag.id.in_(tag_ids)).all()
        if len(tags) != len(tag_ids):
            raise HTTPException(status_code=400, detail="One or more tag IDs are invalid")
        db_blog.tags = tags
    try:
        db.add(db_blog)
        db.commit()
        db.refresh(db_blog)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Unable to create blog") from exc
    return row_to_blog(db_blog)


@app.put("/blogs/{blog_id}")
def update_blog_by_id(
    blog_id: int,
    blog: BlogUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    existing = db.query(Blog).filter(Blog.id == blog_id).first()
    if existing is None:
        raise HTTPException(status_code=404, detail="Blog not found")
    _require_blog_owner(existing, user)
    changes = blog.model_dump(exclude_unset=True)
    tag_ids = changes.pop("tag_ids", None)
    for field_name, value in changes.items():
        setattr(existing, field_name, str(value) if field_name == "email" else value)
    if tag_ids is not None:
        unique_tag_ids = set(tag_ids)
        tags = db.query(Tag).filter(Tag.id.in_(unique_tag_ids)).all() if unique_tag_ids else []
        if len(tags) != len(unique_tag_ids):
            raise HTTPException(status_code=400, detail="One or more tag IDs are invalid")
        existing.tags = tags
    try:
        db.commit()
        db.refresh(existing)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Unable to update blog") from exc
    return row_to_blog(existing)


@app.delete("/blogs/{blog_id}")
def delete_blog_by_id(
    blog_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    existing = db.query(Blog).filter(Blog.id == blog_id).first()
    if existing is None:
        raise HTTPException(status_code=404, detail="Blog not found")
    _require_blog_owner(existing, user)
    deleted = row_to_blog(existing)
    try:
        db.delete(existing)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Unable to delete blog") from exc
    return {"message": "Blog deleted successfully", "deleted": deleted}


@app.get("/users")
def get_users(db: Session = Depends(get_db)) -> list[dict]:
    users = db.query(User).order_by(User.id).all()
    return [{"id": user.id, "name": user.name} for user in users]


@app.post("/users", status_code=410)
def create_user() -> None:
    raise HTTPException(status_code=410, detail="Use POST /register to create an account")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
