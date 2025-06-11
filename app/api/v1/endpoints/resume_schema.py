from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from db.session import get_db
from services.schema_builder import build_resume_schema

router = APIRouter()


@router.get("/resume/schema", summary="Получить JSON-Schema резюме")
def get_resume_schema(db: Session = Depends(get_db)) -> dict:
    """
    Возвращает актуальную JSON-схему резюме.
    """
    return build_resume_schema(db)
