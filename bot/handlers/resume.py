from typing import Any, Dict, List
import asyncio
import httpx
from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from keyboards.inline import (
    consent_kb,
    resume_completed_kb,
    resume_reset_or_continue_kb,
)
from settings import settings
from utils.states import DialogSG

router = Router()

# ──────────────── Telegram limits & helpers ───────────────────────

MAX_TG_MSG = 4096          # формальный предел Telegram
SAFE_TG_MSG = 4000          # оставляем запас для html-тегов


# ────────────────────────── PDF resume ────────────────────────────
@router.message(F.document.mime_type == "application/pdf")
async def pdf_resume_cb(message: Message, bot: Bot, state: FSMContext) -> None:
    """
    Принимает PDF-файл, отдаёт его старой ручке /dialog/pdf.
    Далее:
      • если backend вернул итоговое резюме – показываем его;
      • иначе (нужно уточнение) – переключаем общение на агента.
    """
    status_msg = await message.answer("⏳ Распознаю резюме, подождите...")
    tg_id = str(message.from_user.id)

    # — скачиваем файл из Telegram —
    doc = message.document
    file = await bot.get_file(doc.file_id)
    raw = await bot.download_file(file.file_path)
    files = {"file": ("resume.pdf", raw, "application/pdf")}

    async with httpx.AsyncClient(timeout=120.0) as cli:
        resp = await cli.post(
            f"{settings.bots.app_url}/api/v1/dialog/pdf",
            data={"tg_id": tg_id},
            files=files,
        )

    if resp.status_code != 200:
        await status_msg.edit_text(
            "⚠️ Не удалось распознать PDF. Попробуйте ещё раз."
        )
        return

    data = resp.json()

    # — готовый CV из PDF —
    if "cv_markdown" in data:
        await _send_long(
            message.chat.id,
            f"✅ Я собрал резюме!\n\n{data['cv_markdown']}",
            bot,
            reply_markup=resume_completed_kb(),
        )
        await state.clear()
        return

    # — нужен диалог с агентом для уточнений —
    await status_msg.edit_text(
        "✅ Резюме загружено! Теперь задам несколько уточняющих вопросов."
    )
    await _start_agent_flow(
        message.chat.id,
        message.from_user.id,
        bot,
        state,
        initial_prompt="Продолжим: уточни детали резюме, которые ещё не распознаны",
        message=message,
    )


def _split_long(text: str, limit: int = SAFE_TG_MSG) -> List[str]:
    """
    Делит длинный текст (обычный или HTML/Markdown) на части ≤ limit.
    """
    if len(text) <= limit:
        return [text]

    parts: List[str] = []
    while len(text) > limit:
        cut = text.rfind("\n\n", 0, limit)
        if cut == -1:
            cut = text.rfind("\n", 0, limit)
        if cut == -1:
            cut = limit
        parts.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    if text:
        parts.append(text)
    return parts


async def _send_long(
    chat_id: int,
    text: str,
    bot: Bot,
    *,
    reply_markup=None,
    parse_mode=ParseMode.HTML,
) -> None:
    """
    Отправляет текст (возможно многострочный) несколькими сообщениями.
    """
    chunks = _split_long(text)
    for i, chunk in enumerate(chunks):
        await bot.send_message(
            chat_id,
            chunk,
            parse_mode=parse_mode,
            reply_markup=reply_markup if i == len(chunks) - 1 else None,
            disable_web_page_preview=True,
        )


# ────────────────────────── LLM-агент ─────────────────────────────

async def _ask_agent(tg_id: int, text: str, message: Message) -> str:
    """
    Унифицированная оболочка: шлём сообщение ассистенту
    и возвращаем его ответ (строка).
    """
    stop_typing = asyncio.Event()
    asyncio.create_task(send_typing_periodically(message, stop_typing))
    try:
        async with httpx.AsyncClient(timeout=20.0) as cli:
            resp = await cli.post(
                f"{settings.bots.app_url}/api/v1/dialog/agent",
                json={"user_id": tg_id, "message": text},
            )
        if resp.status_code != 200:
            return (
                "⚠️ Извините, сервис временно недоступен. "
                "Попробуйте повторить запрос чуть позже."
            )
        return resp.json().get("answer") or "…"
    except httpx.ReadTimeout:
        return "Извините, не могу ответить на данное сообщение."
    finally:
        stop_typing.set()


# ────────────────────────── согласия ──────────────────────────────

async def _check_consent(tg_id: int) -> bool:
    """True ⇢ пользователь принял оба юридических согласия."""
    url = f"{settings.bots.app_url}/api/v1/auth/tg"
    async with httpx.AsyncClient(timeout=5.0) as cli:
        resp = await cli.post(url, json={"tg_id": tg_id})
    if resp.status_code != 200:
        return False
    user: Dict[str, Any] = resp.json()["user"]
    return bool(user.get("pdn_agreed") and user.get("offer_agreed"))


# ────────────────────────── вход в диалог ─────────────────────────

async def _start_agent_flow(
    chat_id: int,
    tg_id: int,
    bot: Bot,
    state: FSMContext,
    *,
    initial_prompt: str,
    message: Message,
) -> None:
    """
    Запускает диалог с LLM-ассистентом:
      • шлём ассистенту «initial_prompt»,
      • выводим его ответ,
      • переключаем FSM в waiting_for_answer.
    """
    await bot.send_chat_action(chat_id, "typing")
    answer = await _ask_agent(tg_id, initial_prompt, message)
    await _send_long(chat_id, answer, bot, parse_mode=ParseMode.MARKDOWN)
    await state.set_state(DialogSG.waiting_for_answer)


