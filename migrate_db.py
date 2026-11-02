import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

backup = Path("new_project_db.dump")

if not backup.is_file():
    raise SystemExit("Backup file not found!")

required = [
    "RENDER_DB_HOST",
    "RENDER_DB_PORT",
    "RENDER_DB_NAME",
    "RENDER_DB_USER",
    "RENDER_DB_PASSWORD",
]

for key in required:
    if not os.getenv(key):
        raise SystemExit(f"Missing environment variable: {key}")

env = os.environ.copy()
env["PGPASSWORD"] = os.environ["RENDER_DB_PASSWORD"]
env["PGSSLMODE"] = os.getenv("RENDER_DB_SSLMODE", "require")

command = [
    "pg_restore",
    "--no-owner",
    "--no-privileges",
    "--exit-on-error",
    "-h", os.environ["RENDER_DB_HOST"],
    "-p", os.environ["RENDER_DB_PORT"],
    "-U", os.environ["RENDER_DB_USER"],
    "-d", os.environ["RENDER_DB_NAME"],
    str(backup),
]

print("Connecting to Render PostgreSQL...")

result = subprocess.run(
    command,
    env=env,
    capture_output=True,
    text=True,
)

if result.returncode == 0:
    print("Database migration successful!")
else:
    print("Database migration failed.")
    print("Error:", result.stderr.replace(
        os.environ["RENDER_DB_PASSWORD"], "[REDACTED]"
    ))