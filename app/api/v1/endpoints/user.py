from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.session import get_db
from crud.user import get_user_by_tg_id, set_consent

from schemas.user import (
    ConsentIn,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/consent", status_code=204)
def user_consent(payload: ConsentIn, db: Session = Depends(get_db)) -> None:
    """
    Принимает/отклоняет оферту и согласие на обработку ПДн.
    """
    user = get_user_by_tg_id(db, payload.tg_id)
    if not user:
        raise HTTPException(404, "User not found")

    if not payload.agree:
        set_consent(db, user, False, False)
        return

    set_consent(db, user, True, True)
