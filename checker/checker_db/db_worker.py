from faststream.rabbit import RabbitQueue, RabbitBroker
from faststream import Depends, FastStream
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import NoResultFound
from sqlalchemy import select
from typing import Any

if __package__:
    from .database.engine import ses_control_db
    from .database.tables import Item_Checker
    from .models import UpdateItem
    from .config import rabbit_settings
    from .log_conf import logger
else:
    from database.engine import ses_control_db
    from database.tables import Item_Checker
    from models import UpdateItem
    from config import rabbit_settings
    from log_conf import logger

log = logger()

broker = RabbitBroker(url=rabbit_settings.rabbitmq_url)
queue_db = RabbitQueue(name='db', durable=True)

app = FastStream(broker)


@broker.subscriber(queue_db)
async def insert_in_db(msg: dict[str, Any], ses: AsyncSession = Depends(ses_control_db)):
    """listening messege from API, change DB"""

    log.info('DB worker is starting')
    if 'created' in msg:
        data = msg['created']
        new_item = Item_Checker(name=data.get('name'), art=data.get('art'), shop=data.get('shop'), need_price=data.get('need_price'), id=msg['id'], email=data.get('email'))
        ses.add(new_item)
        await ses.commit()

        return {'status': 200}

    
    if 'deleted' in msg:
        try:
            data = msg['deleted']
            t_id = data.get('id')
            deletion = select(Item_Checker).filter(Item_Checker.id==t_id)
            del_item = await ses.execute(deletion)
            res = del_item.scalars().first()
            await ses.delete(res)
            await ses.commit()
            
            return {'status': 200}

        except NoResultFound as e:
            log.info(e)
            raise e
    

    if 'patched' in msg:
        try:
            payload = msg['patched']
            payload = UpdateItem(**payload)
            update_data = payload.model_dump(exclude_unset=True, exclude_none=True)
            item_id: int = msg['item_id']
            query = select(Item_Checker).filter_by(id=item_id)
            item = await ses.execute(query)
            item = item.scalar_one_or_none()

            if not item:
                return {'status': 404, 'details': 'item not found'}

            for k, v in update_data.items():
                setattr(item, k, v)
            

            await ses.commit()
            await ses.refresh(item)


            return {'status': 200}

        except NoResultFound as e:
            log.info(e)

