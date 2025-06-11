import logging
from datetime import date
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from models.answer import Answer
from models.question_template import QuestionTemplate
from models.resume import Resume
from models.session import Session as DSession
from models.user import User

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    fmt = (
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )
    handler.setFormatter(logging.Formatter(fmt))
    logger.addHandler(handler)
    
REQUIRED_FIELDS: Dict[str, set] = {
    "work_experience": {"exp_company", "exp_position"},
}


def session_has_answers(db: Session, session_id: int) -> bool:
    """
    Проверяет, есть ли в сессии ответы пользователя.
    """
    count = (
        db.query(Answer)
        .filter(
            Answer.session_id == session_id,
            Answer.role == "human",
        )
        .limit(1)
        .count()
    )
    return count > 0


def _group_is_complete(data: Dict[str, Any], gid: str) -> bool:
    """
    Проверяет, заполнены ли обязательные поля группы gid.
    """
    items = data.get(gid, [])
    if not items:
        return False
    required = REQUIRED_FIELDS.get(gid, set())
    return all(
        all(item.get(field) for field in required)
        for item in items
    )


def get_active_session(db: Session, user_id: int) -> Optional[DSession]:
    """
    Возвращает активную сессию пользователя или None.
    """
    return (
        db.query(DSession)
        .join(Resume, DSession.resume_id == Resume.id)
        .filter(
            DSession.user_id == user_id,
            Resume.is_archived.is_(False),
            Resume.status == "incomplete",
        )
        .first()
    )


def _first_group_question(db: Session, gid: str) -> QuestionTemplate:
    """
    Возвращает первый вопрос группы без суффикса _intro.
    """
    return (
        db.query(QuestionTemplate)
        .filter(
            QuestionTemplate.group_id == gid,
            QuestionTemplate.is_last.is_(False),
            ~QuestionTemplate.field_name.like("%_intro"),
        )
        .order_by(QuestionTemplate.priority)
        .first()
    )


def _next_group_question(
    db: Session, gid: str, priority: int
) -> Optional[QuestionTemplate]:
    """Возвращает следующий по приоритету вопрос группы."""
    return (
        db.query(QuestionTemplate)
        .filter(
            QuestionTemplate.group_id == gid,
            QuestionTemplate.priority > priority,
        )
        .order_by(QuestionTemplate.priority)
        .first()
    )


def _intro_question(db: Session, gid: str) -> QuestionTemplate:
    """Возвращает вводный вопрос группы gid."""
    return (
        db.query(QuestionTemplate)
        .filter(
            QuestionTemplate.group_id == gid,
            QuestionTemplate.field_name.like("%_intro"),
        )
        .first()
    )


def _work_item_summary(item: dict, idx: int, labels: dict) -> str:
    """
    Формирует красивое текстовое описание одной записи об опыте работы,
    только для реально заполненных полей.
    """
    label_map = {
        "position": "Должность",
        "company_name": "Компания",
        "from_to": "Период работы",
        "about_work": "Коротко о работе",
        "responsibilities": "Задачи",
        "achievements": "Достижения",
        "client_segments": "Сегмент клиентов",
        "customer_sales_volumes": "Размер клиентов",
        "sales_formats": "Формат продаж",
        "deals_per_month": "Сделок в месяц",
        "average_check": "Средний чек",
        "crm": "CRM",
        "clients": "С кем работал",
    }
    label_map = {**label_map, **labels}

    # Выбираем только непустые поля
    filled = [
        (label_map.get(key, key), value)
        for key, value in item.items()
        if value and str(value).strip() and key in label_map
    ]
    if not filled:
        return ""

    lines = [f"{idx}. "]
    for label, value in filled:
        lines.append(f"   • <b>{label}</b>: {value}")
    return "\n".join(lines)


def _work_summary(items: list, labels: dict) -> str:
    """
    Объединяет только заполненные записи об опыте работы в красивый текст.
    """
    summaries = [
        _work_item_summary(item, idx, labels)
        for idx, item in enumerate(items, 1)
    ]
    summaries = [s for s in summaries if s]
    return "\n".join(summaries) if summaries else "—"


