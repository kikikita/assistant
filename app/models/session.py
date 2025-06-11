from sqlalchemy import (
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


class Session(Base):
    """
    Активная сессия пользователя.

    Attributes:
        id: Уникальный идентификатор сессии.
        user_id: Идентификатор пользователя.
        resume_id: Идентификатор резюме.
        state: Состояние сессии (например, "EMPTY_FLOW").
        current_field: Текущее поле, на котором находится пользователь.
        loop_data: Временный буфер для хранения данных.
        created_at: Дата и время создания сессии.
        updated_at: Дата и время последнего обновления сессии.
        resume: Связь с моделью резюме.
        user: Связь с моделью пользователя.
    """
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resume_id = Column(
        Integer,
        ForeignKey("resumes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    state = Column(String, default="EMPTY_FLOW", nullable=False)
    current_field = Column(String, nullable=True)

    loop_data = Column(
        MutableDict.as_mutable(JSONB),
        nullable=True,
        default=dict,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Время создания записи"
    )
    updated_at = Column(
        DateTime(timezone=True),
        onupdate=func.now(),
        doc="Время последнего обновления"
    )

    # --- relations -------------------------------------------------
    resume = relationship("Resume", back_populates="sessions")
    user = relationship("User", back_populates="sessions")
