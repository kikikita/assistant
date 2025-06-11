from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from db.base import Base


class Resume(Base):
    """
    Резюме пользователя.

    Attributes:
        id: Уникальный идентификатор резюме.
        user_id: Ссылка на пользователя.
        data: Данные резюме (JSONB).
        status: Статус заполнения резюме.
        is_archived: Флаг архивного состояния.
        created_at: Время создания записи.
        updated_at: Время последнего обновления.
        sessions: Сессии, связанные с резюме.
    """
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    data = Column(
        MutableDict.as_mutable(JSONB),
        nullable=False,
        default=lambda: {
            "first_name": None,
            "last_name": None,
            "work_status": None,
            "birthday": None,
            "phone": None,
            "work_experience": [],
        },
    )
    insights = Column(
        JSONB,
        nullable=False,
        server_default="[]",
        comment="Скрытые факты / инсайты агента",
    )

    status = Column(String, default="incomplete", nullable=False)
    is_archived = Column(Boolean, default=False, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        default=func.now(),
        comment="Время создания записи",
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=func.now(),
        onupdate=func.now(),
        comment="Время последнего обновления",
    )

    # --- relations -------------------------------------------------
    sessions = relationship(
        "Session",
        back_populates="resume",
        cascade="all, delete-orphan",
    )
