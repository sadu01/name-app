from datetime import datetime, timedelta, timezone
import hashlib
import uuid

import jwt

from auth import JWT_ISSUER, login_rate_limiter
from main import AuthSession, RefreshToken, User


ORIGIN = "http://testserver"


def register(client, username="alice", email="alice@example.com", password="correct-horse-battery"):
    return client.post(
        "/register",
        headers={"Origin": ORIGIN},
        json={
            "name": "Alice Example",
            "username": username,
            "email": email,
            "password": password,
        },
    )


def login(client, username="alice", password="correct-horse-battery"):
    response = client.post(
        "/login",
        headers={"Origin": ORIGIN},
        data={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()


def test_registration_hashes_password_and_returns_safe_user(client, test_db):
    response = register(client)
    assert response.status_code == 201
    assert response.json()["role"] == "user"
    assert "password_hash" not in response.json()

    with test_db() as db:
        user = db.query(User).filter(User.username == "alice").one()
        assert user.password_hash.startswith("$argon2")
        assert user.password_hash != "correct-horse-battery"


def test_registration_rejects_duplicate_username_or_email(client):
    assert register(client).status_code == 201
    assert register(client, email="different@example.com").status_code == 409
    assert register(client, username="different", email="alice@example.com").status_code == 409


def test_registration_validates_email_password_and_extra_privileges(client):
    invalid_email = register(client, email="not-an-email")
    weak_password = register(client, username="weakuser", email="weak@example.com", password="short")
    forged_role = client.post(
        "/register",
        headers={"Origin": ORIGIN},
        json={
            "name": "Mallory",
            "username": "mallory",
            "email": "mallory@example.com",
            "password": "correct-horse-battery",
            "role": "admin",
        },
    )
    assert invalid_email.status_code == 422
    assert weak_password.status_code == 422
    assert '"input"' not in weak_password.text
    assert forged_role.status_code == 422


def test_registration_does_not_claim_or_overwrite_legacy_user(client, test_db):
    with test_db() as db:
        legacy = User(id=42, name="Legacy User", password_hash=None)
        db.add(legacy)
        db.commit()

    response = register(
        client,
        username="legacy-login",
        email="legacy@example.com",
    )
    assert response.status_code == 201
    assert response.json()["id"] != 42
    with test_db() as db:
        legacy = db.get(User, 42)
        assert legacy.name == "Legacy User"
        assert legacy.password_hash is None


def test_legacy_accounts_without_valid_hash_cannot_log_in(client, test_db):
    with test_db() as db:
        db.add(
            User(
                name="Legacy Account",
                username="legacy-account",
                email="legacy-account@example.com",
                password_hash=None,
            )
        )
        db.add(
            User(
                name="Broken Hash",
                username="broken-hash",
                email="broken-hash@example.com",
                password_hash="not-a-valid-password-hash",
            )
        )
        db.commit()
    no_password = client.post(
        "/login", data={"username": "legacy-account", "password": "any-password"}
    )
    malformed_hash = client.post(
        "/login", data={"username": "broken-hash", "password": "any-password"}
    )
    assert no_password.status_code == 401
    assert malformed_hash.status_code == 401


def test_login_uses_generic_errors_and_emits_required_jwt_claims(client):
    register(client)
    assert client.post("/login", data={"username": "alice", "password": "wrong"}).status_code == 401
    assert client.post(
        "/login", data={"username": "unknown", "password": "correct-horse-battery"}
    ).status_code == 401

    auth_response = client.post(
        "/login",
        headers={"Origin": ORIGIN},
        data={"username": "alice", "password": "correct-horse-battery"},
    )
    result = auth_response.json()
    assert auth_response.headers["cache-control"] == "no-store"
    claims = jwt.decode(
        result["access_token"],
        "test-only-key-with-more-than-thirty-two-bytes",
        algorithms=["HS256"],
        issuer=JWT_ISSUER,
    )
    assert claims["sub"] == str(result["user"]["id"])
    assert claims["typ"] == "access"
    assert claims["sid"]
    assert claims["jti"]
    assert claims["iat"] <= claims["exp"]
    assert result["expires_in"] == 1800
    assert result["user"]["role"] == "user"
    assert "blog_refresh" not in result
    assert any(
        "blog_refresh=" in cookie and "httponly" in cookie.lower()
        for cookie in auth_response.headers.get_list("set-cookie")
    )


def test_refresh_cookie_uses_http_only_secure_cross_site_settings(client, monkeypatch):
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "true")
    monkeypatch.setenv("AUTH_COOKIE_SAMESITE", "none")
    register(client)
    response = client.post(
        "/login",
        headers={"Origin": ORIGIN},
        data={"username": "alice", "password": "correct-horse-battery"},
    )
    assert response.status_code == 200
    cookies = [value.lower() for value in response.headers.get_list("set-cookie")]
    refresh_cookie = next(cookie for cookie in cookies if cookie.startswith("blog_refresh="))
    csrf_cookie = next(cookie for cookie in cookies if cookie.startswith("blog_csrf="))
    assert "httponly" in refresh_cookie
    assert "secure" in refresh_cookie and "samesite=none" in refresh_cookie
    assert "secure" in csrf_cookie and "samesite=none" in csrf_cookie
    assert "httponly" not in csrf_cookie


def test_missing_invalid_expired_tampered_and_wrong_type_access_tokens(client):
    register(client)
    user = login(client)["user"]
    assert client.get("/me").status_code == 401
    assert client.get("/me", headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401

    now = datetime.now(timezone.utc)
    expired = jwt.encode(
        {
            "sub": str(user["id"]),
            "sid": str(uuid.uuid4()),
            "jti": str(uuid.uuid4()),
            "iat": now - timedelta(hours=1),
            "exp": now - timedelta(minutes=1),
            "typ": "access",
            "iss": JWT_ISSUER,
        },
        "test-only-key-with-more-than-thirty-two-bytes",
        algorithm="HS256",
    )
    assert client.get("/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401

    valid_token = client.post(
        "/login",
        headers={"Origin": ORIGIN},
        data={"username": "alice", "password": "correct-horse-battery"},
    ).json()["access_token"]
    parts = valid_token.split(".")
    parts[-1] = ("A" if parts[-1][-1] != "A" else "B") + parts[-1][1:]
    tampered = ".".join(parts)
    assert client.get("/me", headers={"Authorization": f"Bearer {tampered}"}).status_code == 401

    claims = jwt.decode(
        valid_token,
        "test-only-key-with-more-than-thirty-two-bytes",
        algorithms=["HS256"],
        issuer=JWT_ISSUER,
    )
    claims["typ"] = "refresh"
    wrong_type = jwt.encode(
        claims, "test-only-key-with-more-than-thirty-two-bytes", algorithm="HS256"
    )
    assert client.get("/me", headers={"Authorization": f"Bearer {wrong_type}"}).status_code == 401


def test_refresh_rotates_tokens_and_reuse_revokes_the_session(client, test_db):
    register(client)
    session_data = login(client)
    csrf = session_data["csrf_token"]
    old_refresh = client.cookies.get("blog_refresh")
    response = client.post(
        "/refresh",
        headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
    )
    assert response.status_code == 200
    new_refresh = client.cookies.get("blog_refresh")
    assert new_refresh and new_refresh != old_refresh

    with test_db() as db:
        old_row = db.query(RefreshToken).filter(
            RefreshToken.token_hash == hashlib.sha256(old_refresh.encode()).hexdigest()
        ).one()
        assert old_row.revoked_at is not None
        assert old_row.replaced_by_id is not None

    client.cookies.set("blog_refresh", old_refresh, domain="testserver.local", path="/")
    reused = client.post(
        "/refresh",
        headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
    )
    assert reused.status_code == 401
    assert client.get(
        "/me", headers={"Authorization": f"Bearer {session_data['access_token']}"}
    ).status_code == 401
    with test_db() as db:
        auth_session = db.query(AuthSession).one()
        assert auth_session.revoked_at is not None


def test_refresh_and_logout_require_csrf_and_logout_revokes_session(client):
    register(client)
    session_data = login(client)
    token = session_data["access_token"]
    csrf = session_data["csrf_token"]
    no_csrf = client.post("/refresh", headers={"Origin": ORIGIN})
    assert no_csrf.status_code == 403

    response = client.post(
        "/logout",
        headers={"Origin": ORIGIN, "X-CSRF-Token": csrf, "Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert client.get("/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    client.cookies.set("blog_csrf", csrf, domain="testserver.local", path="/")
    assert client.post(
        "/refresh", headers={"Origin": ORIGIN, "X-CSRF-Token": csrf}
    ).status_code == 401


def test_expired_refresh_token_is_rejected(client, test_db):
    register(client)
    session_data = login(client)
    with test_db() as db:
        token = db.query(RefreshToken).one()
        token.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    response = client.post(
        "/refresh",
        headers={"Origin": ORIGIN, "X-CSRF-Token": session_data["csrf_token"]},
    )
    assert response.status_code == 401


def test_login_enforces_rate_limit_and_origin_allowlist(client):
    login_rate_limiter.reset("testclient:/login")
    bad_origin = client.post(
        "/login",
        headers={"Origin": "https://untrusted.example"},
        data={"username": "alice", "password": "anything"},
    )
    assert bad_origin.status_code == 403
    login_rate_limiter.reset("testclient:/login")
    for _ in range(10):
        response = client.post(
            "/login", data={"username": "nobody", "password": "anything"}
        )
        assert response.status_code == 401
    limited = client.post("/login", data={"username": "nobody", "password": "anything"})
    assert limited.status_code == 429
