import json
import os
import sqlite3
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, StrictInt, field_validator

DATABASE_PATH = os.environ.get("DATABASE_PATH", "people.db")


class PersonDetails(BaseModel):
    age: StrictInt = Field(ge=1, le=110)
    city: str
    email: str

    @field_validator("city")
    @classmethod
    def city_must_contain_letters_only(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or any(not character.isalpha() and character != " " for character in normalized):
            raise ValueError("City must contain letters and spaces only")
        return normalized

    @field_validator("email")
    @classmethod
    def email_must_contain_at(cls, value: str) -> str:
        if "@" not in value:
            raise ValueError("Email must contain @")
        return value


class PersonCreate(BaseModel):
    name: str
    details: PersonDetails

    @field_validator("name")
    @classmethod
    def name_must_contain_letters_only(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or any(not character.isalpha() and character != " " for character in normalized):
            raise ValueError("Name must contain letters and spaces only")
        return normalized


class PersonDetailsUpdate(BaseModel):
    age: Optional[StrictInt] = Field(default=None, ge=1, le=110)
    city: Optional[str] = None
    email: Optional[str] = None

    @field_validator("city")
    @classmethod
    def city_must_contain_letters_only(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized or any(not character.isalpha() and character != " " for character in normalized):
            raise ValueError("City must contain letters and spaces only")
        return normalized

    @field_validator("email")
    @classmethod
    def email_must_contain_at(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and "@" not in value:
            raise ValueError("Email must contain @")
        return value


class PersonUpdate(BaseModel):
    name: Optional[str] = None
    details: Optional[PersonDetailsUpdate] = None

    @field_validator("name")
    @classmethod
    def name_must_contain_letters_only(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized or any(not character.isalpha() and character != " " for character in normalized):
            raise ValueError("Name must contain letters and spaces only")
        return normalized


class Person(PersonCreate):
    id: int


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS people (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                details TEXT NOT NULL
            )
            """
        )


def row_to_person(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "details": json.loads(row["details"]),
    }


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:5501",
        "http://localhost:5501",
        "https://name-app-frontend.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()


@app.get("/")
def home():
    return {"message": "API"}


@app.get("/names")
def get_names():
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT id, name, details FROM people ORDER BY id"
        ).fetchall()
    return [row_to_person(row) for row in rows]


@app.get("/names/{name_id}")
def get_name_by_id(name_id: int):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, name, details FROM people WHERE id = ?",
            (name_id,),
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Name not found")
    return row_to_person(row)


@app.post("/names", status_code=201)
def add_name(person: PersonCreate):
    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO people (name, details) VALUES (?, ?)",
            (person.name, json.dumps(person.details.model_dump())),
        )
        person_id = cursor.lastrowid

    return {"id": person_id, "name": person.name, "details": person.details.model_dump()}


@app.put("/names/{name_id}")
def update_name_by_id(name_id: int, person: PersonUpdate):
    with get_connection() as connection:
        existing = connection.execute(
            "SELECT id, name, details FROM people WHERE id = ?",
            (name_id,),
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Name not found")

        updated_name = person.name if person.name is not None else existing["name"]
        current_details = json.loads(existing["details"])
        updated_details = current_details.copy()

        if person.details is not None:
            for field, value in person.details.model_dump().items():
                if value is not None:
                    updated_details[field] = value

        connection.execute(
            "UPDATE people SET name = ?, details = ? WHERE id = ?",
            (updated_name, json.dumps(updated_details), name_id),
        )

    return {"id": name_id, "name": updated_name, "details": updated_details}


@app.delete("/names/{name_id}")
def delete_name_by_id(name_id: int):
    with get_connection() as connection:
        existing = connection.execute(
            "SELECT id, name, details FROM people WHERE id = ?",
            (name_id,),
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Name not found")

        connection.execute("DELETE FROM people WHERE id = ?", (name_id,))

    return {"message": "Name deleted successfully", "deleted": row_to_person(existing)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
