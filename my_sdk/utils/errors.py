import enum
from collections.abc import Iterable
from typing import Any

from fastapi.requests import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class Error(BaseModel):
    """Базовая схема ответа об ошибке для OpenAPI-документации."""

    detail: str


class BaseError(BaseModel):
    """Стандартная модель тела HTTP-ответа при возникновении ошибки."""

    detail: str


class DomainError(Exception):
    """Базовое доменное исключение бизнес-логики.

    Используется для выбрасывания типизированных ошибок из сервисного слоя
    с последующим автоматическим маппингом в HTTP-статусы.

    Attributes:
        code: Код ошибки из перечисления (`enum.Enum`), значение которого отдаётся клиенту.
    """

    code: enum.Enum

    def __init__(self, code: enum.Enum, message: str | None = None) -> None:
        """Инициализирует доменное исключение.

        Args:
            code: Элемент перечисления с кодом/описанием ошибки.
            message: Необязательное внутреннее сообщение для логов и отладки.
        """
        self.code = code
        super().__init__(message or str(code.value))


ERROR_STATUS_MAP: dict[enum.Enum, int] = {}
"""Глобальный реестр соответствия доменных кодов ошибок HTTP-статусам."""


async def domain_error_exception_handler(
    request: Request,
    exc: DomainError,
) -> JSONResponse:
    """Глобальный обработчик исключений `DomainError` для FastAPI.

    Преобразует доменное исключение в JSON-ответ со статус-кодом из
    `ERROR_STATUS_MAP` (или `500`, если код не зарегистрирован).

    Args:
        request: Входящий HTTP-запрос FastAPI.
        exc: Перехваченное доменное исключение.

    Returns:
        JSON-ответ формата `{"detail": "<значение кода>"}`.
    """
    status_code = ERROR_STATUS_MAP.get(exc.code, 500)

    return JSONResponse(
        status_code=status_code,
        content={"detail": exc.code.value},
    )


def create_response_schema(description: str) -> dict[str, Any]:
    """Создаёт описание схемы ответа с ошибкой для декоратора роута FastAPI.

    Args:
        description: Текстовое описание возможных ошибок для OpenAPI/Swagger.

    Returns:
        Словарь конфигурации ответа с моделью `BaseError`.
    """
    return {
        "model": BaseError,
        "description": description,
    }


def _format_description(codes: Iterable[enum.Enum]) -> str:
    """Форматирует список кодов ошибок в HTML-список для Swagger UI."""
    return "".join(f"<br />{code.value}" for code in codes)[len("<br />") :]


def errs(
    **_codes: enum.Enum | Iterable[enum.Enum],
) -> dict[int, dict[str, Any]]:
    """Генерирует словарь `responses` для эндпоинтов FastAPI из кодов ошибок.

    Позволяет декларативно описывать ошибки в роутах через именованные аргументы
    вида `e400=...`, `e404=...`, `e409=...` и автоматически проверяет, что один
    и тот же код ошибки не продублирован в разных HTTP-статусах.

    Args:
        **_codes: Именованные аргументы формата `e<HTTP_STATUS>`, принимающие
            один элемент `enum.Enum` или коллекцию таких элементов.

    Returns:
        Словарь формата `{status_code: {"model": BaseError, "description": ...}}`
        для передачи в параметр `responses` роутера FastAPI.

    Raises:
        RuntimeError: Если один и тот же код ошибки передан более одного раза.
    """
    ret: dict[int, dict[str, Any]] = {}
    processed: set[enum.Enum] = set()

    for status_codes, codes in _codes.items():
        if not isinstance(codes, Iterable):
            codes = (codes,)

        codes_tuple = tuple(codes)
        if set(codes_tuple) & processed:
            raise RuntimeError("Error codes duplicated")

        processed |= set(codes_tuple)
        status_code = int(status_codes.strip("e"))

        ret[status_code] = {
            "model": BaseError,
            "description": _format_description(codes_tuple),
        }

    return ret
