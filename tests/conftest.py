import os
from urllib.parse import quote

from dotenv import dotenv_values

_env = dotenv_values(".env")
_user = quote(_env.get("POSTGRES_USER", "postgres"), safe="")
_password = quote(_env.get("POSTGRES_PASSWORD", ""), safe="")

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    f"postgresql+asyncpg://{_user}:{_password}@localhost:5433/pastebin_test",
)
os.environ["REDIS_URL"] = os.environ.get("TEST_REDIS_URL", "redis://localhost:6380/15")
os.environ["COOKIE_SECURE"] = "false"
os.environ["S3_ENDPOINT"] = os.environ.get("TEST_S3_ENDPOINT", "http://localhost:3900")

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import make_url, text
from sqlmodel import SQLModel

from src import app
from src.db.main import async_engine
from src.db.redis import redis_client
from src.celery_app import celery_app

celery_app.conf.task_always_eager = True
celery_app.conf.task_eager_propagates = True

TEST_PASSWORD = "correct-horse-battery"


async def _create_test_database():
    url = make_url(os.environ["DATABASE_URL"])
    conn = await asyncpg.connect(
        user=url.username,
        password=url.password,
        host=url.host,
        port=url.port,
        database=_env.get("POSTGRES_DB", "postgres"),
    )
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", url.database
        )
        if not exists:
            await conn.execute(f'CREATE DATABASE "{url.database}"')
    finally:
        await conn.close()


@pytest.fixture(scope="session", autouse=True)
async def database():
    await _create_test_database()
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    yield
    await async_engine.dispose()
    await redis_client.aclose()


@pytest.fixture(autouse=True)
async def clean_state():
    tables = ", ".join(t.name for t in SQLModel.metadata.sorted_tables)
    async with async_engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} CASCADE"))
    await redis_client.flushdb()
    yield


@pytest.fixture
async def make_client():
    clients = []

    async def _make():
        c = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        clients.append(c)
        return c

    yield _make
    for c in clients:
        await c.aclose()


@pytest.fixture
async def client(make_client):
    return await make_client()


async def login_as(client: AsyncClient, email: str) -> AsyncClient:
    r = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": TEST_PASSWORD}
    )
    assert r.status_code == 200, r.text
    r = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD}
    )
    assert r.status_code == 200, r.text
    return client


@pytest.fixture
async def alice(make_client):
    return await login_as(await make_client(), "alice@example.com")


@pytest.fixture
async def bob(make_client):
    return await login_as(await make_client(), "bob@example.com")


async def run_sql(sql: str, **params):
    async with async_engine.begin() as conn:
        await conn.execute(text(sql), params)
