import asyncio
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from testcontainers.rabbitmq import RabbitMqContainer

from api import CreatingItem
from checker.checker_db.database.tables import Item_Checker


@pytest.mark.integration
async def test_api_checker_connection(
        rabbit_container: RabbitMqContainer,
        request_to_test_server_without_mock: AsyncClient,
        get_auth_token: dict[str, str],
        test_db_api: AsyncSession,
        test_db_checker: AsyncSession
):

        payload = CreatingItem(art='11111111', name='GTA 6', need_price=200, shop='wb')

        res = await request_to_test_server_without_mock.post(url='/create_item', cookies=get_auth_token, json=payload.model_dump(), timeout=5)

        item = None
        for _ in range(20):
            item = (await test_db_checker.execute(select(Item_Checker))).scalar_one_or_none()
            if item:
                break
            await asyncio.sleep(0.2)


        assert res.status_code == 201
        assert isinstance(item, Item_Checker)
