from typing import List, Dict, Optional, Any
from pydantic import BaseModel


class QuestionOut(BaseModel):
    """
    Ответ от сервера с данными для следующего вопроса в диалоге.

    Attributes:
        session_id (int): Идентификатор активной сессии.
        field_name (str): Название поля, которое нужно заполнить.
        template (str): Шаблон текста вопроса.
        inline_kb (bool): Нужно ли отображать inline-кнопки.
        buttons (List[str]): Список возможных вариантов ответа.
    """
    session_id: int
    field_name: str
    template: str
    inline_kb: bool = False
    buttons: List[str] = []
    multi_select: bool = False


class Config:
    orm_mode = True


class AnswerIn(BaseModel):
    """
    Запрос от клиента с ответом пользователя на вопрос.

    Attributes:
        session_id (int): Идентификатор сессии.
        user_id (int): Telegram ID пользователя.
        field_name (str): Название заполняемого поля.
        answer_raw (str): Ответ пользователя.
    """
    user_id: int
    field_name: str
    answer_raw: str
    session_id: Optional[int] = None


class CVOut(BaseModel):
    """
    Полный ответ с готовым резюме.

    Attributes:
        cv_markdown (str): Отформатированное резюме.
        fields (Dict[str, str]): Значения полей резюме.
    """
    cv_markdown: str
    fields: Dict[str, Any]


class PartialCVOut(BaseModel):
    """
    Ответ с частично заполненным резюме.

    Attributes:
        cv_markdown (str): Текущее содержимое резюме.
        resume_id (int): Идентификатор резюме.
    """
    cv_markdown: str
    resume_id: int


class TextOut(BaseModel):
    template: str
