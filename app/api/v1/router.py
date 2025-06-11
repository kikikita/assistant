from fastapi import APIRouter
from api.v1.endpoints import (
    auth,
    user,
    health,
    dialog,
    dialog_pdf,
    dialog_audio,
    questions_sync,
    resume_schema,
    resume,
    dialog_agent
)

router = APIRouter()
router.include_router(health.router, tags=["Health"])
router.include_router(auth.router, tags=["Auth"])
router.include_router(user.router, tags=["User"])
router.include_router(dialog.router, tags=["Dialog"])
router.include_router(dialog_pdf.router, prefix="/dialog", tags=["Dialog PDF"])
router.include_router(dialog_audio.router, prefix="/dialog",
                      tags=["Dialog Audio"])
router.include_router(questions_sync.router, prefix="/admin", tags=["Admin"])
router.include_router(resume_schema.router, tags=["Schema"])
router.include_router(resume.router, prefix="/resume", tags=["Resume"])
router.include_router(dialog_agent.router, tags=["Dialog Agent"])
