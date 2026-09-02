import aiosmtplib 
import asyncio
import time
from email.message import EmailMessage
from faststream.rabbit import RabbitBroker, RabbitQueue
from faststream import FastStream
from sqlalchemy import select, delete
from pydantic import BaseModel, EmailStr

if __package__:
    from .database.engine import ses_control
    from .database.tables import SendedMesagges
    from .config import sendler_settings, rabbit_settings
    from .log_conf import logger
else:
    from database.engine import ses_control
    from database.tables import SendedMesagges
    from config import sendler_settings, rabbit_settings
    from log_conf import logger

#send email-message to user email 


log = logger(40)

pss = sendler_settings.sendler_pass

Email = sendler_settings.sendler_email


broker = RabbitBroker(url=rabbit_settings.rabbitmq_url)
app = FastStream(broker)

queue_mail = RabbitQueue('mail_queue', durable=True)

class SendlerResponse(BaseModel):
    status: str
    email: EmailStr
    shop: str
    name: str
    price: float

@broker.subscriber(queue_mail)
async def send_message(msg: SendlerResponse):
    """listening to checker and send message to users"""

    
    if msg.status == 'fell':
        cur_time = time.time()
        async with ses_control() as ses:
            query = select(SendedMesagges).filter_by(email=msg.email, name=msg.name).limit(1)
            res = await ses.execute(query)
            message = res.scalar_one_or_none()
            if not message or message.status <= cur_time:
                log.info('sending')
                letter = EmailMessage()
                letter.set_content(f'in {msg.shop} price:{msg.price} of {msg.name}')
                letter['Subject'] = 'price was fell'
                letter['From'] = Email
                letter['To'] = msg.email
                try:
                    async with aiosmtplib.SMTP(hostname='smtp.gmail.com', port=587, start_tls=True) as smtp_server:
                        await smtp_server.login(Email, pss)
                        await smtp_server.send_message(letter)
                except Exception as e:
                    log.error(e)
                if message:
                    message.status = cur_time + 900
                else:
                    new_message = SendedMesagges(email=msg.email, name=msg.name, status=cur_time+900)
                    ses.add(new_message)
                await ses.commit()


        return msg



if __name__ == "__main__":
    import asyncio
    asyncio.run(app.run())




