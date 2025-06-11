import json
from typing import Dict, Any
from sqlalchemy import Boolean, Column, Integer, JSON, String
from db.base import Base


class QuestionTemplate(Base):
    """
    Шаблон одного шага диалога.

    Attributes
    ----------
    field_name : str
        Уникальный ключ; первичный ключ таблицы.
    label : str
        “Читабельное” название поля (для CV и темплейтов).
    priority : int
        Порядок вопросов (возрастающий).
    template : str
        Содержимое вопроса для пользователя.
    inline_kb : bool
        Если True — показываем inline-кнопки.
    multi_select : bool
        Разрешён многоразовый выбор.
    buttons : JSON[list[str]]
        Сами тексты кнопок (массив строк).
    destination : str
        Куда сохранять: “users” | “resume_fields” | “work_experience” | …
    group_id : str | None
        Если этот вопрос — часть повторяемой группы
        (например “work_experience”), то здесь её ключ.
    is_last : bool
        Для циклических групп: последний вопрос цикла?
        По нему мы выходим из цикла.
    """

    __tablename__ = "question_templates"

    field_name = Column(String, primary_key=True)
    label = Column(String, nullable=False)
    priority = Column(Integer, nullable=False, index=True)
    template = Column(String, nullable=False)

    inline_kb = Column(Boolean, default=False, nullable=False)
    multi_select = Column(Boolean, default=False, nullable=False)
    buttons = Column(JSON, nullable=True)

    destination = Column(String, default="resume", nullable=False)
    group_id = Column(String, nullable=True, index=True)
    is_last = Column(Boolean, default=False, nullable=False)

    @classmethod
    def from_sheet_row(cls, row: Dict[str, str]) -> "QuestionTemplate":
        """
        Создет объект из строк Google Sheets.
        """
        def _bool(val: str) -> bool:
            return str(val).strip().upper() == "TRUE"

        def _json_or_none(val: str) -> Any:
            s = (val or "").strip()
            if not s:
                return None
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                return None

        return cls(
            field_name=row["field_name"],
            label=row["label"],
            priority=int(row["priority"]),
            template=row["template"],
            inline_kb=_bool(row["inline_kb"]),
            multi_select=_bool(row["multi_select"]),
            buttons=_json_or_none(row["buttons"]),
            destination=row["destination"],
            group_id=(row["group_id"] or None),
            is_last=_bool(row["is_last"]),
        )
