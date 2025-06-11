import json
from typing import Any, Dict, List

import httpx
from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from keyboards.inline import (
    build_answer_keyboard,
    consent_kb,
    resume_completed_kb,
    resume_reset_or_continue_kb,
)
from settings import settings
from utils.states import DialogSG

router = Router()
CONFIRM_MARK = "__confirm__"

# ──────────────── Telegram limits & helpers ───────────────────────

MAX_TG_MSG = 4096          # формальный лимит Telegram
SAFE_TG_MSG = 4000


def _split_long_html(text: str, limit: int = SAFE_TG_MSG) -> List[str]:
    """
    Делит длинный HTML-текст на части ≤ limit символов.
    • режет по двойному '\n\n', затем по '\n', и лишь затем по лимиту.
    • теговая целостность не проверяется, но для простого markdown достаточно.
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


async def _send_cv(
    chat_id: int,
    cv_markdown: str,
    bot: Bot,
    *,
    prefix: str | None = None,
    reply_markup=None,
) -> None:
    """
    Отправляет CV несколькими сообщениями, если нужно.
    • reply_markup добавляется только к первому сообщению.
    """
    full_text = f"{prefix}\n{cv_markdown}" if prefix else cv_markdown
    chunks = _split_long_html(full_text)

    for i, chunk in enumerate(chunks):
        await bot.send_message(
            chat_id,
            chunk,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup if i == len(chunks) - 1 else None,
        )

# ───────────────────────────── PDF ────────────────────────────────


@router.message(F.document.mime_type == "application/pdf")
async def pdf_resume_cb(message: Message, bot: Bot, state: FSMContext) -> None:
    """
    Полный flow в один запрос:
      • грузим PDF,
      • backend возвращает либо QuestionOut, либо CVOut,
      • выводим пользователю то, что пришло.
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
            "⚠️ Не удалось распознать PDF. Попробуйте ещё раз.")
        return

    data = resp.json()

    # — ветка CVOut —
    if "cv_markdown" in data:
        await _send_cv(
            chat_id=message.chat.id,
            cv_markdown=data["cv_markdown"],
            bot=bot,
            prefix="✅ Я собрал резюме!",
            reply_markup=resume_completed_kb(),
        )
        await state.clear()
        return

    # — ветка QuestionOut —
    await status_msg.edit_text(
        "✅ Резюме загружено! Теперь задам несколько уточняющих вопросов."
    )
    await _show_first_question(
        chat_id=message.chat.id,
        q=data,
        bot=bot,
        state=state,
    )


# ────────────────────────── утилиты ───────────────────────────────


async def _check_consent(tg_id: int) -> bool:
    """True ⇢ пользователь принял оба юридических согласия."""
    url = f"{settings.bots.app_url}/api/v1/auth/tg"
    async with httpx.AsyncClient(timeout=5.0) as cli:
        resp = await cli.post(url, json={"tg_id": tg_id})
    if resp.status_code != 200:
        return False
    user: Dict[str, Any] = resp.json()["user"]
    return bool(user.get("pdn_agreed") and user.get("offer_agreed"))


def _get_chosen(st_data: Dict[str, Any]) -> List[str]:
    return json.loads(st_data.get("chosen", "[]"))


async def _store_chosen(state: FSMContext, chosen: List[str]) -> None:
    await state.update_data(chosen=json.dumps(chosen))


def _is_multi(q: Dict[str, Any]) -> bool:
    return bool(q.get("multi_select"))


# ─────────────────── вывод вопроса и FSM-контекст ────────────────


async def _send_question(
    chat_id: int,
    q: Dict[str, Any],
    chosen: List[str],
    bot: Bot,
) -> Message:
    kb = None
    if q.get("inline_kb"):
        kb = build_answer_keyboard(
            session_id=q["session_id"],
            field_name=q["field_name"],
            buttons=q.get("buttons", []),
            multi_select=_is_multi(q),
            chosen=chosen,
        )
    return await bot.send_message(chat_id, q["template"], reply_markup=kb)


async def _show_first_question(
    chat_id: int,
    q: Dict[str, Any],
    bot: Bot,
    state: FSMContext,
) -> None:
    """Отображает вопрос и пишет его контекст в FSM."""
    q = dict(q)
    q["multi_select"] = _is_multi(q)

    msg = await _send_question(chat_id, q, [], bot)

    await state.set_state(DialogSG.waiting_for_answer)
    await state.set_data(
        {
            "session_id": q["session_id"],
            "field_name": q["field_name"],
            "multi_select": q["multi_select"],
            "inline_kb": q.get("inline_kb", False),
            "buttons": q.get("buttons", []),
            "template": q["template"],
            "msg_id": msg.message_id,
            "chosen": json.dumps([]),
        },
    )

