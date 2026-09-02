import os
import tempfile
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine
from testcontainers.rabbitmq import RabbitMqContainer
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from fast_depends import dependency_provider
from collections.abc import AsyncGenerator


def _write_test_jwt_keys() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    directory = Path(tempfile.mkdtemp())
    private_path = directory / "private_key.pem"
    public_path = directory / "public_key.pem"
    private_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    public_path.write_bytes(
        key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    return str(private_path), str(public_path)


os.environ["PRIVATE_KEY_PATH"], os.environ["PUBLIC_KEY_PATH"] = _write_test_jwt_keys()

from api import app, db_helper, broker, Base, encode_jwt
from checker.checker_db.database.engine import ses_control_db
from checker.checker_db.database.tables import Base as c_Base
from checker.checker_db.db_worker import broker as c_broker
from sqlalchemy.pool import StaticPool

url_api = 'sqlite+aiosqlite:///file:API?mode=memory&cache=shared'
url_checker = 'sqlite+aiosqlite:///file:CHEKCER?mode=memory&cache=shared'


@pytest.fixture(scope='function')
async def async_engine_api():
    engine = create_async_engine(url=url_api, poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture(scope='function')
async def async_engine_checker():
    engine = create_async_engine(url=url_checker, poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(c_Base.metadata.drop_all)
        await conn.run_sync(c_Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def test_db_api(async_engine_api: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    async with async_engine_api.connect() as conn:
        async with conn.begin() as trans:
            async_session = AsyncSession(bind=conn, expire_on_commit=False)

            app.dependency_overrides[db_helper] = lambda: async_session

            yield async_session

            app.dependency_overrides.clear()

            await trans.rollback()


@pytest.fixture
async def test_db_checker(async_engine_checker: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    async with async_engine_checker.connect() as conn:
        async with conn.begin() as trans:
            async_session = AsyncSession(bind=conn, expire_on_commit=False)

            dependency_provider.override(ses_control_db, lambda: async_session)

            yield async_session


            dependency_provider.clear()


            await trans.rollback()


@pytest.fixture
async def request_to_test_server():
    original_publish = broker.publish

    broker.publish = AsyncMock(return_value=None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://localhost') as c:
        yield c

    broker.publish = original_publish


@pytest.fixture
async def request_to_test_server_without_mock(rabbit_container: RabbitMqContainer):
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://localhost') as c:
        yield c


@pytest.fixture
async def get_auth_token():
    token = encode_jwt(payload={'id': 1, 'sub': 'bogdanlavrenenko@gmail.com'})

    cookie = {'web-app-session-id': token}

    return cookie


@pytest.fixture
async def rabbit_container():
    rabbit = RabbitMqContainer()
    rabbit.start()
    params = rabbit.get_connection_params()
    cred = params.credentials
    amqp_url = f"amqp://{cred.username}:{cred.password}@{params.host}:{params.port}/"

    broker._connection_kwargs["url"] = amqp_url
    c_broker._connection_kwargs["url"] = amqp_url

    try:
        await broker.start()
        await c_broker.start()
        yield rabbit
    finally:
        await broker.stop()
        await c_broker.stop()
        rabbit.stop()










