from pydantic import BaseModel

class UpdateItem(BaseModel):
    art: str | None = None
    name: str | None = None
    need_price: int | None = None
    shop: str | None = None