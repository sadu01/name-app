import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config


ROOT = Path(__file__).resolve().parents[1]


def test_authentication_migration_preserves_existing_database_rows(tmp_path):
    database_path = tmp_path / "existing.sqlite3"
    connection = sqlite3.connect(database_path)
    connection.executescript(
        """
        CREATE TABLE users (id INTEGER PRIMARY KEY, name VARCHAR NOT NULL);
        CREATE TABLE profiles (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
            city VARCHAR NOT NULL
        );
        CREATE TABLE blogs (
            id INTEGER PRIMARY KEY,
            title VARCHAR NOT NULL,
            description TEXT NOT NULL,
            city VARCHAR NOT NULL,
            email VARCHAR NOT NULL,
            author VARCHAR NOT NULL,
            date_created DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER NULL REFERENCES users(id)
        );
        CREATE TABLE tags (id INTEGER PRIMARY KEY, name VARCHAR NOT NULL UNIQUE);
        CREATE TABLE blog_tags (
            blog_id INTEGER NOT NULL REFERENCES blogs(id),
            tag_id INTEGER NOT NULL REFERENCES tags(id),
            PRIMARY KEY (blog_id, tag_id)
        );
        INSERT INTO users (id, name) VALUES (17, 'Existing User');
        INSERT INTO profiles (id, user_id, city) VALUES (23, 17, 'Existing City');
        INSERT INTO blogs (id, title, description, city, email, author, user_id)
            VALUES (31, 'Existing Blog', 'Keep this description', 'Existing City',
                    'existing@example.com', 'Existing Author', 17);
        INSERT INTO tags (id, name) VALUES (41, 'Existing Tag');
        INSERT INTO blog_tags (blog_id, tag_id) VALUES (31, 41);
        """
    )
    connection.commit()
    connection.close()

    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")
    command.upgrade(config, "9dcbc0c149f6")

    connection = sqlite3.connect(database_path)
    connection.execute(
        "UPDATE users SET mobile_number = ? WHERE id = 17",
        ("+155512345678901",),
    )
    connection.commit()
    connection.close()

    command.upgrade(config, "head")

    connection = sqlite3.connect(database_path)
    user = connection.execute(
        "SELECT id, name, username, email, password_hash, role, mobile_number "
        "FROM users WHERE id=17"
    ).fetchone()
    mobile_number_type = next(
        row[2]
        for row in connection.execute("PRAGMA table_info(users)").fetchall()
        if row[1] == "mobile_number"
    )
    blog = connection.execute(
        "SELECT id, title, description, user_id FROM blogs WHERE id=31"
    ).fetchone()
    profile_city = connection.execute(
        "SELECT city FROM profiles WHERE user_id=17"
    ).fetchone()[0]
    tag_name = connection.execute(
        "SELECT tags.name FROM tags JOIN blog_tags ON tags.id=blog_tags.tag_id "
        "WHERE blog_tags.blog_id=31"
    ).fetchone()[0]
    added_tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    connection.close()

    assert user == (17, "Existing User", None, None, None, "user", "+155512345678901")
    assert mobile_number_type == "VARCHAR(20)"
    assert blog == (31, "Existing Blog", "Keep this description", 17)
    assert profile_city == "Existing City"
    assert tag_name == "Existing Tag"
    assert {"auth_sessions", "refresh_tokens", "alembic_version"} <= added_tables
