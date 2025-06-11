import io
from typing import Final

import aiohttp
from fastapi import (
    APIRouter,
    File,
    HTTPException,
    UploadFile,
    status,
)
from pydantic import BaseModel

from core.config import settings

router = APIRouter(prefix="/audio", tags=["Dialog Audio"])

YANDEX_STT_URL: Final = (
    "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
)
ASR_TIMEOUT = aiohttp.ClientTimeout(total=120)


class _TranscriptionResponse(BaseModel):
    text: str


async def _recognize_with_yc(
    audio_bytes: bytes,
) -> str:
    """Отправляет запрос в Yandex SpeechKit и возвращает текст."""
    params = {
        "folderId": settings.YC_FOLDER_ID.get_secret_value(),
        "lang": "ru-RU",
        "format": "oggopus",
        "model": settings.YC_MODEL_VERSION,
    }
    headers = {
        "Authorization": f"Api-Key "
        f"{settings.YC_API_KEY.get_secret_value()}",
        "Content-Type": "application/octet-stream",
    }

    async with aiohttp.ClientSession(timeout=ASR_TIMEOUT) as session:
        async with session.post(
            YANDEX_STT_URL,
            params=params,
            data=io.BytesIO(audio_bytes),
            headers=headers,
        ) as resp:
            data = await resp.json()
            if resp.status != 200 or "error_code" in data:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"SpeechKit error: {data}",
                )
    return data.get("result", "")


@router.post(
    "/",
    response_model=_TranscriptionResponse,
)
async def recognize_audio(
    file: UploadFile = File(...)
) -> _TranscriptionResponse:
    """Принимает аудио и возвращает расшифровку текста."""
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file",
        )

    text = await _recognize_with_yc(content)
    if not text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not recognize speech",
        )
    return _TranscriptionResponse(text=text)
