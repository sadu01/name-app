from sqlalchemy.exc import SQLAlchemyError

from database import get_db
from main import Blog, Tag, User, app


ORIGIN = "http://testserver"


def register_and_login(client, username):
    response = client.post(
        "/register",
        headers={"Origin": ORIGIN},
        json={
            "name": username.title(),
            "username": username,
            "email": f"{username}@example.com",
            "password": "a-strong-password-123",
        },
    )
    assert response.status_code == 201
    response = client.post(
        "/login",
        headers={"Origin": ORIGIN},
        data={"username": username, "password": "a-strong-password-123"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def blog_payload(**changes):
    payload = {
        "title": "A Blog",
        "description": "A useful description",
        "city": "London",
        "email": "blog@example.com",
        "author": "Alice",
        "tag_ids": [1],
    }
    return {**payload, **changes}


def test_public_blog_reads_and_documentation(client):
    assert client.get("/blogs").status_code == 200
    assert client.get("/blogs/999").status_code == 404
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json").json()
    assert schema["components"]["securitySchemes"]["OAuth2PasswordBearer"]["flows"]["password"][
        "tokenUrl"
    ] == "/login"


def test_blog_responses_never_expose_mobile_numbers(client):
    registration = client.post(
        "/register",
        headers={"Origin": ORIGIN},
        json={
            "name": "Alice Example",
            "username": "alice",
            "email": "alice@example.com",
            "password": "a-strong-password-123",
            "mobile_number": "+12025550123",
        },
    )
    assert registration.status_code == 201
    token = register_and_login(client, "bob")
    created = client.post(
        "/blogs",
        headers={"Authorization": f"Bearer {token}"},
        json=blog_payload(tag_ids=[]),
    )
    assert created.status_code == 201
    assert "mobile_number" not in created.json()
    assert "mobile_number" not in client.get("/blogs").json()[0]
    assert "mobile_number" not in client.get(
        f"/blogs/{created.json()['id']}"
    ).json()


def test_database_errors_return_cors_visible_service_unavailable(client):
    original_override = app.dependency_overrides[get_db]

    def failed_db():
        raise SQLAlchemyError("private database details")
        yield

    app.dependency_overrides[get_db] = failed_db
    try:
        response = client.get("/blogs", headers={"Origin": ORIGIN})
    finally:
        app.dependency_overrides[get_db] = original_override

    assert response.status_code == 503
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert response.json() == {"detail": "Database operation failed"}
    assert "private database details" not in response.text


def test_blog_create_requires_auth_and_never_uses_client_owner(client, test_db):
    unauthenticated = client.post("/blogs", json=blog_payload())
    assert unauthenticated.status_code == 401

    token = register_and_login(client, "alice")
    with test_db() as db:
        db.add(Tag(id=1, name="King"))
        db.commit()
    forged = client.post(
        "/blogs",
        headers={"Authorization": f"Bearer {token}"},
        json=blog_payload(user_id=999),
    )
    assert forged.status_code == 422

    created = client.post(
        "/blogs",
        headers={"Authorization": f"Bearer {token}"},
        json=blog_payload(),
    )
    assert created.status_code == 201
    body = created.json()
    assert body["user_id"] > 0
    assert body["tags"] == ["King"]
    assert body["user_name"] == "Alice"

    public_response = client.get(f"/blogs/{body['id']}")
    assert public_response.status_code == 200
    assert public_response.json()["tags"] == ["King"]
    assert client.post(
        "/blogs",
        headers={"Authorization": f"Bearer {token}"},
        json=blog_payload(tag_ids=[999]),
    ).status_code == 400


def test_only_owner_can_update_or_delete_blog(client, test_db):
    owner_token = register_and_login(client, "owner")
    other_token = register_and_login(client, "other")
    with test_db() as db:
        db.add(Tag(id=1, name="King"))
        db.commit()
    created = client.post(
        "/blogs",
        headers={"Authorization": f"Bearer {owner_token}"},
        json=blog_payload(),
    )
    blog_id = created.json()["id"]

    assert client.put(
        f"/blogs/{blog_id}",
        headers={"Authorization": f"Bearer {other_token}"},
        json={"title": "Other title"},
    ).status_code == 403
    updated = client.put(
        f"/blogs/{blog_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"title": "Updated title"},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Updated title"
    assert updated.json()["tags"] == ["King"]
    cleared_tags = client.put(
        f"/blogs/{blog_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"tag_ids": []},
    )
    assert cleared_tags.status_code == 200
    assert cleared_tags.json()["tags"] == []
    assert client.put(
        f"/blogs/{blog_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"title": "Should roll back", "tag_ids": [999]},
    ).status_code == 400
    assert client.get(f"/blogs/{blog_id}").json()["title"] == "Updated title"
    restored_tags = client.put(
        f"/blogs/{blog_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"tag_ids": [1]},
    )
    assert restored_tags.json()["tags"] == ["King"]
    assert client.put(
        f"/blogs/{blog_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"user_id": 2},
    ).status_code == 422

    assert client.delete(
        f"/blogs/{blog_id}", headers={"Authorization": f"Bearer {other_token}"}
    ).status_code == 403
    deleted = client.delete(
        f"/blogs/{blog_id}", headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert deleted.status_code == 200
    assert deleted.json()["deleted"]["id"] == blog_id
    assert client.get(f"/blogs/{blog_id}").status_code == 404


def test_legacy_unowned_blog_cannot_be_claimed_and_user_endpoint_is_closed(client, test_db):
    token = register_and_login(client, "newuser")
    with test_db() as db:
        db.add(User(id=100, name="Old Account"))
        db.flush()
        db.add(
            Blog(
                title="Legacy",
                description="Existing blog",
                city="Paris",
                email="old@example.com",
                author="Old Author",
                user_id=None,
            )
        )
        db.commit()
        legacy_blog = db.query(Blog).one()
        legacy_blog_id = legacy_blog.id

    assert client.put(
        f"/blogs/{legacy_blog_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Claim it"},
    ).status_code == 403
    assert client.delete(
        f"/blogs/{legacy_blog_id}", headers={"Authorization": f"Bearer {token}"}
    ).status_code == 403
    assert client.post("/users", json={"name": "Insecure"}).status_code == 410
    assert all("password_hash" not in user for user in client.get("/users").json())
