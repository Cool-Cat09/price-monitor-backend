from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String
from .engine import Base
from pydantic import EmailStr


#database models

class SendedMesagges(Base):
    __tablename__ = 'sendedMessages'

    email: Mapped[EmailStr] = mapped_column(String)
    name: Mapped[str] = mapped_column(unique=True)
    status: Mapped[float]
