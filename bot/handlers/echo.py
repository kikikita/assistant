import httpx
from aiogram import Router, F
from aiogram.enums import ParseMode
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from keyboards.inline import consent_kb
from handlers.resume import _check_consent
from settings import settings

router = Router()
AGENT_ENDPOINT = f"{settings.bots.app_url}/api/v1/dialog/agent"

@router.message(F.text)
async def unknown_message(message: Message, state: FSMContext):
    consent_txt = (
        "Как хорошо воспитанный робот, я должен получить ваше согласие "
        "на обработку персональных данных и согласие с офертой.\n\n"
        "Пожалуйста, ознакомьтесь с документом по "
        '<a href="https://tomoru.team/useragreement">ссылке</a>\n\n'
        "Вы согласны с этим документом?"
    )
    if not await _check_consent(message.from_user.id):
        await message.answer(
            consent_txt,
            parse_mode=ParseMode.HTML,
            reply_markup=consent_kb(),
            disable_web_page_preview=True,
        )
        return
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
