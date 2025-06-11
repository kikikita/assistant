
from typing import Optional, Type, List, Dict, Any, Tuple
from pydantic import BaseModel, create_model
from sqlalchemy.orm import Session
from db.session import SessionLocal
from crud.dialog import get_resume_parse_fields
from agent.llm import create_precise_llm

from logging import getLogger

logger = getLogger(__name__)


class DynamicResumeModelManager:
    """
    Manages the lifecycle of a dynamically created Pydantic model for resume parsing.
    This model's structure is determined at runtime based on database field definitions.
    """

    def __init__(self):
        self.model: Optional[Type[BaseModel]] = None
        self.initialized: bool = False
        self.resume_fields: List[Dict[str, Any]] = []
        self.llm = None

    async def initialize_model(self):
        """
        Initializes the dynamic Pydantic model for resume parsing.
        Fetches field definitions from the database, builds Pydantic field definitions,
        and creates the model.
        """
        logger.info("Attempting to initialize dynamic resume model...")
        if not SessionLocal:
            logger.error(
                "SessionLocal not available from db.session. Cannot initialize dynamic model at startup.",
                exc_info=True,
            )
            self.initialized = False
            return

        db: Optional[Session] = None
        try:
            db = SessionLocal()
            self.resume_fields = get_resume_parse_fields(db)
            if not self.resume_fields:
                logger.warning(
                    "No fields returned from get_resume_parse_fields. Dynamic model will be empty or minimal."
                )

            pydantic_model_fields = _build_dynamic_model_field_definitions(
                self.resume_fields
            )

            self.model = create_model(
                "GlobalDynamicResumeModel",  # Name of the dynamically created Pydantic model
                **pydantic_model_fields,
            )

            self.llm = create_precise_llm().with_structured_output(self.model)

            self.initialized = True
            if self.model:
                logger.info(
                    f"Dynamic resume model '{self.model.__name__}' initialized successfully "
                    f"with fields: {list(pydantic_model_fields.keys())}"
                )
            else:
                logger.error(
                    "Dynamic resume model creation resulted in None, though no exception was raised.",
                    exc_info=True,
                )
                self.initialized = False

        except Exception as e:
            logger.error(
                f"Failed to initialize dynamic resume model: {e}", exc_info=True
            )
            self.initialized = False
            self.model = None  # Ensure model is reset on failure
        finally:
            if db:
                db.close()


def _build_dynamic_model_field_definitions(
    db_fields: List[Dict[str, Any]],
) -> Dict[str, Tuple[Type, Any]]:
    """
    Builds the field definitions for a dynamic Pydantic model based only on database fields.
    """
    pydantic_definitions: Dict[str, Tuple[Type, Any]] = {}

    # Separate fields into non-grouped and grouped
    non_grouped_fields: List[Dict[str, Any]] = []
    # group_name -> list of field definitions for that group
    grouped_fields_map: Dict[str, List[Dict[str, Any]]] = {}

    for field_def in db_fields:
        group_name = field_def.get("group")
        if group_name:
            if group_name not in grouped_fields_map:
                grouped_fields_map[group_name] = []
            grouped_fields_map[group_name].append(field_def)
        else:
            non_grouped_fields.append(field_def)

    # Process non-grouped fields
    for field_def in non_grouped_fields:
        field_name = field_def["name"]
        pydantic_definitions[field_name] = (Optional[str], None)

    for group_name, fields_in_group_defs in grouped_fields_map.items():
        inner_model_field_names = sorted(
            list(set(f_def["name"] for f_def in fields_in_group_defs))
        )

        if len(inner_model_field_names) > 1:
            # This group has multiple fields, so define a specific Pydantic model for its items.
            inner_model_pydantic_fields: Dict[str, Tuple[Type, Any]] = {
                name: (Optional[str], None) for name in inner_model_field_names
            }

            model_name = group_name.capitalize() + "Item"

            InnerGroupModel = create_model(model_name, **inner_model_pydantic_fields)
            pydantic_definitions[group_name] = (Optional[List[InnerGroupModel]], None)
        else:
            # For groups with 1 field, use List[str]
            pydantic_definitions[group_name] = (Optional[List[str]], None)

    return pydantic_definitions


dynamic_resume_model_manager = DynamicResumeModelManager()


async def initialize_dynamic_resume_model():
    await dynamic_resume_model_manager.initialize_model()
