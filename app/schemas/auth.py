from pydantic import BaseModel, Field


class TelegramAuth(BaseModel):
    """Запрос на авторизацию по Telegram-ID."""
    tg_id: int = Field(..., ge=1, description="ID пользователя Telegram")


class Token(BaseModel):
    """Базовый access-token (остался для обратной совместимости)."""
    access_token: str
    token_type: str = "bearer"


class UserInfo(BaseModel):
    """Минимальный набор полей, нужный боту для проверки согласий."""
    tg_id: int
    pdn_agreed: bool
    offer_agreed: bool


class TokenWithUser(Token):
    """
    Access-token + информация о пользователе.
    """
    user: UserInfo
