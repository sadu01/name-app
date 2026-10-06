from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

from fastapi import FastAPI

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:5501",
        "http://localhost:5501",
        "https://sadu-pavan.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

people = [
    {
        "id": 1,
        "name": "Pavan",
        "details": {
            "age": 25,
            "city": "Hyderabad",
            "email": "pavan@example.com",
        },
    },
    {
        "id": 2,
        "name": "Rahul",
        "details": {
            "age": 28,
            "city": "Bangalore",
            "email": "rahul@example.com",
        },
    },
    {
        "id": 3,
        "name": "Suresh",
        "details": {
            "age": 30,
            "city": "Chennai",
            "email": "suresh@example.com",
        },
    },
    {
        "id": 4,
        "name": "Anil",
        "details": {
            "age": 22,
            "city": "Delhi",
            "email": "anil@example.com",
        },
    },
    {
        "id": 5,
        "name": "Vikram",
        "details": {
            "age": 27,
            "city": "Mumbai",
            "email": "vikram@example.com",
        },
    },
    {
        "id": 6,
        "name": "Ramesh",
        "details": {
            "age": 29,
            "city": "Kolkata",
            "email": "ramesh@example.com",
        },
    }
]


@app.get("/")
def home():
    return {"message": "API"}


@app.get("/names")
def get_names():
    return people


@app.get("/names/{name_id}")
def get_name_by_id(name_id: int):
    for person in people:
        if person["id"] == name_id:
            return person
    return {"error": "Name not found"}


@app.post("/names")
def add_name(name: str, details: dict):
    new_id = max(person["id"] for person in people) + 1
    new_person = {"id": new_id, "name": name, "details": details}
    people.append(new_person)
    return new_person


@app.put("/names/{name_id}")
def update_name_by_id(name_id: int, name: Optional[str] = None, details: Optional[dict] = None):
    for person in people:
        if person["id"] == name_id:
            if name is not None:
                person["name"] = name
            if details is not None:
                person["details"] = details
            return person
    return {"error": "Name not found"}


@app.delete("/names/{name_id}")
def delete_name_by_id(name_id: int, name: Optional[str] = None, details: Optional[dict] = None):
    for index, person in enumerate(people):
        if person["id"] == name_id:
            deleted_person = people.pop(index)
            return {"message": f"Name with id {name_id} deleted successfully.", "deleted": deleted_person}
    return {"error": "Name not found"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
