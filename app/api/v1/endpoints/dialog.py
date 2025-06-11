from typing import Any, Union

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from crud.dialog import (
    continue_resume_flow,
    get_cv,
    get_or_create_session,
    next_question,
    reset_resume_flow,
    save_answer,
)
from crud.user import get_user_by_tg_id
from db.session import get_db
from models.question_template import QuestionTemplate
from schemas.dialog import (
    AnswerIn,
    CVOut,
    PartialCVOut,
    QuestionOut,
)

router = APIRouter()


def _build_qo(
    session_id: int,
    q: Union[QuestionTemplate, dict[str, Any]],
) -> QuestionOut:
    """
    Формирует QuestionOut из ORM-объекта или dict.
    """
    if isinstance(q, dict):
        return QuestionOut(
            session_id=session_id,
            field_name=q["field_name"],
            template=q["template"],
            inline_kb=q["inline_kb"],
            buttons=q.get("buttons", []),
            multi_select=q["multi_select"],
        )
    return QuestionOut(
        session_id=session_id,
        field_name=q.field_name,
        template=q.template,
        inline_kb=q.inline_kb,
        buttons=q.buttons or [],
        multi_select=q.multi_select,
    )


@router.post(
    "/dialog/next",
    response_model=QuestionOut | CVOut | PartialCVOut,
)
def dialog_next(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
):
    """
    Выбирает этап диалога: новый вопрос,
    предпросмотр или готовое резюме.
    """
    user = get_user_by_tg_id(db, payload["user_id"])
    if not user:
        raise HTTPException(404, "User not found")

    cv = get_cv(db, user.id)

    if cv["status"] == "completed":
        return CVOut(
            cv_markdown=cv["cv_markdown"],
            fields=cv["fields"],
        )
    if cv["status"] == "incomplete":
        return PartialCVOut(
            cv_markdown=cv["cv_markdown"],
            resume_id=cv["resume_id"],
        )

    sess = get_or_create_session(db, user.id)
    q = next_question(db, sess)
    if q is None:
        return CVOut(
            cv_markdown="Все поля уже заполнены.",
            fields={},
        )
    return _build_qo(sess.id, q)


@router.post(
    "/dialog/answer",
    response_model=QuestionOut | CVOut,
)
def dialog_answer(
    data: AnswerIn,
    db: Session = Depends(get_db),
):
    """
    Сохраняет ответ, возвращает следующий вопрос
    или готовое резюме.
    """
    user = get_user_by_tg_id(db, data.user_id)
    if not user:
        raise HTTPException(404, "User not found")

    if data.session_id is None:
        sess = get_or_create_session(db, user.id)
        session_id = sess.id
    else:
        session_id = data.session_id

    next_q = save_answer(
        db=db,
        session_id=session_id,
        user_id=user.id,
        field_name=data.field_name,
        answer_raw=data.answer_raw,
    )
    if next_q is None:
        cv = get_cv(db, user.id)
        return CVOut(
            cv_markdown=cv["cv_markdown"],
            fields=cv["fields"],
        )
    return _build_qo(session_id, next_q)


@router.post(
    "/dialog/reset",
    response_model=QuestionOut | CVOut,
)
def dialog_reset(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
):
    """
    Архивирует старое резюме и начинает новый диалог.
    """
    user = get_user_by_tg_id(db, payload["user_id"])
    if not user:
        raise HTTPException(404, "User not found")

    result = reset_resume_flow(db, user)
    if "cv_markdown" in result:
        return CVOut(
            cv_markdown=result["cv_markdown"],
            fields={},
        )
    return _build_qo(result["session_id"], result)


@router.post(
    "/dialog/resume-continue",
    response_model=QuestionOut,
)
def resume_continue(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
):
    """
    Возобновляет диалог по resume_id,
    возвращает следующий вопрос.
    """
    user = get_user_by_tg_id(db, payload["user_id"])
    if not user:
        raise HTTPException(404, "User not found")

    q = continue_resume_flow(
        db,
        resume_id=payload["resume_id"],
        user_id=user.id,
    )
    return _build_qo(q["session_id"], q)
