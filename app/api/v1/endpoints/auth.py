from datetime import datetime, timedelta

import jwt
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.config import settings
from db.session import get_db
from crud.user import create, get_user_by_tg_id
from schemas.auth import TelegramAuth, TokenWithUser, UserInfo

router = APIRouter()


@router.post(
    "/auth/tg",
    response_model=TokenWithUser,
    summary="Auth by Telegram ID",
)
def auth_tg(
    payload: TelegramAuth, db: Session = Depends(get_db)
) -> TokenWithUser:
    """
    Создаёт (или находит) пользователя по `tg_id`
    и возвращает access‑token вместе с информацией о нём.
    """
    user = get_user_by_tg_id(db, payload.tg_id) or create(db, payload.tg_id)

    to_encode = {
        "sub": str(user.tg_id),
        "exp": datetime.utcnow()
        + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    token = jwt.encode(to_encode, settings.SECRET_KEY, settings.ALGORITHM)

    return TokenWithUser(
        access_token=token,
        user=UserInfo(
            tg_id=user.tg_id,
            pdn_agreed=user.pdn_agreed,
            offer_agreed=user.offer_agreed,
        ),
    )
