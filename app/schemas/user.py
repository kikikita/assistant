from pydantic import BaseModel


class ConsentIn(BaseModel):
    tg_id: int
    agree: bool
