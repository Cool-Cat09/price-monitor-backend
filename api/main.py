# main fastapi app

import asyncio
from fastapi import FastAPI, Depends, HTTPException, status, Form, Response, Cookie
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from faststream.rabbit import RabbitQueue, RabbitBroker
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError, NoResultFound
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import uuid

from typing import Any

if __package__:
    from .database.engine import engine, Session
    from .database.tables import Item
    from .api_func import create_item, list_of_items, patching, create_user, search_user_by_name
    from .models import CreatingItem, UpdateItem, CreatingUser, UserSchema, ItemSchema
    from .database.pass_to_hash import hash_pass, check_pass
    from .token_issuence import encode_jwt, decode_jwt
    from .config import rabbit_settings, api_settings
    from .log_conf import logger
else:
    from database.engine import engine, Session
    from database.tables import Item
    from api_func import create_item, list_of_items, patching, create_user, search_user_by_name
    from models import CreatingItem, UpdateItem, CreatingUser, UserSchema, ItemSchema
    from database.pass_to_hash import hash_pass, check_pass
    from token_issuence import encode_jwt, decode_jwt
    from config import rabbit_settings, api_settings
    from log_conf import logger

log = logger()

broker = RabbitBroker(url=rabbit_settings.rabbitmq_url)
queue = RabbitQueue(name='db', durable=True)

outbox_event = asyncio.Event()


async def send_cron_trigger():
    await broker.publish(message={'trigger': 'now',}, queue='crone')


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with broker:
        scheduler = AsyncIOScheduler()
        scheduler.add_job(send_cron_trigger, 'interval', seconds=60)
        scheduler.start()
        yield 
    await engine.dispose()

app = FastAPI(lifespan=lifespan)

origins = [
    'http://localhost:8000',
    'https://localhost:443',
    'http://127.0.0.1:8000',
    'https://127.0.0.1:443',
    api_settings.api_url,
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


async def db_helper():
    """dependence to gives sessions
    
    !!!Dependence
    """


    async with Session() as ses:
        try:
            yield ses
        except IntegrityError as e:
            await ses.rollback()
            log.error(e)
            raise e
        except Exception as e:
            await ses.rollback()
            log.error(e)
            raise e
        finally: 
            await ses.close()


COOKIE_SESSION_ID_KEY = 'web-app-session-id'


def gen_ses_id():
    return uuid.uuid4().hex


async def authentication(response: Response, username: str = Form(), password: str = Form(), ses: AsyncSession = Depends(db_helper)):
    """create jwt when user do aunthentication

    !!!Dependence
    """


    try:
        user = await search_user_by_name(username=username, ses=ses)
    except:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='user is not found')

    if check_pass(password=password, hashed_password=user.password):
        token = encode_jwt(payload={'id': user.id, 'sub': user.email})
        response.set_cookie(COOKIE_SESSION_ID_KEY, value=token, max_age=86400, httponly=True, samesite='lax')
        return user
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid password')


async def authorization(response: Response, token: str = Cookie(alias=COOKIE_SESSION_ID_KEY)):
    """check jwt and gives user
    
    !!!Dependence
    """
    

    try:
        payload = decode_jwt(token=token)
        now = int(datetime.now(timezone.utc).timestamp())
        time_left =payload['exp'] - now
        if time_left < 300:
            token = encode_jwt(payload={'id': payload['id'], 'sub': payload['sub']})
            response.set_cookie(key=COOKIE_SESSION_ID_KEY, value=token, max_age=1380, httponly=True, samesite='lax')
        return payload

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=e)


@app.get('/health', status_code=status.HTTP_200_OK)
async def health():
    return {'status': 200, 'health': 'ok'}


@app.post(
        '/authentication', status_code=status.HTTP_200_OK, 
        response_model=UserSchema, 
        responses={401: {'description': 'invalid password'}, 404: {'description': 'user is not found'}
        }
)
async def loging(user: UserSchema = Depends(authentication)):
    return user


@app.get('/', 
        status_code=status.HTTP_200_OK, 
        response_model=list[ItemSchema], 
        responses={401: {'description': ''}})
async def list_of_user_items(user: dict[str, Any] = Depends(authorization), db: AsyncSession = Depends(db_helper)):
    try:
        result = await list_of_items(ses=db, user_id=user['id'])
        return result
    except Exception as e:
        log.error(e)

@app.delete(
        '/delete_item', 
        status_code=status.HTTP_200_OK, 
        response_model=CreatingItem, 
        responses={
            403: {'description': ''}, 
            404: {'description': 'item doesnt exist'}, 
            401: {'description': ''}
        }
)
async def deleting_item(id: int, user: dict[str, Any] = Depends(authorization),  ses: AsyncSession = Depends(db_helper)):
    try:
        item = select(Item).filter_by(id=id, user_id=user['id'])
        del_item = await ses.execute(item)
        result = del_item.scalar_one()
        res_data = {'id': result.id}
        await broker.publish(message={'deleted': res_data}, queue=queue)
        await ses.delete(result)
        await ses.commit()
        return result
    except AttributeError:
        await ses.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='item doesnt exist')
    except NoResultFound:
        await ses.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='item doesnt exist')


@app.post(
        '/create_item', 
        status_code=status.HTTP_201_CREATED, 
        response_model=CreatingItem, 
        responses={
            401: {'description': ''}, 
            409: {'description': 'the name is already exist'}
        }
)
async def creating_item(item: CreatingItem, user: dict[str, Any] = Depends(authorization), ses: AsyncSession = Depends(db_helper)):
    try:
        new_item = await create_item(item=item, ses=ses, user_id=user['id'], user_email=user['sub'])
        mes: dict[str, int] = item.model_dump(mode='json')
        mes['email'] = user['sub']
        await broker.publish(message={'created': mes, 'id': new_item.id, 'user_id': user['id']}, queue=queue)
        await ses.commit()

        return new_item
    except IntegrityError:
        await ses.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='the name is already exist')


@app.patch(
        '/patch_item', 
        status_code=status.HTTP_200_OK, 
        response_model=CreatingItem, 
        responses={
            400: {'description': 'invalid information'},
            404: {'description': 'item doesnt exist'}
        }
)
async def patching_item(id: int, data: UpdateItem, user: dict[str, Any] = Depends(authorization), ses: AsyncSession = Depends(db_helper)):
    try:
        item = await patching(id=id, data=data, ses=ses, user_id=user['id'])

        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='item doesnt exist')
        await ses.commit()
        await ses.refresh(item)
        await broker.publish(message={'patched': data, 'item_id': id}, queue=queue)

        return item
    except IntegrityError:
        await ses.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='invalid info')


@app.post(
        '/create_user', 
        status_code=status.HTTP_201_CREATED, 
        response_model=CreatingUser, 
        responses={
            401: {'description': ''}, 
            409: {'description': 'email is existing'}
        }
)
async def creating_user(user: CreatingUser, ses: AsyncSession = Depends(db_helper)): 
    try:
        user.password = hash_pass(user.password).decode('utf-8')
        created_user = await create_user(user=user, ses=ses)
        await ses.commit()

        return created_user
    except IntegrityError:
        await ses.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='email or username is existing')
    

@app.post('/logout', status_code=status.HTTP_204_NO_CONTENT, responses={500: {'description': ''}})
async def logout(response: Response, token: str = Cookie(alias=COOKIE_SESSION_ID_KEY)):
    try:
        response.delete_cookie(key=COOKIE_SESSION_ID_KEY)
        return 
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)



# entry point
if __name__ == '__main__':
    uvicorn.run('main:app', host='0.0.0.0')




