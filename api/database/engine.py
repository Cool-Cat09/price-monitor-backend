from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from contextlib import asynccontextmanager
try:
    from ..config import database_settings
except ImportError:
    from config import database_settings





URL = database_settings.database_url

class Base(DeclarativeBase):

    id: Mapped[int] = mapped_column(primary_key=True)

engine = create_async_engine(URL, echo=True)
Session = async_sessionmaker(bind=engine, expire_on_commit=False)










