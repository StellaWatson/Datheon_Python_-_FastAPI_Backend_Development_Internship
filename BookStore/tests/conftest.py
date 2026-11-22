import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession
)
from sqlalchemy.pool import NullPool

from app.app import app
from sqlalchemy import update

from app.database import Base, Role, User, get_db
from app.notifications import notification_log
from app.rate_limit import ALL_LIMITERS


# -------------------------
# TEST DATABASE
# -------------------------
# A separate SQLite file so tests never touch bookstore.db.
# NullPool: every connection is opened and closed immediately,
# which avoids "database is locked" problems between asyncio.run() calls.

TEST_DATABASE_URL = "sqlite+aiosqlite:///./bookstore_test.db"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    poolclass=NullPool
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def get_test_db():
    async with TestingSessionLocal() as session:
        yield session


# Tell the lifespan not to run create_tables()/dispose() on the real engine.
app.state.testing = True


# -------------------------
# FIXTURES
# -------------------------

@pytest.fixture
def client():
    """
    Fresh app client with an empty test database for every test.

    The override is installed HERE, not at module import time,
    so it is guaranteed to be present for every test, and it is
    removed with pop() so we only undo what we added.
    """
    app.dependency_overrides[get_db] = get_test_db

    # In-memory state must not leak between tests.
    for limiter in ALL_LIMITERS:
        limiter.reset()
    notification_log.clear()

    async def setup_database():
        async with test_engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.run_sync(Base.metadata.create_all)

    async def cleanup_database():
        async with test_engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
        await test_engine.dispose()

    asyncio.run(setup_database())

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        asyncio.run(cleanup_database())
        app.dependency_overrides.pop(get_db, None)


def register_and_login(client, username, email, password):
    """
    Helper: register a brand-new user and return auth headers.

    The database is empty at the start of every test, so registration
    MUST succeed. If it ever returns 409, the test DB isolation is broken
    and we want the test to fail loudly rather than fall back to login.
    """
    register_response = client.post(
        "/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password
        }
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/auth/login",
        json={"email": email, "password": password}
    )
    assert login_response.status_code == 200

    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers(client):
    """User A: the main test user."""
    return register_and_login(
        client,
        username="test_user",
        email="user@example.com",
        password="stringst"
    )


@pytest.fixture
def user_b_headers(client):
    """User B: a second user, used for ownership tests."""
    return register_and_login(
        client,
        username="stella",
        email="stella@example.com",
        password="stella2407"
    )


def create_book(client, headers, title="Old Book", author="Old Author", price=10.0):
    """Helper: create a book and return its id."""
    response = client.post(
        "/books",
        json={"title": title, "author": author, "price": price},
        headers=headers
    )
    assert response.status_code == 201
    return response.json()["id"]


def promote_to_admin(email):
    """Helper: set a user's role to admin directly in the test DB."""
    async def _promote():
        async with TestingSessionLocal() as session:
            await session.execute(
                update(User)
                .where(User.email == email)
                .values(role=Role.ADMIN.value)
            )
            await session.commit()

    asyncio.run(_promote())


@pytest.fixture
def admin_headers(client):
    """An admin user. Role is checked from the DB on each request."""
    headers = register_and_login(
        client,
        username="admin",
        email="admin@example.com",
        password="adminpass123"
    )
    promote_to_admin("admin@example.com")
    return headers
