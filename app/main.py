from fastapi import FastAPI
from fastapi.concurrency import asynccontextmanager
from core.config import settings
from api.v1.router import router as api_v1_router
from resume.dynamic_resume_model_manager import (
    initialize_dynamic_resume_model,
)

import logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    await initialize_dynamic_resume_model()
    yield


logger = logging.getLogger(__name__)

app = FastAPI(
    title="Vacancy Assistant API", version="0.1.0", lifespan=lifespan
)

if settings.DEBUG:
    import debugpy

    debugpy.listen(("0.0.0.0", 5678))
    logger.info("Debugger enabled!")

app.include_router(api_v1_router, prefix=settings.API_V1_STR)
