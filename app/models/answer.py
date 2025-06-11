from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from db.base import Base


class Answer(Base):
    """
    Модель записи в истории диалога.

    Attributes:
        id: Уникальный идентификатор записи.
        session_id: Сессия, к которой относится запись.
        role: Роль отправителя (human/bot).
        answer_raw: Текст сообщения.
        created_at: Дата и время создания записи.
    """
    __tablename__ = "answers"

    id = Column(Integer, primary_key=True)
    session_id = Column(
        Integer,
        ForeignKey(
            "sessions.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )
    role = Column(
        String,
        nullable=False
    )
    answer_raw = Column(
        String,
        nullable=False
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