async def _begin_dialog(
    chat_id: int,
    tg_id: int,
    bot: Bot,
    state: FSMContext,
    message: Message,
) -> None:
    """
    Определяет, что именно показать пользователю при нажатии
    «📝 Заполнить резюме»: готовое, частичное или запуск нового
    диалога с ассистентом.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{settings.bots.app_url}/api/v1/dialog/next",
            json={"user_id": tg_id},
            timeout=10.0,
        )
    if resp.status_code != 200:
        await bot.send_message(chat_id, "⚠️ Сервис временно недоступен.")
        return

    data: Dict[str, Any] = resp.json()

    # ── уже готовое резюме ────────────────────────────────────────
    if data.get("cv_markdown") and "resume_id" not in data:
        await _send_long(
            chat_id,
            f"✅ Резюме уже готово:\n\n{data['cv_markdown']}",
            bot,
            reply_markup=resume_completed_kb(),
        )
        return

    # ── есть черновик ─────────────────────────────────────────────
    if data.get("resume_id"):
        await _send_long(
            chat_id,
            f"📝 Вы начали, но ещё не завершили:\n\n{data['cv_markdown']}",
            bot,
            reply_markup=resume_reset_or_continue_kb(data["resume_id"]),
        )
        return

    # ── нового диалога ещё не начинали – запускаем ассистента ────
    await _start_agent_flow(
        chat_id,
        tg_id,
        bot,
        state,
        initial_prompt="Начать заполнение резюме",
        message=message,
    )


# ────────────────────────── public handlers ───────────────────────

@router.message(F.text == "📝 Заполнить резюме")
async def start_dialog(message: Message, bot: Bot, state: FSMContext) -> None:
    await state.clear()
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
    await _begin_dialog(message.chat.id, message.from_user.id, bot, state, message)


@router.callback_query(F.data.startswith("consent:"))
async def consent_cb(
    query: CallbackQuery,
    bot: Bot,
    state: FSMContext,
) -> None:
    await query.answer()
    if query.data.endswith(":no"):
        await query.message.answer(
            "😔 Без согласия мы не сможем продолжить.\n"
            "При желании нажмите «📝 Заполнить резюме» ещё раз.",
        )
        await query.message.delete_reply_markup()
        return

    url = f"{settings.bots.app_url}/api/v1/users/consent"
    async with httpx.AsyncClient(timeout=5.0) as cli:
        await cli.post(url, json={"tg_id": query.from_user.id, "agree": True})
    await query.message.delete_reply_markup()

    await _begin_dialog(query.message.chat.id, query.from_user.id, bot, state, query.message)


# ────────────────────────── поток общения ─────────────────────────

async def send_typing_periodically(message: Message, stop_event: asyncio.Event):
    """Send typing indicator every 4 seconds until stop_event is set"""
    while not stop_event.is_set():
        try:
            await message.bot.send_chat_action(message.chat.id, "typing")
            await asyncio.wait_for(stop_event.wait(), timeout=4.0)
        except asyncio.TimeoutError:
            continue # Timeout is expected, continue sending typing

@router.message(DialogSG.waiting_for_answer)
async def relay_to_agent(message: Message, state: FSMContext) -> None:
    """
    Любое пользовательское сообщение → ассистенту, ответ – обратно.
    """
    answer = await _ask_agent(message.from_user.id, message.text or "", message)
    await _send_long(message.chat.id, answer, message.bot, parse_mode=ParseMode.MARKDOWN)


# ─────────────────── reset / continue черновика ───────────────────

@router.callback_query(F.data == "resume:reset")
async def reset_resume(
    query: CallbackQuery,
    state: FSMContext,
    bot: Bot,
) -> None:
    """Архивируем черновик, создаём новый и сразу зовём ассистента."""
    await query.answer()
    await state.clear()

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{settings.bots.app_url}/api/v1/dialog/reset",
            json={"user_id": query.from_user.id},
            timeout=10.0,
        )
    if resp.status_code != 200:
        await query.message.answer("⚠️ Не удалось начать заново.")
        return

    await query.message.answer("🔁 Заполняем резюме заново!")
    await _start_agent_flow(
        query.message.chat.id,
        query.from_user.id,
        bot,
        state,
        initial_prompt="Начнём заполнение резюме заново",
        message=query.message,
    )


@router.callback_query(F.data.startswith("resume:continue:"))
async def continue_resume(
    query: CallbackQuery,
    bot: Bot,
    state: FSMContext,
) -> None:
    """
    Возобновляем черновик в БД, дальше снова передаём управление ассистенту.
    """
    await query.answer()
    resume_id = int(query.data.split(":")[-1])

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{settings.bots.app_url}/api/v1/dialog/resume-continue",
            json={"resume_id": resume_id, "user_id": query.from_user.id},
            timeout=10.0,
        )
    if resp.status_code != 200:
        await query.message.answer("⚠️ Ошибка при продолжении заполнения.")
        return

    await query.message.answer("✍️ Продолжаем заполнение!")
    await _start_agent_flow(
        query.message.chat.id,
        query.from_user.id,
        bot,
        state,
        initial_prompt="Продолжим заполнять резюме",
        message=query.message,
    )
