import os
import tempfile
import unittest

from fastapi.testclient import TestClient

import main


class PeopleApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "people.db")
        main.DATABASE_PATH = self.db_path
        main.init_db()
        self.client = TestClient(main.app)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_and_read_person(self):
        response = self.client.post(
            "/names",
            json={
                "name": "Priya",
                "details": {
                    "age": 26,
                    "city": "Pune",
                    "email": "priya@example.com",
                },
            },
        )

        self.assertEqual(response.status_code, 201)
        person = response.json()
        self.assertEqual(person["name"], "Priya")
        self.assertEqual(person["details"]["city"], "Pune")

        response = self.client.get("/names")
        self.assertEqual(response.status_code, 200)
        people = response.json()
        self.assertEqual(len(people), 1)
        self.assertEqual(people[0]["name"], "Priya")

    def test_update_and_delete_person(self):
        create_response = self.client.post(
            "/names",
            json={
                "name": "Amit",
                "details": {"age": 31, "city": "Jaipur", "email": "amit@example.com"},
            },
        )
        person_id = create_response.json()["id"]

        response = self.client.put(
            f"/names/{person_id}",
            json={
                "name": "Amit Kumar",
                "details": {"age": 32, "city": "Jaipur", "email": "amit@example.com"},
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Amit Kumar")

        response = self.client.delete(f"/names/{person_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "Name deleted successfully")
        self.assertEqual(self.client.get("/names").json(), [])

    def test_partial_update_person(self):
        create_response = self.client.post(
            "/names",
            json={
                "name": "Neha",
                "details": {"age": 29, "city": "Lucknow", "email": "neha@example.com"},
            },
        )
        person_id = create_response.json()["id"]

        response = self.client.put(
            f"/names/{person_id}",
            json={"name": "Neha Sharma"},
        )

        self.assertEqual(response.status_code, 200)
        person = response.json()
        self.assertEqual(person["name"], "Neha Sharma")
        self.assertEqual(person["details"]["city"], "Lucknow")

    def test_create_rejects_invalid_name_age_and_email(self):
        valid_details = {"age": 26, "city": "Pune", "email": "priya@example.com"}
        invalid_people = [
            {"name": "Priya123", "details": valid_details},
            {"name": "Priya", "details": {**valid_details, "age": 0}},
            {"name": "Priya", "details": {**valid_details, "age": 111}},
            {"name": "Priya", "details": {**valid_details, "age": "26"}},
            {"name": "Priya", "details": {**valid_details, "email": "priya.example.com"}},
        ]

        for person in invalid_people:
            with self.subTest(person=person):
                response = self.client.post("/names", json=person)
                self.assertEqual(response.status_code, 422)

    def test_update_rejects_invalid_name_age_and_email(self):
        create_response = self.client.post(
            "/names",
            json={
                "name": "Priya",
                "details": {
                    "age": 26,
                    "city": "Pune",
                    "email": "priya@example.com",
                },
            },
        )
        person_id = create_response.json()["id"]
        invalid_updates = [
            {"name": "Priya123"},
            {"details": {"age": 0}},
            {"details": {"age": 111}},
            {"details": {"age": "26"}},
            {"details": {"email": "priya.example.com"}},
        ]

        for update in invalid_updates:
            with self.subTest(update=update):
                response = self.client.put(f"/names/{person_id}", json=update)
                self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
