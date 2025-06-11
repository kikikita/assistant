from typing import Any, List
from sqlalchemy.orm import Session
from crud.resume import (
    get_or_create_active_resume,
    update_resume_field,
    append_resume_insight,
)
from crud.user import get_user_by_tg_id
from crud.dialog import continue_resume_flow
from db.session import SessionLocal
from services.schema_builder import build_resume_schema


async def get_resume_scheme():
    """Получает схему резюме из API."""
    db: Session = SessionLocal()
    try:
        schema = build_resume_schema(db=db)
        return schema
    finally:
        db.close()


async def get_user_resume(user_id: str):
    """Получает текущее резюме пользователя из API."""
    db: Session = SessionLocal()
    try:
        current_user = get_user_by_tg_id(db=db, tg_id=int(user_id))
        if not current_user:
            return None
        resume = get_or_create_active_resume(db=db, user_id=current_user.id)
        # Remove None fields from resume data
        filtered_data = {k: v for k, v in resume.data.items() if v is not None}
        return filtered_data
    finally:
        db.close()


async def update_user_resume(session: Session, user_id: str, field_name: str, value: Any):
    """Обновляет поле резюме пользователя в API."""
    current_user = get_user_by_tg_id(db=session, tg_id=int(user_id))
    if not current_user:
        return None
    resume = get_or_create_active_resume(db=session, user_id=current_user.id)
    updated_resume = update_resume_field(
        db=session,
        resume=resume,
        field_name=field_name,
        value=value
    )
    return updated_resume.data


async def append_user_insight(
    session: Session,
    user_id: str,
    description: str,
    insight: str,
) -> List[str] | None:
    """
    Добавляет скрытый инсайт к резюме пользователя.

    Возвращает обновлённый список инсайтов.
    """
    user = get_user_by_tg_id(db=session, tg_id=int(user_id))
    if not user:
        return None
    resume = get_or_create_active_resume(db=session, user_id=user.id)
    updated_resume = append_resume_insight(
        db=session,
        resume=resume,
        description=description,
        insight=insight,
    )
    return updated_resume.insights


async def get_next_question(resume_id: int, user_id: int):
    """Получает следующий вопрос для резюме из API."""
    db: Session = SessionLocal()
    try:
        result = continue_resume_flow(
            db=db,
            resume_id=resume_id,
            user_id=user_id
        )
        return result
    finally:
        db.close()
