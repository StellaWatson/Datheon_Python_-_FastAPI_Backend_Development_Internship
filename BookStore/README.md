# BookStore API

An async REST API for managing a personal book collection, built with FastAPI, async SQLAlchemy and SQLite. Each user registers, logs in with a JWT and manages their own books. Admins can manage users and look at stats. Notifications run as background jobs, and the service runs in Docker.

## Internship tasks covered

| # | Task | Where to look |
|---|---|---|
| 1 | CRUD REST API with Pydantic validation, query filtering and Swagger docs | [`app/app.py`](app/app.py), [`app/schemas.py`](app/schemas.py) |
| 2 | Registration/login with JWT, password hashing, protected routes, roles (RBAC) | [`app/security.py`](app/security.py), [`app/admin.py`](app/admin.py) |
| 3 | SQLAlchemy ORM on SQLite, Users → Books relation, migrations, JOINs | [`app/database.py`](app/database.py), [`migrations/`](migrations/) |
| 4 | Background tasks, rate limiting, multi-stage Dockerfile | [`app/notifications.py`](app/notifications.py), [`app/rate_limit.py`](app/rate_limit.py), [`Dockerfile`](Dockerfile) |

## Tech stack

Python 3.13 · FastAPI · Uvicorn · Pydantic v2 · SQLAlchemy 2 (async) + aiosqlite · Alembic · PyJWT · Argon2 · httpx · pytest · Docker · [uv](https://docs.astral.sh/uv/)

## Quick start

### With Docker

```bash
git clone https://github.com/StellaWatson/Datheon_Python_-_FastAPI_Backend_Development_Internship.git
cd Datheon_Python_-_FastAPI_Backend_Development_Internship/BookStore

export SECRET_KEY=$(openssl rand -hex 32)
docker compose up -d --build
```

Open http://localhost:8000/docs. The database is stored in the `bookstore-data` Docker volume, so it survives restarts and rebuilds. Stop the service with `docker compose down`, or use `docker compose down -v` to delete the data as well.

### Without Docker

```bash
cd BookStore
uv sync
cp .env.example .env          # then set SECRET_KEY to a long random string
uv run python main.py         # http://127.0.0.1:8000/docs
```

The tables are created automatically the first time the app starts. To load sample data, run `uv run python seed.py`. It adds 20 books for `user@example.com` with password `stringst`.

## Using the API

1. Create an account with `POST /auth/register`.
2. Log in with `POST /auth/login`. It returns an `access_token`.
3. In Swagger, click **Authorize** and paste the token. Outside Swagger, send it as the `Authorization: Bearer <token>` header.

Example with curl:

```bash
curl -X POST localhost:8000/auth/register -H "Content-Type: application/json" \
  -d '{"username":"reader","email":"reader@example.com","password":"readerpass1"}'

TOKEN=$(curl -s -X POST localhost:8000/auth/login -H "Content-Type: application/json" \
  -d '{"email":"reader@example.com","password":"readerpass1"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

curl -X POST localhost:8000/books -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"title":"Dune","author":"Frank Herbert","price":12.5}'

curl "localhost:8000/books?author=herbert&sort_by=price&order=desc" -H "Authorization: Bearer $TOKEN"
```

### Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | none | Health check, also used by the Docker `HEALTHCHECK` |
| POST | `/auth/register` | none | Create an account (201, or 409 if the email or username is taken) |
| POST | `/auth/login` | none | Get a JWT access token |
| GET | `/auth/me` | user | The current user's profile and role |
| GET | `/books` | user | Your books. Query params: `author`, `sort_by=title\|price`, `order=asc\|desc`, `skip`, `limit` |
| POST | `/books` | user | Add a book |
| GET | `/books/{id}` | user | Get one of your books (404 if it isn't yours) |
| PUT | `/books/{id}` | user | Replace a book |
| DELETE | `/books/{id}` | user | Delete a book |
| GET | `/admin/users` | admin | List all users |
| PATCH | `/admin/users/{id}/role` | admin | Set a user's role to `user` or `admin` |
| PATCH | `/admin/users/{id}/active` | admin | Activate or deactivate a user |
| GET | `/admin/stats` | admin | Book count and total value per user (LEFT JOIN + GROUP BY) |
| GET | `/admin/notifications` | admin | Recent background jobs and their status |

### Status codes

`201` created · `401` missing or invalid token · `403` authenticated but not allowed (for example, a regular user calling `/admin`) · `404` not found or not owned by you · `409` duplicate email or username · `422` validation error (for example, a price ≤ 0 or a password shorter than 8 characters) · `429` rate limit exceeded

## How it works

### Authentication and roles

- Passwords are hashed with **Argon2**, not bcrypt. Argon2 is the newer recommended algorithm, and passlib, which the task suggested for bcrypt, is no longer maintained.
- Tokens are HS256 JWTs signed with `SECRET_KEY`. The `sub` claim holds the user id, and tokens expire after `ACCESS_TOKEN_EXPIRE_MINUTES`.
- `get_current_user` loads the user from the database on every request. This means a role change or a deactivation takes effect immediately, even for tokens that were already issued.
- `require_role(Role.ADMIN)` is a dependency that returns 403 to users without that role. The whole `/admin` router is guarded by it.
- New users get the `user` role. To promote the first admin, run:

  ```bash
  uv run python make_admin.py you@example.com                   # local
  docker compose exec api python make_admin.py you@example.com  # Docker
  ```

### Background jobs

The jobs use FastAPI `BackgroundTasks`. They run after the response has been sent, so the client never waits for them.

| Event | Job |
|---|---|
| User registers | Welcome email. It is simulated: logged and recorded, not actually sent. |
| User registers | `user.registered` webhook |
| Book created / deleted | `book.created` / `book.deleted` webhook |

Webhooks are sent as POST requests to `WEBHOOK_URL`, with up to 3 attempts and exponential backoff. If `WEBHOOK_URL` is not set, they are recorded as `skipped`. To see real deliveries, get a URL from https://webhook.site and set it before you start:

```bash
WEBHOOK_URL=https://webhook.site/<your-id> docker compose up -d
```

Every finished job (sent, delivered, skipped or failed) can be inspected at `GET /admin/notifications`.

### Rate limiting

A sliding-window limiter tracks requests per client IP:

- `/auth/register` and `/auth/login`: **5 requests per minute** combined. This protects against brute-force login attempts.
- `/books` and `/admin`: **60 requests per minute**.

Going over the limit returns `429 Too Many Requests` with a `Retry-After` header.

### Database and migrations

SQLite is accessed through SQLAlchemy's async engine. The tables are `users` and `books`, and `books.user_id` points to `users.id`. Every book query filters by the current user, so users can only see and change their own books.

The app creates any missing tables on startup. Schema changes to an existing database go through Alembic:

```bash
uv run alembic upgrade head
```

### Docker image

The [`Dockerfile`](Dockerfile) has two stages:

1. **builder**: installs the dependencies from `uv.lock` into a virtualenv with `uv sync --frozen --no-dev`.
2. **runtime**: copies only that virtualenv and the app code onto `python:3.13-slim`.

The resulting image is about 300 MB. It runs as a non-root user, has a `HEALTHCHECK` on `/health`, and keeps the SQLite file in a `/data` volume.

## Configuration

Settings are read from environment variables or a `.env` file. See [`.env.example`](.env.example).

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | (required) | Key used to sign JWTs |
| `ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Token lifetime |
| `DATABASE_URL` | `sqlite+aiosqlite:///./bookstore.db` | Set to `/data/bookstore.db` in Docker |
| `RATE_LIMIT_ENABLED` | `true` | Turns rate limiting on or off |
| `AUTH_RATE_LIMIT` | `5` | Auth requests per IP per window |
| `API_RATE_LIMIT` | `60` | Other requests per IP per window |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Window length |
| `WEBHOOK_URL` | unset | Where webhooks are sent |
| `WEBHOOK_TIMEOUT_SECONDS` | `5` | Timeout for each attempt |
| `WEBHOOK_MAX_RETRIES` | `3` | Maximum number of attempts |

## Tests

```bash
uv run pytest
```

There are 41 tests, covering:

- auth: registration, duplicates, validation and tokens
- book CRUD, filtering and sorting, and ownership between users
- roles (401 vs 403, promotion, deactivation)
- the stats JOIN
- background jobs and webhook retries, using a mocked HTTP transport
- rate limiting

The tests run against a separate `bookstore_test.db` that is rebuilt for every test.

## Project structure

```
BookStore/
├── app/
│   ├── app.py            # FastAPI app, auth and book routes
│   ├── admin.py          # admin-only router
│   ├── security.py       # hashing, JWT, get_current_user, require_role
│   ├── database.py       # engine, session, User/Book models, Role enum
│   ├── schemas.py        # Pydantic request/response models
│   ├── modules.py        # query helpers
│   ├── notifications.py  # background jobs: email + webhooks
│   ├── rate_limit.py     # sliding-window rate limiter
│   └── config.py         # settings (pydantic-settings)
├── migrations/           # Alembic
├── tests/
├── Dockerfile
├── docker-compose.yml
├── make_admin.py         # promote a user to admin
├── seed.py               # sample data
└── main.py               # local dev server with reload
```

## Known limitations

- The rate-limit counters and the job log are kept in process memory. That's fine for one Uvicorn worker, which is how the container runs. Running several workers or containers would need a shared store such as Redis, and a real job queue such as Celery, RQ or arq.
- The welcome email is simulated. Real delivery would need an SMTP server or an email provider's API.
- SQLite fits a single instance. To use PostgreSQL, change `DATABASE_URL` to `postgresql+asyncpg://...` and install `asyncpg`.
