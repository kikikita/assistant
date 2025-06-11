import logging
import json
from typing import Annotated, Any, Dict, List
from langgraph.prebuilt import InjectedState
from sqlalchemy.orm import Session
from agent.resume import (
    get_user_resume,
    update_user_resume,
    append_user_insight,
)
from agent.validation import validate
from langchain_core.tools import tool

import uuid

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Вспомогательные утилиты
# ---------------------------------------------------------------------------


def _err(msg: str) -> str:
    """Возвращаем ошибку в согласованном формате и одновременно логируем."""
    logger.error(msg)
    return f"{{ 'error': '{msg}' }}"

def _success(msg: str) -> str:
    """Возвращаем успешный результат в согласованном формате и одновременно логируем."""
    logger.info(msg)
    return f"{{ 'success': '{msg}' }}"


def _create_list_entry_dict(item_fields: Dict[str, Any]) -> Dict[str, Any]:
    entry = {
        "id": str(uuid.uuid4())[:5],
        **item_fields,
    }

    return entry


async def _save_resume_field(session: Session, user_id: str, field: str, value: Any) -> str:
    await update_user_resume(session, user_id, field, value)
    return _success("Поле успешно обновлено.")


async def _save_resume_insight(
    session: Session,
    user_id: str,
    description: str,
    insight: str,
) -> str:
    await append_user_insight(session, user_id, description, insight)
    return _success("Инсайт успешно сохранён.")


# ---------------------------------------------------------------------------
# Инструменты для одиночных полей
# ---------------------------------------------------------------------------


@tool
async def update_resume_field(
    field_name: str,
    value: Any,
    state: Annotated[dict, InjectedState],
):
    """Обновляет простое (не составное) поле в резюме пользователя."""
    try:
        user_id = state.get("user_id")
        
        logger.info("calling update_resume_field(%s=%s) [user %s]", field_name, value, user_id)
        if not user_id:
            return _err("User ID not found")

        ok, err_msg = validate(field_name, value)
        if not ok:
            return _err(err_msg)

        state["current_resume"][field_name] = value
        return await _save_resume_field(state["session"], str(user_id), field_name, value)
    except Exception as e:
        return _err(f"Error updating resume field: {e}")

@tool
async def create_list_item(
    list_name: str,
    state: Annotated[dict, InjectedState],
    item_fields: Dict[str, Any] | str = {},
):
    """
    Creates a new item in a resume list field (like work_experience, languages, certificates).
    
    Args:
        list_name: Name of the list field in resume (e.g., "work_experience", "languages", "certificates")
        item_fields: Optional fields for the new item (e.g., position="Developer", company_name="Google")
    
    Example usage:
    - For work experience: create_list_item(list_name="work_experience", item_fields={"position": "Программист"})
    - For languages: create_list_item(list_name="languages", item_fields={"language": "English", "level": "Advanced"})
    - For certificates: create_list_item(list_name="certificates", item_fields={"name": "AWS Certified", "year": "2023"})
    """
    try:
        if isinstance(item_fields, str):
            item_fields = json.loads(item_fields)
        user_id = state.get("user_id")
        if not user_id:
            return _err("User ID not found")
        
        resume_scheme = state.get("resume_scheme", {})
        list_schema = resume_scheme.get("properties", {}).get(list_name)

        if not list_schema or list_schema.get("type") != "array":
            valid_list_names = [name for name, schema in resume_scheme.get("properties", {}).items() if schema.get("type") == "array"]
            return _err("List name is invalid. Valid list names: " + ", ".join(valid_list_names))

        # Собираем словарь со всеми полями (возможно пустыми) для новой записи
        list_entry: Dict[str, Any] = _create_list_entry_dict(item_fields)

        logger.info("create_list_item [user %s]: %s", user_id, list_entry)

        resume = await get_user_resume(user_id)
        list: List[Dict[str, Any]] = resume.get(list_name, [])
        list.insert(0, list_entry)
        
        state["current_resume"][list_name] = list

        await update_user_resume(state["session"], str(user_id), list_name, list)
        return _success(f"{list_name} entry created.")
    except Exception as e:
        return _err(f"Error creating list item: {e}")


