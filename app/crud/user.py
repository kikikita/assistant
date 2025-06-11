from sqlalchemy.orm import Session

from models.user import User


def get_user_by_tg_id(db: Session, tg_id: int) -> User | None:
    """
    Возвращает пользователя по Telegram ID, если он существует.
    """
    return db.query(User).filter(User.tg_id == tg_id).first()


def create(db: Session, tg_id: int) -> User:
    """
    Создаёт нового пользователя по Telegram ID.
    """
    user = User(tg_id=tg_id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def set_consent(
    db: Session,
    user: User,
    pdn_agreed: bool,
    offer_agreed: bool,
) -> None:
    """
    Фиксирует юридическое согласие пользователя.
    """
    user.pdn_agreed = pdn_agreed
    user.offer_agreed = offer_agreed
    db.commit()