def _build_intro_reply(
    base: QuestionTemplate,
    work: List[Dict[str, str]],
    add_error: Optional[str] = None,
) -> SimpleNamespace:
    """
    Создает объект ответа для вводного вопроса опыта работы.
    """
    summary = _work_summary(work)
    text = base.template
    if summary:
        text += f"\n\n<b>Вы ответили:</b>\n{summary}"
    if add_error:
        text += add_error

    buttons = ["+ Добавить опыт работы"]
    if work:
        buttons = ["Ответить заново", *buttons, "Подтвердить"]

    return SimpleNamespace(
        field_name=base.field_name,
        template=text,
        inline_kb=True,
        buttons=buttons,
        multi_select=False,
    )


def _store_user_field(user: User, name: str, value: str) -> None:
    """Сохраняет базовые поля пользователя в модели User."""
    if name == "first_name":
        user.first_name = value
    elif name == "last_name":
        user.last_name = value
    elif name == "work_status":
        user.work_status = value.lower() == "true"
    elif name == "birthday":
        try:
            user.birthday = date.fromisoformat(value)
        except ValueError:
            logger.debug("Некорректная дата рождения: %s", value)
    elif name == "hideBirthday":
        user.hideBirthday = value.lower() == "false"
    elif name == "phone":
        user.phone = value
    else:
        return


def get_or_create_session(db: Session, user_id: int) -> DSession:
    """
    Возвращает существующую сессию или создает новую резюме и сессию.
    """
    session = get_active_session(db, user_id)
    if session:
        logger.debug("Reuse session %s for user %s", session.id, user_id)
        return session

    resume = Resume(user_id=user_id)
    db.add(resume)
    db.commit()
    db.refresh(resume)

    session = DSession(user_id=user_id, resume_id=resume.id)
    db.add(session)
    db.commit()
    db.refresh(session)
    logger.debug(
        "Created resume %s and session %s", resume.id, session.id
    )
    return session


def get_question_by_field_name(
    db: Session, field_name,
):
    tmpl = db.get(QuestionTemplate, field_name)
    return tmpl


def next_question(
    db: Session, sess: DSession
) -> Optional[QuestionTemplate]:
    """
    Определяет следующий вопрос по данным сессии.
    """
    data = sess.resume.data
    updated = False
    for gid in REQUIRED_FIELDS:
        if _group_is_complete(data, gid) and not data.get(f"{gid}_ok"):
            data[f"{gid}_ok"] = True
            updated = True
    if updated:
        flag_modified(sess.resume, "data")
        db.flush()

    if sess.loop_data:
        gid = sess.loop_data["group"]
        curr = db.get(QuestionTemplate, sess.current_field)
        nxt = _next_group_question(db, gid, curr.priority)
        if nxt:
            sess.current_field = nxt.field_name
            db.flush()
        return nxt

    filled = {
        k for k, v in data.items() if v not in (None, "", [], {})
    }
    for q in db.query(QuestionTemplate).order_by(
        QuestionTemplate.priority
    ):
        if q.group_id and data.get(f"{q.group_id}_ok"):
            continue
        if q.group_id and q.field_name.endswith("_intro"):
            sess.current_field = q.field_name
            db.flush()
            return q
        if q.field_name in filled:
            continue
        sess.current_field = q.field_name
        db.flush()
        return q

    sess.state = "CONFIRM"
    db.flush()
    return None


