from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from sqlalchemy import text
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from typing import List, Dict

from core.config import settings
from db.session import get_db
from models.question_template import QuestionTemplate

router = APIRouter()


def _read_sheet() -> List[Dict[str, str]]:
    """Читает Google Sheets и возвращает список словарей по строкам."""
    creds = Credentials.from_service_account_file(
        settings.GSHEETS_CREDS_PATH,
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    service = build("sheets", "v4", credentials=creds)
    sheet = service.spreadsheets().values().get(
        spreadsheetId=settings.GSHEETS_SHEET_ID,
        range=settings.GSHEETS_FIRST_TAB,
    ).execute()

    values = sheet.get("values", [])
    if not values:
        raise RuntimeError("Пустой лист")

    header = values[0]
    rows = [dict(zip(header, r)) for r in values[1:] if any(r)]
    return rows


@router.post("/update-questions")
def update_questions(
    token: str = Body(..., embed=True),
    db: Session = Depends(get_db),
):
    """Полностью пересоздаёт таблицу question_templates из Google Sheets."""
    if token != settings.ADMIN_SYNC_TOKEN:
        raise HTTPException(403, detail="Forbidden")

    try:
        rows = _read_sheet()
    except Exception as exc:
        raise HTTPException(500, detail=f"Sheet read error: {exc}") from exc

    db.execute(
        text("TRUNCATE TABLE question_templates CASCADE")
    )
    objs = [QuestionTemplate.from_sheet_row(r) for r in rows]
    db.bulk_save_objects(objs)
    db.commit()
    return {"status": "ok", "inserted": len(objs)}
