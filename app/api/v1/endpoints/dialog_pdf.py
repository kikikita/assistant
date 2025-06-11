import json
import os
import uuid
import logging
from typing import Any, Dict, List, Optional

import fitz  # PyMuPDF
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from core.config import settings
from crud.dialog import get_cv, next_question
from crud.user import get_user_by_tg_id
from db.session import get_db
from models.resume import Resume
from models.session import Session as DSession
from resume.dynamic_resume_model_manager import dynamic_resume_model_manager
from schemas.dialog import CVOut, QuestionOut


logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    fmt = (
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )
    handler.setFormatter(logging.Formatter(fmt))
    logger.addHandler(handler)

ALLOWED_CONTENT_TYPE = "application/pdf"
TEMP_UPLOAD_DIR = settings.TEMP_UPLOAD_DIR
os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)

router = APIRouter()


def extract_text_from_pdf(path: str) -> str:
    """
    Извлекает текст из PDF-файла по указанному пути.
    """
    try:
        doc = fitz.open(path)
        text = "\n".join(
            doc.load_page(i).get_text() for i in range(len(doc))
        )
        return text
    except Exception as exc:
        logger.error(
            "Ошибка извлечения текста из PDF: %s", exc, exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при обработке PDF: {exc}"
        ) from exc
    finally:
        if 'doc' in locals():
            doc.close()


async def extract_resume_data_with_llm(txt: str) -> BaseModel:
    """
    Извлекает данные резюме из текста с помощью LLM.
    """
    if not dynamic_resume_model_manager.initialized:
        await dynamic_resume_model_manager.initialize_model()
    if (not dynamic_resume_model_manager.initialized
            or dynamic_resume_model_manager.model is None):
        raise HTTPException(
            status_code=503,
            detail="Модель резюме не инициализирована"
        )
    if not dynamic_resume_model_manager.resume_fields:
        logger.critical("Поля схемы пусты – LLM вызов отменён.")
        raise HTTPException(
            status_code=503,
            detail="Сервис временно недоступен, попробуйте позже."
        )

    prompt = (
        "Верни JSON по схеме; опускай пустые поля.\n\n"
        "Текст резюме:\n" + txt[:4000]
    )
    logger.debug(
        "LLM prompt: %s",
        prompt[:300].replace("\n", " ⏎ ")
    )
    try:
        result = await dynamic_resume_model_manager.llm.ainvoke(prompt)
        logger.debug("LLM raw result: %s", result)
        return result
    except Exception as exc:
        logger.error("Ошибка LLM: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=f"Сбой LLM API: {exc}"
        ) from exc


def merge_parsed_into_resume(
    resume: Resume,
    parsed: Dict[str, Any]
) -> bool:
    """
    Сливает распарсенные данные в объект Resume.
    Возвращает True, если данные изменились.
    """
    data = resume.data
    changed = False
    logger.debug(
        "Данные до мерджа: %s",
        json.dumps(data, ensure_ascii=False)
    )

    for key, value in parsed.items():
        if not value:
            continue
        if isinstance(value, list):
            old = data.get(key, [])
            data[key] = old + value
            changed = True
        else:
            if not data.get(key):
                data[key] = value
                changed = True

    if changed:
        flag_modified(resume, "data")
        logger.debug("Слияние данных по ключам: %s", list(parsed.keys()))

    logger.debug(
        "Данные после мерджа: %s",
        json.dumps(data, ensure_ascii=False)
    )
    return changed


def collect_missing_fields(resume: Resume) -> List[str]:
    """
    Составляет список отсутствующих полей резюме.
    """
    field_names = {
        f["name"] for f in dynamic_resume_model_manager.resume_fields
    }
    data = resume.data
    missing: List[str] = [
        name for name in field_names
        if not data.get(name)
    ]
    if not data.get("work_experience_ok"):
        missing.append("work_experience")
    logger.debug("Отсутствующие поля: %s", missing)
    return missing


@router.post(
    "/pdf",
    response_model=QuestionOut | CVOut
)
async def process_pdf_resume(
    file: UploadFile = File(...),
    tg_id: str = Form(...),
    db: Session = Depends(get_db)
) -> QuestionOut | CVOut:
    """
    Обрабатывает загруженный PDF с резюме и возвращает
    следующий вопрос или готовое резюме.
    """
    user = get_user_by_tg_id(db, tg_id)
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    if file.content_type != ALLOWED_CONTENT_TYPE:
        raise HTTPException(400, "Поддерживается только PDF")

    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Файл пуст")
    if len(raw) > settings.MAX_FILE_SIZE:
        raise HTTPException(413, "Слишком большой файл")

    tmp_path: Optional[str] = None
    try:
        tmp_path = os.path.join(
            TEMP_UPLOAD_DIR,
            f"{uuid.uuid4()}.pdf"
        )
        with open(tmp_path, "wb") as buf:
            buf.write(raw)

        text = extract_text_from_pdf(tmp_path)
        logger.debug("Длина текста: %d", len(text))

        llm_obj = await extract_resume_data_with_llm(text)
        parsed = llm_obj.model_dump()
        logger.debug("Ключи распарсенного: %s", list(parsed.keys()))

        resume = (
            db.query(Resume)
            .filter_by(
                user_id=user.id,
                is_archived=False,
                status="incomplete"
            )
            .first()
        )
        if not resume:
            resume = Resume(
                user_id=user.id,
                status="incomplete",
                data={}
            )
            db.add(resume)
            logger.debug("Создано новое резюме")

        merge_parsed_into_resume(resume, parsed)
        if not resume.data.get("resume_pdf"):
            resume.data["resume_pdf"] = "Загружен PDF"
            flag_modified(resume, "data")
        db.commit()
        db.refresh(resume)

        missing = collect_missing_fields(resume)
        if not missing:
            resume.status = "completed"
            db.commit()
            cv = get_cv(db, user.id)
            return CVOut(
                cv_markdown=cv["cv_markdown"],
                fields=cv["fields"]
            )

        sess = (
            db.query(DSession)
            .filter_by(
                resume_id=resume.id,
                user_id=user.id
            )
            .first()
        )
        if not sess:
            sess = DSession(
                user_id=user.id,
                resume_id=resume.id
            )
            db.add(sess)
            db.commit()
            db.refresh(sess)

        question = next_question(db, sess)
        if not question:
            resume.status = "completed"
            db.commit()
            cv = get_cv(db, user.id)
            return CVOut(
                cv_markdown=cv["cv_markdown"],
                fields=cv["fields"]
            )

        return QuestionOut(
            session_id=sess.id,
            field_name=question.field_name,
            template=question.template,
            inline_kb=question.inline_kb,
            buttons=question.buttons or [],
            multi_select=question.multi_select,
        )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError as exc:
                logger.error(
                    "Не удалось удалить временный файл %s: %s",
                    tmp_path,
                    exc,
                    exc_info=True
                )