def save_answer(
    db: Session,
    session_id: int,
    user_id: int,
    field_name: str,
    answer_raw: str,
) -> Optional[QuestionTemplate]:
    """
    Сохраняет ответ, обновляет данные и возвращает следующий вопрос.
    Также сохраняет в историю разговора.
    """
    sess = db.get(DSession, session_id)
    resume = sess.resume
    user = db.get(User, user_id)
    tmpl = db.get(QuestionTemplate, field_name)

    logger.debug(
        "save_answer(sess=%s field=%s) answer=%r",
        session_id,
        field_name,
        answer_raw,
    )
    
    # Сохраняем в историю разговора
    db.add(
        Answer(
            session_id=session_id,
            role="human",
            answer_raw=answer_raw,
        )
    )
    db.flush()

    if tmpl.group_id is None:
        _store_user_field(user, field_name, answer_raw)
        resume.data[field_name] = answer_raw
        flag_modified(resume, "data")
        nxt = next_question(db, sess)
        if nxt is None:
            resume.status = "completed"
        db.commit()
        return nxt

    if field_name.endswith("_intro"):
        return _handle_intro(db, sess, tmpl, answer_raw)
    return _handle_group_flow(db, sess, tmpl, answer_raw)


def _handle_intro(
    db: Session,
    sess: DSession,
    tmpl: QuestionTemplate,
    answer: str,
) -> QuestionTemplate:
    """
    Обрабатывает ввод на этапе intro: создание/сброс/
    подтверждение записи в группе.
    """
    gid = tmpl.group_id
    data = sess.resume.data

    if answer.startswith("+"):
        sess.loop_data = {"group": gid, "item": {}}
        flag_modified(sess, "loop_data")
        first_q = _first_group_question(db, gid)
        sess.current_field = first_q.field_name
        db.commit()
        logger.debug("loop_data после '+': %s", sess.loop_data)
        return first_q

    if answer.startswith("Ответить"):
        data[gid] = []
        data.pop(f"{gid}_ok", None)
        flag_modified(sess.resume, "data")
        sess.loop_data = None
        db.commit()
        return next_question(db, sess)

    if answer == "Подтвердить":
        if not data.get(gid):
            return _build_intro_reply(
                _intro_question(db, gid),
                data.get(gid, []),
                add_error="\n\n⚠️ Сначала добавьте запись.",
            )
        data[f"{gid}_ok"] = True
        flag_modified(sess.resume, "data")
        nxt = next_question(db, sess)
        if nxt is None:
            sess.resume.status = "completed"
        db.commit()
        return nxt

    # некорректный ввод
    return _build_intro_reply(
        _intro_question(db, gid),
        data.get(gid, []),
        add_error="\n\n⚠️ Используйте кнопки ниже.",
    )


def _handle_group_flow(
    db: Session,
    sess: DSession,
    tmpl: QuestionTemplate,
    answer: str,
) -> QuestionTemplate:
    """
    Обрабатывает ввод внутри группы: сбор полей, валидацию
    и сохранение в данные резюме.
    """
    gid = tmpl.group_id
    loop = sess.loop_data or {"group": gid, "item": {}}
    item = dict(loop["item"])
    item[tmpl.field_name] = answer
    loop["item"] = item
    sess.loop_data = loop
    flag_modified(sess, "loop_data")
    db.commit()
    logger.debug("loop_data после commit: %s", sess.loop_data)

    if not tmpl.is_last:
        nxt = _next_group_question(db, gid, tmpl.priority)
        sess.current_field = nxt.field_name
        db.commit()
        return nxt

    # проверка обязательных полей
    miss = [
        f for f in REQUIRED_FIELDS.get(gid, set())
        if not item.get(f)
    ]
    if miss:
        intro = _intro_question(db, gid)
        intro.template += "\n⚠️ Заполните обязательные поля."
        sess.current_field = intro.field_name
        db.commit()
        return intro

    # сохраняем запись в resume.data
    work = sess.resume.data.get(gid, [])
    work.append(item)
    sess.resume.data[gid] = work
    flag_modified(sess.resume, "data")
    sess.loop_data = None
    db.commit()
    logger.debug("work_experience теперь %s записей", len(work))

    intro_base = _intro_question(db, gid)
    reply = _build_intro_reply(intro_base, work)
    sess.current_field = reply.field_name
    db.commit()
    return reply


