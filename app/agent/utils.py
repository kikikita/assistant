from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

__all__ = ["get_next_question"]



# helpers
def _is_filled(value: Any) -> bool:
    """Проверка «поле заполнено?»."""
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, dict)):
        return bool(value)
    return True  # число / bool


def _priority_of(meta: Dict[str, Any]) -> int:
    """
    Определяем приоритет узла схемы.

    * Если есть собственный "priority" — берём его.
    * Для групп (type=array) берём min(priority) из дочерних полей.
    * Иначе ставим 'бесконечность', чтобы такие узлы не влияли.
    """
    if "priority" in meta:
        return meta["priority"]

    if meta.get("type") == "array":
        child_props = meta["items"]["properties"]
        child_priorities = [
            v["priority"] for v in child_props.values() if "priority" in v
        ]
        if child_priorities:
            return min(child_priorities)

    return 10**9


def _iter_schema_props(
    schema_props: Dict[str, Any],
    resume_fragment: Dict[str, Any],
    prefix: str = "",
) -> List[Tuple[str, str, int]]:
    """
    Рекурсивный обход схемы:
    возвращает список (field_path, question, priority) незаполненных полей.
    """
    candidates: List[Tuple[str, str, int]] = []

    for field, meta in sorted(
        schema_props.items(), key=lambda item: _priority_of(item[1])
    ):
        if meta.get("type") != "array":
            if not _is_filled(resume_fragment.get(field)) and meta["question"] not in ["", "-"]:
                candidates.append(
                    (f"{prefix}{field}", meta["question"], _priority_of(meta))
                )
            continue
        
        group_items_schema = meta["items"]["properties"]
        group_resume: List[Dict[str, Any]] = resume_fragment.get(field, [])

        if not group_resume:
            first_field, first_meta = min(
                group_items_schema.items(), key=lambda i: _priority_of(i[1])
            )
            candidates.append(
                (
                    f"{prefix}{field}.{first_field}",
                    first_meta["question"],
                    _priority_of(first_meta),
                )
            )
            continue

        for item in group_resume:
            candidates.extend(
                _iter_schema_props(
                    group_items_schema, item, prefix=f"{prefix}{field}."
                )
            )

    return candidates


# public
def get_next_question(
    current_resume: Dict[str, Any],
    resume_schema: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Возвращает ближайший незаполненный вопрос или None,
    если резюме полностью заполнено.
    """
    props = resume_schema.get("properties", {})
    # Игнорировать вопрос про PDF если есть специальный флаг
    if current_resume.get("resume_pdf") == "ignored":
        props = {k: v for k, v in props.items() if k != "resume_pdf"}
    candidates = _iter_schema_props(props, current_resume)

    if not candidates:
        return None

    next_field, next_question, next_priority = min(
        candidates, key=lambda x: x[2]
    )
    return {
        "field_name": next_field,
        "question": next_question,
        "priority": next_priority,
    }
