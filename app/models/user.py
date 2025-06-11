from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    DateTime,
    String,
    Date,
    Boolean,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from db.base import Base


class User(Base):
    """
    Модель пользователя.

    Attributes:
        id: Уникальный идентификатор пользователя.
        tg_id: Идентификатор Telegram.
        created_at: Дата и время создания профиля.
        full_name: Полное имя пользователя.
        birthday: Дата рождения.
        citizenship: Гражданство.
        phone: Номер телефона.
        work_status: Статус поиска работы (True = в активном поиске вакансий).
        pdn_agreed: Согласие на обработку персональных данных.
        offer_agreed: Согласие на оферту соискателя.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    tg_id = Column(
        BigInteger,
        unique=True,
        nullable=False,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # --- персональные данные ---
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    # статус поиска (True = в активном поиске вакансий)
    work_status = Column(Boolean, nullable=True)
    birthday = Column(Date, nullable=True)
    hideBirthday = Column(Boolean, nullable=True)
    phone = Column(String, nullable=True)

    # юридические согласия
    pdn_agreed = Column(Boolean, default=False)     # персональные данные
    offer_agreed = Column(Boolean, default=False)   # оферта соискателя
    # ───── relationships ────────────────────────────────────────────
    sessions = relationship(
        "Session",
        back_populates="user",
        cascade="all, delete-orphan",
    )
