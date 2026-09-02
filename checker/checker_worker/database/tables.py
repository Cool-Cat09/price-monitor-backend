from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String

from .engine import Base


#database models


class Item_Checker(Base):
    __tablename__ = 'items'

    art: Mapped[str]
    name: Mapped[str]  
    need_price: Mapped[int]
    shop: Mapped[str]
    email: Mapped[str] = mapped_column(String)

    id: Mapped[int] = mapped_column(primary_key=True)