@tool
async def update_list_item(
    list_name: str,
    entry_id: str,
    field_name: str,
    value: Any,
    state: Annotated[dict, InjectedState],
):
    """
    Updates a specific field of an existing item in a resume list field.
    
    Args:
        list_name: Name of the list field in resume (e.g., "work_experience", "languages", "certificates")
        entry_id: ID of the item to update
        field_name: Name of the field to update within the item
        value: New value for the field
    
    Example usage:
    - For work experience: update_list_item(list_name="work_experience", entry_id="bgsrf", field_name="position", value="Senior Developer")
    - For languages: update_list_item(list_name="languages", entry_id="abs23", field_name="level", value="Fluent")
    - For certificates: update_list_item(list_name="certificates", entry_id="fsw12", field_name="year", value="2024")
    """
    try:
        user_id = state.get("user_id")
        if not user_id:
            return _err("User ID not found")

        if not list_name:
            return _err("List name is required")

        resume = await get_user_resume(user_id)
       
        list_items = resume.get(list_name, [])
        entry_index = None
        for i, item in enumerate(list_items):
            if item.get("id") == entry_id:
                entry_index = i
                break
        
        if entry_index is None:
            return _err(f"Entry with ID {entry_id} not found in {list_name}")
        
        resume[list_name][entry_index][field_name] = value
        
        state["current_resume"][list_name] = resume[list_name]

        await update_user_resume(state["session"], str(user_id), list_name, resume[list_name])
        return _success(f"{list_name} item updated.")
    except Exception as e:
        return _err(f"Error updating list item: {e}")

@tool
async def remove_list_item(
    list_name: str,
    entry_id: str,
    state: Annotated[dict, InjectedState],
):
    """
    Removes an item from a resume list field by ID.
    
    Args:
        list_name: Name of the list field in resume (e.g., "work_experience", "languages", "certificates")
        entry_id: ID of the item to remove
    
    Example usage:
    - For work experience: remove_list_item(list_name="work_experience", entry_id="bgsrf")
    - For languages: remove_list_item(list_name="languages", entry_id="abs23")
    - For certificates: remove_list_item(list_name="certificates", entry_id="fsw12")
    """
    try:
        user_id = state.get("user_id")
        if not user_id:
            return _err("User ID not found")

        if not list_name:
            return _err("List name is required")

        resume = await get_user_resume(user_id)

        list_items = resume.get(list_name, [])
        entry_index = None
        for i, item in enumerate(list_items):
            if item.get("id") == entry_id:
                entry_index = i
                break

        if entry_index is None:
            return _err(f"Entry with ID {entry_id} not found in {list_name}")

        resume[list_name].pop(entry_index)

        state["current_resume"][list_name] = resume[list_name]

        await update_user_resume(state["session"], str(user_id), list_name, resume[list_name])
        return _success(f"{list_name} item removed.")
    except Exception as e:
        return _err(f"Error removing item from {list_name}: {e}")


@tool
async def save_interview_insight(
    description: str,
    insight: str,
    state: Annotated[dict, InjectedState],
):
    """
    Saves insights about a candidate during interview process.

    Use this tool to record important observations, conclusions, or insights
    about the candidate based on their responses or behavior during the interview.

    Args:
        description: Brief description of what was observed or discussed
        insight: The actual insight or conclusion about the candidate

    Example:
    - description: "Response to technical question about databases"
    - insight: "Shows strong understanding of SQL optimization but lacks NoSQL experience"
    """
    try:
        user_id = state.get("user_id")
        if not user_id:
            return _err("User ID not found")

        logger.info(
            "calling save_interview_insight(%s → %s) [user %s]",
            description,
            insight,
            user_id,
        )
        return await _save_resume_insight(
            state["session"],
            str(user_id),
            description,
            insight,
        )
    except Exception as exc:
        return _err(f"Error saving interview insight: {exc}")


# ---------------------------------------------------------------------------
# Регистрируем экспортируемые инструменты
# ---------------------------------------------------------------------------

available_tools = [
    update_resume_field,
    create_list_item,
    update_list_item,
    remove_list_item,
    save_interview_insight,
]
