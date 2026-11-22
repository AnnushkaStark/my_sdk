from datetime import date
from datetime import datetime
from datetime import time
from typing import Annotated
from typing import Any
from typing import TypeVar

import phonenumbers
from fastapi import File
from fastapi import UploadFile
from pydantic import AfterValidator
from pydantic import EmailStr

T = TypeVar("T")


def get_unique_values_list[T](lst: list[T]) -> list[T]:
    """Удаляет дубликаты из списка с сохранением порядка элементов."""
    return list(dict.fromkeys(lst))


UniqueValuesList = Annotated[list[Any], AfterValidator(get_unique_values_list)]
"""Список с автоматическим удалением дубликатов при валидации Pydantic."""


def normalize_phone(value: str, region: str = "RU") -> str:
    """Проверяет номер телефона и приводим его к международному формату E.164.

    Args:
        value: Исходная строка с номером телефона.
        region: Код региона по умолчанию (по умолчанию `"RU"`).

    Returns:
        Нормализованный номер в формате E.164 (например, `"+79991234567"`).

    Raises:
        ValueError: Если строка не является валидным номером телефона.
    """
    try:
        parsed = phonenumbers.parse(value, region)
    except phonenumbers.NumberParseException as exc:
        raise ValueError(f"Invalid phone number: {value}") from exc

    if not phonenumbers.is_valid_number(parsed):
        raise ValueError(f"Invalid phone number: {value}")

    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


ValidPhone = Annotated[str, AfterValidator(normalize_phone)]
"""Валидированный номер телефона в стандарте E.164."""


def get_lower_mail(email: EmailStr) -> EmailStr:
    """Приводит адрес электронной почты к нижнему регистру."""
    return email.lower()


LowerEmailStr = Annotated[EmailStr, AfterValidator(get_lower_mail)]
"""Email-адрес, автоматически приведённый к нижнему регистру."""


def validate_password(password: str) -> str:
    """Проверяет базовые требования к формату пароля (длина 8–128 символов, без пробелов)."""
    if (
        not isinstance(password, str)
        or not 8 <= len(password) <= 128
        or any(character.isspace() for character in password)
    ):
        raise ValueError("invalid password format")
    return password


ValidPassword = Annotated[str, AfterValidator(validate_password)]
"""Строка пароля, прошедшая проверку длины (8–128) и отсутствия пробельных символов."""


def title_string(value: str) -> str:
    """Очищает строку от пробелов/дефисов и приводит к Title Case."""
    return value.strip().replace("-", "").replace(" ", "").title()


TitleString = Annotated[str, AfterValidator(title_string)]
"""Нормализованная строка в формате Title Case без пробелов и дефисов."""


def contact_str(value: str) -> str:
    """Определяет тип контакта (email или телефон) и нормализует его."""
    if "@" in value:
        return value.lower()
    return normalize_phone(value=value)


ContactStr = Annotated[str, AfterValidator(contact_str)]
"""Универсальное контактное поле: нормализует либо email, либо телефон в E.164."""


def get_date_iso(dt: date) -> str:
    """Сериализует объект `date` в строку формата ISO 8601."""
    return dt.isoformat()


IsoformatDate = Annotated[date, AfterValidator(get_date_iso)]
"""Дата, автоматически преобразуемая в ISO-строку (`YYYY-MM-DD`)."""


def date_time_iso(dt_time: datetime) -> str:
    """Сериализует объект `datetime` в строку формата ISO 8601."""
    return dt_time.isoformat()


DateTimeIsoformat = Annotated[datetime, AfterValidator(date_time_iso)]
"""Дата и время, автоматически преобразуемые в ISO-строку."""


def time_iso(tm: time) -> str:
    """Сериализует объект `time` в строку формата ISO 8601."""
    return tm.isoformat()


TimeIsoformat = Annotated[time, AfterValidator(time_iso)]
"""Время, автоматически преобразуемое в ISO-строку."""


FileForm = Annotated[UploadFile | None, File()]
"""Аннотация для опциональной загрузки файла в multipart/form-data эндпоинтах FastAPI."""
