import httpx
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from settings import settings

router = Router()
AGENT_ENDPOINT = f"{settings.bots.app_url}/api/v1/dialog/agent"

@router.message(F.text)
async def unknown_message(message: Message, state: FSMContext):
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(
                AGENT_ENDPOINT,
                json={
                    "message": message.text,
                    "user_id": message.from_user.id,
                }
            )
            answer = resp.json().get("answer", "Ошибка ассистента")
    except httpx.ReadTimeout:
        answer = "Извините, ассистент не ответил вовремя. Попробуйте ещё раз."
    except Exception as e:
        answer = f"Ошибка ассистента: {type(e).__name__}"

    await message.answer(answer, parse_mode="Markdown")
