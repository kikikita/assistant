from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session


from api import deps
from schemas.resume import (
    ResumeFieldUpdatePayload,
    InsightAppendPayload,
    InsightListResponse,
)
from crud.resume import (
    get_or_create_active_resume,
    update_resume_field,
    append_resume_insight,
    get_resume_insights,
)
from crud.user import get_user_by_tg_id
import logging

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("/{tg_id}")
async def get_resume(
    tg_id: int,
    db: Session = Depends(deps.get_db),
):
    """
    Retrieve the user's active resume.
    """
    current_user = get_user_by_tg_id(db=db, tg_id=tg_id)
    resume = get_or_create_active_resume(db=db, user_id=current_user.id)
    return resume.data


@router.put("/update")
async def update_resume_field_value(
    payload: ResumeFieldUpdatePayload,
    db: Session = Depends(deps.get_db),
):
    """
    Update a specific field in the user's active resume.
    If no active resume exists, one will be created.
    """
    current_user = get_user_by_tg_id(db=db, tg_id=payload.tg_id)
    resume = get_or_create_active_resume(db=db, user_id=current_user.id)

    updated_resume = update_resume_field(
        db=db,
        resume=resume,
        field_name=payload.field_name,
        value=payload.value
    )

    return updated_resume.data


@router.put("/insight", response_model=dict)
async def append_insight(
    payload: InsightAppendPayload,
    db: Session = Depends(deps.get_db),
):
    """
    Append a new insight to the user's active resume.
    """
    user = get_user_by_tg_id(db=db, tg_id=payload.tg_id)
    resume = get_or_create_active_resume(db=db, user_id=user.id)

    append_resume_insight(
        db=db,
        resume=resume,
        description=payload.description,
        insight=payload.insight,
    )
    return {"success": "Insight saved"}


@router.get("/{tg_id}/insight", response_model=InsightListResponse)
async def list_insights(
    tg_id: int,
    db: Session = Depends(deps.get_db),
):
    """
    List all insights for the user's active resume.
    """
    user = get_user_by_tg_id(db=db, tg_id=tg_id)
    resume = get_or_create_active_resume(db=db, user_id=user.id)

    insights = get_resume_insights(db=db, resume=resume)
    return InsightListResponse(tg_id=tg_id, insights=list(insights))
