from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
import httpx

from settings import settings
from filters.chat_filters import AdminFilter

router = Router()
INSIGHTS_URL = f"{settings.bots.app_url}/api/v1/resume"


@router.message(AdminFilter(), Command("admin"))
async def admin_cmd(msg: Message):
    txt = ('Доступные команды:\n' +
           '/update_questions -> Обновить базу вопросов\n'
           '/health -> Проверить состояние API\n'
           )
    await msg.answer(txt)


@router.message(AdminFilter(), Command("update_questions"))
async def update_questions_cmd(msg: Message):
    bot_msg = await msg.answer("⏳ Обновляю вопросы из Google Sheets…")
    async with httpx.AsyncClient(timeout=30.0) as cli:
        resp = await cli.post(
            f"{settings.bots.app_url}/api/v1/admin/update-questions",
            json={"token": str(settings.bots.admin_id)},
        )

    if resp.status_code == 200:
        cnt = resp.json()["inserted"]
        await bot_msg.edit_text(f"✅ Готово! Заменено {cnt} вопросов.")
    else:
        await bot_msg.edit_text(f"⚠️ Ошибка: {resp.text}")


@router.message(AdminFilter(), Command(commands=["health"]))
async def health_command(message: Message):
    url = f"{settings.bots.app_url}/api/v1/health_check"
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(url)
    status = "✅ API работает" if resp.status_code == 200 else "❌ Нет связи"
    await message.answer(status)


@router.message(Command("insights"))
async def get_insights_cmd(msg: Message):
    """
    /insights <tg_id> — показывает скрытые факты о пользователе.
    """
    tg_id = msg.from_user.id
    parts = msg.text.split(maxsplit=1)
    if len(parts) > 1 and parts[1].isdigit():
        tg_id = int(parts[1])
        await msg.answer(f"Использование: /insights для {tg_id}")

    await msg.answer("⏳ Запрашиваю инсайты…")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{INSIGHTS_URL}/{tg_id}/insight")

    if resp.status_code == 200:
        data = resp.json()
        facts = data["insights"]
        if facts:
            formatted = "\n".join(f"• {fact}" for fact in facts)
            await msg.answer(f"📝 Факты о пользователе:\n{formatted}")
        else:
            await msg.answer("ℹ️ Фактов пока нет")
    else:
        await msg.answer(f"❌ Ошибка: {resp.text}")
