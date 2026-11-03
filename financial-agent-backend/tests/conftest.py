"""
Shared pytest fixtures.

Each test module gets an isolated in-memory SQLite database. The FastAPI
dependency is overridden so no test ever touches the developer database.
"""

from __future__ import annotations

from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.seed import seed_default_categories
from app.main import app

TEST_PASSWORD = "Password123!"


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _fk_pragma(dbapi_connection, connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(db_engine):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        await seed_default_categories(session)
        await session.commit()
    return factory


@pytest_asyncio.fixture
async def client(session_factory) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
    app.dependency_overrides.clear()


async def register_user(
    client: AsyncClient,
    email: str = "student@example.com",
    full_name: str = "Test Student",
) -> str:
    """Register a user and return the bearer token."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": TEST_PASSWORD, "full_name": full_name},
    )
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def auth_client(client: AsyncClient) -> tuple[AsyncClient, dict[str, str]]:
    token = await register_user(client)
    return client, bearer(token)
