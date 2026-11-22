import logging
import time
import uuid
from typing import Final

from starlette import status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from my_sdk.utils.logger import log
from my_sdk.utils.logger import request_id_ctx_var

REQUEST_ID_HEADER: Final[str] = "X-Request-Id"
REAL_IP_HEADER: Final[str] = "x-real-ip"
_SECONDS_TO_MS: Final[int] = 1000

# fmt: off
_BASE_FMT: Final[str] = (
    "ip=%s | "
    "method=%s | "
    "url=%s | "
    "status=%d | "
    "dur=%dms | "
    "ua=%s | "
    "size=%d bytes"
)

_ACCESS_INFO_FMT: Final[str] = "HTTP | SUCCESS | " + _BASE_FMT
_ACCESS_WARNING_FMT: Final[str] = "HTTP | CLIENT ERROR | " + _BASE_FMT
_ACCESS_ERROR_FMT: Final[str] = "HTTP | SERVER ERROR | " + _BASE_FMT
# fmt: on


class RequestAccessMiddleware(BaseHTTPMiddleware):
    """Middleware для сквозной трассировки (`X-Request-Id`) и логирования HTTP-запросов.

    Проставляет и возвращает заголовок `X-Request-Id`, сохраняет его в `contextvars`
    для всех логов внутри запроса, замеряет длительность обработки в миллисекундах
    и пишет структурированный access-лог с уровнем в зависимости от HTTP-статуса.
    """

    def __init__(
        self,
        app: ASGIApp,
        excluded_urls: frozenset[str] = frozenset(),
        logger: logging.Logger = log.app,
    ) -> None:
        """Инициализирует middleware логирования входящих запросов.

        Args:
            app: Следующий ASGI-обработчик в цепочке приложения.
            excluded_urls: Набор URL-путей, которые не нужно логировать
                (например, `frozenset({"/health", "/metrics"})`).
            logger: Экземпляр логгера (по умолчанию `log.app`).
        """
        super().__init__(app)
        self._excluded_urls = excluded_urls
        self._logger = logger

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Обрабатывает входящий HTTP-запрос, логирует метрики и пробрасывает `X-Request-Id`.

        Args:
            request: Входящий объект запроса Starlette/FastAPI.
            call_next: Функция передачи управления следующему обработчику.

        Returns:
            HTTP-ответ `Response` с добавленным заголовком `X-Request-Id`.
        """
        if request.url.path in self._excluded_urls:
            return await call_next(request)

        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        token = request_id_ctx_var.set(request_id)

        ip = request.headers.get(REAL_IP_HEADER) or (request.client.host if request.client else None) or "unknown"
        method = request.method
        path = request.url.path
        query = request.url.query
        full_url = f"{path}?{query}" if query else path
        user_agent = request.headers.get("user-agent", "-")

        start_time = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_ctx_var.reset(token)

        duration_ms = int((time.perf_counter() - start_time) * _SECONDS_TO_MS)
        status_code = response.status_code
        size = int(response.headers.get("content-length") or 0)

        response.headers[REQUEST_ID_HEADER] = request_id

        if status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
            self._logger.error(
                _ACCESS_ERROR_FMT,
                ip,
                method,
                full_url,
                status_code,
                duration_ms,
                user_agent,
                size,
            )
        elif status_code >= status.HTTP_400_BAD_REQUEST:
            self._logger.warning(
                _ACCESS_WARNING_FMT,
                ip,
                method,
                full_url,
                status_code,
                duration_ms,
                user_agent,
                size,
            )
        else:
            self._logger.info(
                _ACCESS_INFO_FMT,
                ip,
                method,
                full_url,
                status_code,
                duration_ms,
                user_agent,
                size,
            )

        return response
