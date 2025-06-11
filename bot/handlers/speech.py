import logging
import tempfile
from pathlib import Path

import httpx
from aiogram import F, Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from settings import settings

router = Router()
logger = logging.getLogger(__name__)

ASR_ENDPOINT = f"{settings.bots.app_url}/api/v1/dialog/audio/"
AGENT_ENDPOINT = f"{settings.bots.app_url}/api/v1/dialog/agent"
HTTP_TIMEOUT = 60.0


async def _download_telegram_file(bot, file_id: str,
                                  suffix: str = ".ogg") -> Path:
    """Скачивает файл Telegram во временную папку и
    возвращает путь к нему."""
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    path = Path(tmp.name)
    await bot.download(file_id, destination=path)
    tmp.close()
    return path


async def _send_to_asr(file_path: Path) -> str:
    """Отправляет файл на сервис ASR и возвращает текст."""
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as cli:
        with file_path.open("rb") as fh:
            resp = await cli.post(
                ASR_ENDPOINT,
                files={
                    "file": (file_path.name,
                             fh,
                             "application/octet-stream")
                },
            )

    if resp.status_code != 200:
        logger.error("ASR %s → %s", resp.status_code, resp.text)
        raise RuntimeError("ASR service error")

    return resp.json().get("text", "")


async def _send_to_agent(transcript: str, user_id: int) -> str:
    """Отправляет текст на сервис агента и возвращает ответ."""
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.post(
            AGENT_ENDPOINT,
            json={
                "message": transcript,
                "user_id": user_id,
            }
        )
    if resp.status_code != 200:
        logger.error("AGENT %s → %s", resp.status_code, resp.text)
        return "Ошибка ассистента"
    return resp.json().get("answer", "Ошибка ассистента")


@router.message(F.voice | F.audio)
async def voice_message(message: Message, state: FSMContext) -> None:
    """Обрабатывает голосовые и аудио-сообщения."""
    bot = message.bot
    await bot.send_chat_action(message.chat.id, "typing")

    media = message.voice or message.audio  # type: ignore
    tmp_path: Path | None = None

    try:
        tmp_path = await _download_telegram_file(bot, media.file_id)
        transcript = await _send_to_asr(tmp_path)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Speech err: %s", exc)
        await message.answer(
            "Не удалось обработать аудио. "
            "Попробуйте ещё раз позже 🙏",
        )
        return
    finally:
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                logger.warning("Tmp not removed: %s", tmp_path)

    if not transcript:
        await message.answer("К сожалению, речь не распознана 😔")
        return

    await bot.send_chat_action(message.chat.id, "typing")
    try:
        answer = await _send_to_agent(transcript, message.from_user.id)
    except Exception as exc:
        logger.exception("Agent err: %s", exc)
        answer = "Ошибка ассистента"

    await message.answer(answer)
