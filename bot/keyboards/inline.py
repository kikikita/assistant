from typing import Iterable

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def consent_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text='✅ Согласен', callback_data='consent:yes')
    kb.button(text='❌ Не согласен', callback_data='consent:no')
    kb.adjust(2)
    return kb.as_markup()


# ─────────────────── generic answer keyboard ────────────────────────

def _decorate(btn: str, chosen: Iterable[str]) -> str:
    """Добавляем галочку к уже выбранным вариантам."""
    return f'☑️ {btn}' if btn in chosen else btn


def build_answer_keyboard(
    *,
    session_id: int,
    field_name: str,
    buttons: list[str],
    multi_select: bool = False,
    chosen: list[str] | None = None,
) -> InlineKeyboardMarkup:
    """
    Формирует inline-клавиатуру.

    • варианты располагаются по две кнопки в ряд;
    • «✅ Подтвердить» всегда отдельной, последней строкой.
    """
    chosen = chosen or []
    kb = InlineKeyboardBuilder()

    # ― варианты ―
    for b in buttons:
        kb.button(
            text=_decorate(b, chosen),
            callback_data=f'answer:{session_id}:{field_name}:{b}',
        )

    # список ширин строк для кнопок-вариантов: 2-2-…-(1)
    width_list: list[int] = [2] * (len(buttons) // 2)
    if len(buttons) % 2:
        width_list.append(1)

    # ― «Подтвердить» (только при multi-select) ―
    if multi_select:
        kb.button(
            text='✅ Подтвердить',
            callback_data=f'answer:{session_id}:{field_name}:__confirm__',
        )
        width_list.append(1)

    kb.adjust(*width_list)
    return kb.as_markup()


# ───────────────────────── резюме-кнопки ────────────────────────────

def resume_completed_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text='🔁 Заполнить заново', callback_data='resume:reset')
    return kb.as_markup()


def resume_reset_or_continue_kb(resume_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text='Продолжить заполнение',
        callback_data=f'resume:continue:{resume_id}',
    )
    kb.button(text='Заполнить заново', callback_data='resume:reset')
    kb.adjust(1)
    return kb.as_markup()
