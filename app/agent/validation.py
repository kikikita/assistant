import re
from datetime import datetime
from typing import Any, Tuple

_NUMERIC_RE = re.compile(r"^\d[\d\s]*$")


def _is_numeric(value: Any) -> bool:
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        return bool(_NUMERIC_RE.fullmatch(value.strip()))
    return False


def _is_date(value: str) -> bool:
    for fmt in ("%d.%m.%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            datetime.strptime(value, fmt)
            return True
        except ValueError:
            continue
    return False


def validate(field: str, value: Any) -> Tuple[bool, str]:
    """
    Проверяет значение. Возвращает (ok, err_msg).
    err_msg == "" → всё в порядке.
    """
    field = field.lower()

    # ---- Доход --------------------------------------------------------------
    if field in {"desired_income", "salary", "salary_expectation"}:
        if _is_numeric(value):
            return True, ""
        return False, _err("Система: Доход должен быть числом в рублях. Не проси пользователя исправить, вызови инструмент снова с корректным инсутрментом.")

    # ---- Имя/фамилия --------------------------------------------------------
    if field in {"first_name", "last_name", "middle_name"}:
        if isinstance(value, str) and value.isalpha():
            return True, ""
        return False, _err("Имя должно содержать только буквы")

    # ---- Дата рождения ------------------------------------------------------
    if field in {"birth_date", "date_of_birth"}:
        if isinstance(value, str) and _is_date(value):
            return True, ""
        return False, _err("Дата должна быть в формате ДД.ММ.ГГГГ")

    # ---- По умолчанию — OK --------------------------------------------------
    return True, ""


def _err(msg: str) -> str:
    return f"{ 'error': {msg} }"

