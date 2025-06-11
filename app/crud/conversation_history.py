import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from models.answer import Answer
from models.session import Session as DSession
from crud.user import get_user_by_tg_id

logger = logging.getLogger(__name__)


def save_conversation_message(
    db: Session,
    session_id: int,
    role: str,
    message: str,
) -> Answer:
    """
    Сохраняет сообщение в историю разговора.
    
    Args:
        db: Сессия базы данных
        session_id: ID сессии
        role: Роль отправителя ('human', 'bot', 'tool_call')
        message: Текст сообщения
        
    Returns:
        Созданная запись Answer
    """
    answer = Answer(
        session_id=session_id,
        role=role,
        answer_raw=message,
    )
    db.add(answer)
    db.flush()
    return answer


def get_conversation_history(
    db: Session,
    session_id: int,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Получает историю разговора для сессии.
    
    Args:
        db: Сессия базы данных
        session_id: ID сессии
        limit: Максимальное количество сообщений
        
    Returns:
        Список сообщений в формате [{"role": str, "content": str, "timestamp": datetime}, ...]
    """
    answers = (
        db.query(Answer)
        .filter(Answer.session_id == session_id)
        .order_by(Answer.created_at.desc())
        .limit(limit)
        .all()
    )
    
    return [
        {
            "role": answer.role,
            "content": answer.answer_raw,
            "timestamp": answer.created_at,
        }
        for answer in reversed(answers)
    ]


def get_user_session_for_conversation(
    db: Session,
    user_id: int
) -> DSession:
    """
    Получает или создает активную сессию для пользователя для ведения разговора.
    """
    from crud.dialog import get_or_create_session
    return get_or_create_session(db, user_id)


def save_user_message(
    db: Session,
    tg_user_id: int,
    message: str
) -> DSession:
    """
    Сохраняет сообщение пользователя в историю разговора.
    Получает или создает сессию для пользователя.
    
    Returns:
        Сессия пользователя
    """
    user = get_user_by_tg_id(db, tg_user_id)
    if not user:
        raise ValueError(f"User with tg_id {tg_user_id} not found")
    
    session = get_user_session_for_conversation(db, user.id)
    
    save_conversation_message(
        db=db,
        session_id=session.id,
        role="human",
        message=message
    )
    
    db.commit()
    return session


def save_bot_message(
    db: Session,
    session_id: int,
    message: str
) -> Answer:
    """
    Сохраняет ответ бота в историю разговора.
    """
    answer = save_conversation_message(
        db=db,
        session_id=session_id,
        role="bot",
        message=message
    )
    db.commit()
    return answer 