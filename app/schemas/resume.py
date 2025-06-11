from typing import Any
from pydantic import BaseModel, Field


class ResumeFieldUpdatePayload(BaseModel):
    """Payload for updating a single field in the user's resume data."""
    field_name: str
    value: Any
    tg_id: str


class InsightAppendPayload(BaseModel):
    """Request for saving insight."""
    tg_id: int = Field(..., ge=1)
    description: str = Field(..., max_length=256)
    insight: str = Field(..., max_length=512)


class InsightListResponse(BaseModel):
    """User insights collection."""
    tg_id: int
    insights: list[str]