# ────────────────────────── сценарий входа ─────────────────────────


async def _begin_dialog(
    chat_id: int,
    tg_id: int,
    bot: Bot,
    state: FSMContext,
) -> None:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f'{settings.bots.app_url}/api/v1/dialog/next',
            json={'user_id': tg_id},
            timeout=10.0,
        )
    if resp.status_code != 200:
        await bot.send_message(chat_id, '⚠️ Сервис временно недоступен.')
        return

    data: Dict[str, Any] = resp.json()

    if 'resume_id' in data:
        await _send_cv(
            chat_id=chat_id,
            cv_markdown=data["cv_markdown"],
            bot=bot,
            prefix="📝 Вы начали, но ещё не завершили:",
            reply_markup=resume_reset_or_continue_kb(data['resume_id']),
        )
        return

    if 'cv_markdown' in data:
        await _send_cv(
            chat_id=chat_id,
            cv_markdown=data["cv_markdown"],
            bot=bot,
            prefix="✅ Резюме уже готово:",
            reply_markup=resume_completed_kb(),
        )
        return

    if {'session_id', 'field_name', 'template'} <= data.keys():
        await _show_first_question(chat_id, data, bot, state)
        return

    await bot.send_message(chat_id, '⚠️ Сервис временно недоступен.')


@router.message(F.text == '📝 Заполнить резюме')
async def start_dialog(message: Message, bot: Bot, state: FSMContext) -> None:
    await state.clear()
    consent_txt = (
        'Как хорошо воспитанный робот, я должен получить ваше согласие '
        'на обработку персональных данных и согласие с офертой.\n\n'
        'Пожалуйста, ознакомьтесь с документом по '
        '<a href="https://tomoru.team/useragreement">ссылке</a>\n\n'
        'Вы согласны с этим документом?'
        )
    if not await _check_consent(message.from_user.id):
        await message.answer(
            consent_txt,
            parse_mode=ParseMode.HTML,
            reply_markup=consent_kb(),
        )
        return

    await _begin_dialog(message.chat.id, message.from_user.id, bot, state)


@router.callback_query(F.data.startswith('consent:'))
async def consent_cb(
    query: CallbackQuery, bot: Bot, state: FSMContext
) -> None:
    await query.answer()
    if query.data.endswith(':no'):
        await query.message.answer(
            '😔 Без согласия мы не сможем продолжить.\n'
            'При желании нажмите «📝 Заполнить резюме» ещё раз.',
        )
        await query.message.delete_reply_markup()
        return

    url = f'{settings.bots.app_url}/api/v1/users/consent'
    async with httpx.AsyncClient(timeout=5.0) as cli:
        await cli.post(url, json={'tg_id': query.from_user.id, 'agree': True})
    await query.message.delete_reply_markup()

    await _begin_dialog(query.message.chat.id, query.from_user.id, bot, state)


# ───────────────────────── ответы пользователя ──────────────────────


