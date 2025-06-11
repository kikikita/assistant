from aiogram.fsm.state import StatesGroup, State


class Basic(StatesGroup):
    basic = State()


class DialogSG(StatesGroup):
    """
    Состояния для диалога заполнения резюме:
    - waiting_for_answer: бот ожидает текстовый ответ или нажатие кнопки
    """
    waiting_for_answer = State()
