import httpx
from aiogram import Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message

from keyboards.reply import get_main_kb, remove_kb
from settings import settings

router = Router()


@router.message(Command("start"))
async def start_command(message: Message):
    """Регистрирует пользователя в бэкэнде и приветствует его."""
    url = f"{settings.bots.app_url}/api/v1/auth/tg"
    payload = {"tg_id": message.from_user.id}

    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.post(url, json=payload)

    if resp.status_code != 200:
        await message.answer("⚠️ Сервис временно недоступен.")
        return

    welcome = (
        f"👋 Привет, <b>{message.from_user.first_name}</b>!\n\n"
        "Я — умный HR-ассистент Tomoru.Team. "
        "В диалоговом режиме помогу тебе составить современное и "
        "привлекательное резюме для поиска работы.\n\n"
        "Что я умею:\n"
        "• Принимать <b>готовые резюме в PDF</b> — я сам извлеку нужную информацию\n"
        "• Распознавать <b>аудио-сообщения</b> — просто надиктуй свой ответ\n"
        "• Вести диалог и подсказывать, что и как лучше написать\n\n"
        "Чтобы узнать о доступных возможностях, нажми /help\n"
        "Для старта — жми кнопку <b>Заполнить резюме</b> или напиши любой вопрос."
    )
    await message.answer(welcome, parse_mode=ParseMode.HTML,
                         reply_markup=get_main_kb())


@router.message(Command(commands=["help"]))
async def help_command(message: Message):
    help_message = (
        "ℹ️ <b>Как пользоваться HR-ассистентом Tomoru.Team:</b>\n\n"
        "<b>1. Заполнение резюме</b>\n"
        "— Нажмите кнопку <b>Заполнить резюме</b> и следуйте инструкциям.\n"
        "— Я буду задавать простые вопросы. Просто отвечайте на них, чтобы заполнить все разделы.\n\n"
        "<b>2. Голосовые сообщения</b>\n"
        "— Можете надиктовывать ответы голосом. Я распознаю речь и обработаю ваш ответ как текст.\n\n"
        "<b>3. Загрузка PDF</b>\n"
        "— Если у вас уже есть резюме в PDF — отправьте его сюда, и я сам заполню нужные поля.\n\n"
        "<b>4. Редактирование резюме</b>\n"
        "— Чтобы изменить любую информацию, просто напишите: "
        "\"Измени номер телефона\" или \"Обновить образование\" — я помогу скорректировать нужное поле.\n\n"
        "<b>5. Получение итогового резюме</b>\n"
        "— После заполнения всех полей вы получите готовое резюме в удобном формате.\n\n"
        "<b>Доступные команды:</b>\n"
        "/start — Запустить бота заново\n"
        "/help — Показать эту справку\n\n"
        "❓ <b>Если возникнут вопросы — просто напишите мне!</b>"
    )
    await message.answer(
            help_message,
            parse_mode=ParseMode.HTML,
            reply_markup=remove_kb
            )