@router.callback_query(F.data.startswith('answer:'))
async def answer_cb(query: CallbackQuery, state: FSMContext) -> None:
    """Inline-ответ; корректно обрабатывает multi-select."""
    await query.answer()
    _, sess_id, field, value = query.data.split(':', 3)
    session_id = int(sess_id)

    st = await state.get_data()
    is_multi = st.get('multi_select', False)

    # выбор / отмена пункта
    if is_multi and value != CONFIRM_MARK:
        chosen = _get_chosen(st)
        if value in chosen:
            chosen.remove(value)
        else:
            chosen.append(value)
        await _store_chosen(state, chosen)

        await query.bot.edit_message_text(
            chat_id=query.message.chat.id,
            message_id=st['msg_id'],
            text=(
                f"{st['template']}\n"
                f"<i>Вы выбрали: {', '.join(chosen) or '—'}</i>"
            ),
            reply_markup=build_answer_keyboard(
                session_id=session_id,
                field_name=field,
                buttons=st['buttons'],
                multi_select=True,
                chosen=chosen,
            ),
            parse_mode=ParseMode.HTML,
        )
        return

    # подтверждение
    if is_multi:
        chosen = _get_chosen(st)
        if not chosen:
            await query.answer(
                'Сначала выберите минимум один вариант.',
                show_alert=True,
            )
            return
        answer_raw = ', '.join(chosen)

        # убираем старую клавиатуру
        await query.bot.edit_message_reply_markup(
            chat_id=query.message.chat.id,
            message_id=st['msg_id'],
            reply_markup=None,
        )
    else:
        answer_raw = value
        await query.bot.edit_message_text(
            chat_id=query.message.chat.id,
            message_id=query.message.message_id,
            text=(
                f"{st['template']}\n"
                f"<i>Вы выбрали: {value}</i>"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=None,
        )

    await state.set_data({'session_id': session_id, 'field_name': field})
    await _handle_answer(
        reply_target=query.message,
        tg_id=query.from_user.id,
        answer_raw=answer_raw,
        bot=query.bot,
        state=state,
    )


@router.message(DialogSG.waiting_for_answer)
async def handle_text_answer(message: Message, state: FSMContext) -> None:
    st = await state.get_data()
    # нельзя писать текст, если есть inline-варианты
    if st.get('inline_kb'):
        await message.answer('Пожалуйста, выберите вариант кнопкой 👆')
        return
    # простая валидация числовых / дат-полей
    # if st['field_name'] in {'desiredSalary', 'fixedPart', 'minSalary'}:
    #     if not message.text.isdigit():
    #         await message.answer('Введите число, пожалуйста 🔢')
    #         return
    # if st['field_name'] == 'readyInDays':
    #     if not (message.text.isdigit() and 0 < int(message.text) <= 365):
    #         await message.answer('Укажите число от 1 до 365 📅')
    #         return
    # if st['field_name'] == 'birthday':
    #     import re
    #     if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', message.text):
    #         await message.answer('Формат даты: YYYY-MM-DD 📆')
    #         return
    await _handle_answer(
        reply_target=message,
        tg_id=message.from_user.id,
        answer_raw=message.text,
        bot=message.bot,
        state=state,
    )


# ───────────────────── отправка ответа в бек-энд ────────────────────


async def _handle_answer(
    reply_target: Message | CallbackQuery,
    tg_id: int,
    answer_raw: str,
    bot: Bot,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    payload = {
        'session_id': data['session_id'],
        'user_id': tg_id,
        'field_name': data['field_name'],
        'answer_raw': answer_raw,
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f'{settings.bots.app_url}/api/v1/dialog/answer',
            json=payload,
            timeout=10.0,
        )
    if resp.status_code != 200:
        await reply_target.answer('⚠️ Ошибка при сохранении ответа.')
        return

    result: Dict[str, Any] = resp.json()

    if result.get('template') is None:
        await _send_cv(
            chat_id=reply_target.chat.id,
            cv_markdown=result["cv_markdown"],
            bot=bot,
            prefix="✅ Резюме уже готово:",
            reply_markup=resume_completed_kb(),
        )
        await state.clear()
        return

    await _show_first_question(reply_target.chat.id, result, bot, state)


# ───────────────────────── reset / continue ─────────────────────────


@router.callback_query(F.data == 'resume:reset')
async def reset_resume(
    query: CallbackQuery, state: FSMContext, bot: Bot
) -> None:
    await query.answer()
    await state.clear()

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f'{settings.bots.app_url}/api/v1/dialog/reset',
            json={'user_id': query.from_user.id},
            timeout=10.0,
        )
    if resp.status_code != 200:
        await query.message.answer('⚠️ Не удалось начать заново.')
        return

    first_q = resp.json()
    await query.message.answer('🔁 Заполняем резюме заново!')
    await _show_first_question(query.message.chat.id, first_q, bot, state)


@router.callback_query(F.data.startswith('resume:continue:'))
async def continue_resume(
    query: CallbackQuery, bot: Bot, state: FSMContext
) -> None:
    await query.answer()
    resume_id = int(query.data.split(':')[-1])
    await state.update_data(resume_id=resume_id)

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f'{settings.bots.app_url}/api/v1/dialog/resume-continue',
            json={'resume_id': resume_id, 'user_id': query.from_user.id},
            timeout=10.0,
        )
    if resp.status_code != 200:
        await query.message.answer('⚠️ Ошибка при продолжении заполнения.')
        return

    first_q = resp.json()
    await query.message.answer('✍️ Продолжаем заполнение!')
    await _show_first_question(query.message.chat.id, first_q, bot, state)
