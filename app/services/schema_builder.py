from typing import Dict, Any
from sqlalchemy.orm import Session
from models.question_template import QuestionTemplate


def build_resume_schema(db: Session) -> Dict[str, Any]:
    """
    Генерирует JSON-Schema по текущему содержимому question_templates.
    Группы (work_experience и т.п.) превращаются во вложенные объекты/массивы.
    """
    root: Dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Resume schema",
        "type": "object",
        "properties": {},
    }
    group_props: Dict[str, Dict[str, Any]] = {}

    for qt in db.query(QuestionTemplate).order_by(QuestionTemplate.priority):
        prop = {
            "question": qt.template,
            "priority": qt.priority,
        }
        if qt.buttons:
            prop["enum"] = qt.buttons

        if qt.group_id:  # вложенное поле
            grp = qt.group_id
            group_props.setdefault(grp, {})[qt.field_name] = prop
        else:
            root["properties"][qt.field_name] = prop

    # группы в корне схемы
    for gid, props in group_props.items():
        root["properties"][gid] = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": props,
            },
            "description": f"Повторяющаяся группа полей «{gid}»",
        }

    return root
