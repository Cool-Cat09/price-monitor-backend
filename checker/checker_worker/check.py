import asyncio
import httpx
from httpx import URL
from faststream.rabbit import RabbitBroker, RabbitQueue
from faststream import FastStream
from sqlalchemy import select
from playwright.async_api import async_playwright

from typing import Any

if __package__:
    from .database.engine import ses_control, engine
    from .database.tables import Item_Checker
    from .check_base import PARAMS, URLS
    from .config import rabbit_settings
    from .log_conf import logger
else:
    from database.engine import ses_control, engine
    from database.tables import Item_Checker
    from check_base import PARAMS, URLS
    from config import rabbit_settings
    from log_conf import logger


#in infinity loop checking need_price from BD and compare with parsing data from sites

log = logger()

broker = RabbitBroker(url=rabbit_settings.rabbitmq_url)
app = FastStream(broker)

queue_mail = RabbitQueue(name='mail_queue', durable=True)
queue_cron = RabbitQueue(name='crone', durable=True)

semaphore = asyncio.Semaphore(8)



async def parse_json(url: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        async with page.expect_response(lambda response: "/cards/v4/detail" in response.url and response.status == 200) as response:
            await page.goto(url)
            response = await response.value
            res = await response.json()
            
        await browser.close()

        
        return res


async def process_item(item: Item_Checker, client: httpx.AsyncClient):
    """handle one item: parse site and send email"""


    url = URLS.get(item.shop) + item.art #type: ignore
    price_hadler = PARAMS.get(item.shop)
    if not url or not price_hadler:
        log.warning(f'There is no parser for {item.shop}.')
        return

    data = await parse_json(url=url) #type: ignore

    try:
        price_val = price_hadler(data=data) #type: ignore
        log.info(f'shop-{item.shop}, price-{price_val}, target-{item.need_price}')

        if price_val <= item.need_price:
            await broker.publish(message={'status': 'fell', 'email': item.email, 'shop': item.shop, 'name': item.name, 'price': price_val}, queue=queue_mail)
            log.info('the message was send.')
    except Exception as e:
        log.error(e)


@broker.subscriber(queue_cron)
async def db_checker(msg: dict[str, Any]):
    """worker for checking DB"""


    log.info('worker was started')
    async with httpx.AsyncClient(verify=True) as client:
            try:
                async with ses_control() as ses:
                    query = select(Item_Checker)
                    res = await ses.execute(query)
                    items = res.scalars().all()

                if not items:
                    log.info('no items to check')
                else:
                    tasks = [process_item(item, client) for item in items]
                    await asyncio.gather(*tasks)
            except Exception as e:
                log.error(e)


@app.after_shutdown
async def close():
    await engine.dispose()


if __name__ == "__main__":
    app.run() #type: ignore

