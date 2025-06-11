from typing import Optional, Any, Iterable

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from models.resume import Resume


def get_active_resume_for_user(db: Session, user_id: int) -> Optional[Resume]:
    """Retrieves the single active (not archived, incomplete) resume for a user."""
    return (
        db.query(Resume)
        .filter(
            Resume.user_id == user_id,
            Resume.is_archived.is_(False),
        )
        .order_by(Resume.created_at.desc())
        .first()
    )


def get_or_create_active_resume(db: Session, user_id: int) -> Resume:
    """
    Retrieves the active resume for a user, or creates a new one if none exists.
    An active resume is one that is not archived.
    If multiple non-archived resumes exist, this will pick the first one.
    Consider if "incomplete" status is also a criterion for "active" for modification.
    """
    resume = get_active_resume_for_user(db, user_id)
    if not resume:
        # If no active resume, create a new one.
        # The default data is set by the Resume model itself.
        resume = Resume(user_id=user_id)
        db.add(resume)
        db.commit()
        db.refresh(resume)
    return resume


def update_resume_field(
    db: Session, resume: Resume, field_name: str, value: Any
) -> Resume:
    """
    Updates a specific field in the resume's data JSONB object.
    """
    if resume.data is None:
        resume.data = {}
    resume.data[field_name] = value
    flag_modified(resume, "data")
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


def append_resume_insight(
    db: Session,
    resume: Resume,
    description: str,
    insight: str,
) -> Resume:
    """
    Appends a new insight to the resume's insights list.
    """
    facts: list[str] = list(resume.insights or [])
    facts.append(f"{description}: {insight}")
    resume.insights = facts
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


def get_resume_insights(db: Session, resume: Resume) -> Iterable[str]:
    """
    Retrieves all insights from the resume.
    """
    return resume.insights or []