def get_cv(db: Session, user_id: int) -> Dict[str, Any]:
    resume = (
        db.query(Resume)
        .filter_by(user_id=user_id, is_archived=False)
        .order_by(Resume.updated_at.desc())
        .first()
    )
    if not resume:
        return {
            "status": "not_started",
            "cv_markdown": "Резюме ещё не начинали заполнять.",
            "fields": {},
        }

    templates = list(db.query(QuestionTemplate).all())
    labels = {qt.field_name: qt.label for qt in templates}
    priorities = {qt.field_name: qt.priority for qt in templates}
    data = resume.data
    lines: list[str] = ["📄 <b>Ваше резюме</b>\n"]

    # Базовые поля (без work_experience)
    entries = []
    for key, val in data.items():
        if key.endswith("_ok") or isinstance(val, list):
            continue
        if not val or str(val).strip() == "":
            continue  # пропускаем пустые
        prio = priorities.get(key, float("inf"))
        entries.append((prio, key, val))

    for _, key, val in sorted(entries, key=lambda x: x[0]):
        lines.append(f"• <b>{labels.get(key, key)}</b>: «{val}»")

    # Опыт работы
    work_exp = data.get("work_experience", [])
    if work_exp:
        summary = _work_summary(work_exp, labels)
        if summary.strip() != "—":
            lines.append("\n• <b>Опыт работы:</b>")
            lines.append(summary)

    return {
        "status": resume.status,
        "cv_markdown": "\n".join(lines),
        "fields": data,
        "resume_id": resume.id,
    }


def reset_resume_flow(db: Session, user: User) -> Dict[str, Any]:
    """
    Архивирует предыдущий черновик и создаёт новый,
    возвращает первый вопрос или markdown CV.
    """
    prev = (
        db.query(Resume)
        .filter_by(user_id=user.id, is_archived=False)
        .first()
    )
    if prev:
        prev.is_archived = True
        db.commit()

    resume = Resume(
        user_id=user.id,
        data={
            "first_name": user.first_name,
            "last_name": user.last_name,
            "work_status": user.work_status,
            "birthday": str(user.birthday) if user.birthday else None,
            "hideBirthday": user.hideBirthday,
            "phone": user.phone,
        },
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)

    sess = DSession(user_id=user.id, resume_id=resume.id)
    db.add(sess)
    db.commit()
    db.refresh(sess)

    first = next_question(db, sess)
    if not first:
        return {"cv_markdown": "Все поля уже заполнены."}

    return {
        "session_id": sess.id,
        "field_name": first.field_name,
        "template": first.template,
        "inline_kb": first.inline_kb,
        "buttons": first.buttons or [],
        "multi_select": first.multi_select,
    }


def continue_resume_flow(
    db: Session,
    resume_id: int,
    user_id: int,
) -> Dict[str, Any]:
    """
    Возобновляет заполнение существующего резюме,
    возвращает следующий вопрос.
    """
    resume = (
        db.query(Resume)
        .filter_by(id=resume_id, user_id=user_id)
        .first()
    )
    if not resume:
        raise ValueError("Resume not found")

    sess = (
        db.query(DSession)
        .filter_by(resume_id=resume.id, user_id=user_id)
        .first()
    )
    if not sess:
        raise ValueError("Session not found")

    q = next_question(db, sess)
    if not q:
        raise ValueError("No next question")

    return {
        "session_id": sess.id,
        "field_name": q.field_name,
        "template": q.template,
        "inline_kb": q.inline_kb,
        "buttons": q.buttons or [],
        "multi_select": q.multi_select,
    }


def save_resume_data(
    db: Session,
    user_id: int,
    payload: Dict[str, Any],
) -> Resume:
    """
    Создаёт черновик резюме со статусом 'incomplete' и
    возвращает объект Resume.
    """
    resume = Resume(user_id=user_id, data=payload, status="incomplete")
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


def get_resume_parse_fields(db: Session) -> List[Dict[str, Any]]:
    """
    Возвращает список полей резюме для PDF-парсера
    (API-совместимость).
    """
    rows = (
        db.query(
            QuestionTemplate.field_name,
            QuestionTemplate.label,
            QuestionTemplate.group_id,
        )
        .order_by(QuestionTemplate.priority)
        .all()
    )
    return [
        {"name": fn, "label": lbl, "group": grp}
        for fn, lbl, grp in rows
    ]
