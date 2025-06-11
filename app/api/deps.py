import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from core.config import settings
from db.session import get_db
from crud.user import get_user_by_tg_id

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/tg")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        tg_id: int = int(payload.get("sub"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    user = get_user_by_tg_id(db, tg_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
