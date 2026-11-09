# Authentication setup

## Configuration

Install dependencies and configure these environment variables for the API:

- `DATABASE_URL`: the existing PostgreSQL connection URL. PostgreSQL URLs are normalized to the installed `psycopg` driver.
- `JWT_SECRET_KEY`: a randomly generated secret of at least 32 bytes. Generate one with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Keep it in the Render environment settings or a local, ignored `.env` file.
- `FRONTEND_ORIGINS`: comma-separated, exact browser origins. Include the development frontend and deployed frontend; do not include paths or wildcards.
- `AUTH_COOKIE_SECURE=true` and `AUTH_COOKIE_SAMESITE=none` for Render's cross-site frontend/API deployment. For local HTTP development, use `AUTH_COOKIE_SECURE=false` and `AUTH_COOKIE_SAMESITE=lax`.

The refresh token is an HttpOnly cookie; the access token stays in frontend memory. Refresh and logout require the readable CSRF cookie to match the `X-CSRF-Token` header and an allowed browser origin. CORS credentials are limited to the configured origins.

## Schema migration

The migrations add nullable username, email, password-hash, and mobile-number columns so existing user rows remain intact, assign existing accounts the non-privileged `user` role, and create session/token tables and uniqueness indexes. Mobile numbers are private profile data: only the authenticated `/me` endpoints return them. Registration and public user/blog responses do not.

Review the migration and take a database backup before applying it to any deployed database. It is not run at application startup:

```sh
pip install -r requirements.txt
alembic current
alembic upgrade head
alembic current
```

Run this manually against a staging database first. Do not point local tests at the Render database. Downgrading removes authentication columns and session data; it does not remove existing users, blogs, tags, profiles, or blog-tag links. Back up first and coordinate any downgrade with deployed application versions.

Existing users without credentials cannot log in. Registration creates a new account and will not take over a password-less account; provide a separately verified and audited enrollment process before granting access to legacy accounts. Blogs whose `user_id` is `NULL` remain public but cannot be edited or deleted by ordinary users.

## Endpoints

- `POST /register`: create a normal user.
- `POST /login`: OAuth2 form fields `username` (username or email) and `password`; returns a 30-minute bearer access token and sets refresh/CSRF cookies.
- `POST /refresh`: rotate the refresh cookie; requires the CSRF cookie/header pair.
- `POST /logout`: revoke the current session; requires an access token and CSRF cookie/header pair.
- `GET /me`: return the authenticated user's profile, including their private mobile number.
- `PATCH /me`: update the authenticated user's own mobile number; send `{"mobile_number": "..."}` or `{"mobile_number": null}` to clear it.
- `GET /blogs` and `GET /blogs/{id}` remain public. Blog creation, update, and deletion require authentication and ownership.

User roles are not self-selectable; registration always creates a `user`. No admin-account bootstrap or email/password-reset delivery is configured.

## Tests and operational notes

Run `pytest -q`. The tests use isolated SQLite databases, including a migration test that starts with the existing schema and verifies sample records survive. They never connect to `DATABASE_URL`.

The authentication rate limiter is process-local, suitable as a baseline for this single-instance setup but not shared between multiple workers/instances. For multi-worker or high-traffic deployment, add a shared Redis/edge rate limit. Configure strong secrets and exact origins in Render before deploying; apply the migration explicitly and only after reviewing the target database.
