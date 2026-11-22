import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Match
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR
from starlette.types import ASGIApp

from my_sdk.constants.metrics import EXCEPTIONS
from my_sdk.constants.metrics import INFO
from my_sdk.constants.metrics import REQUESTS
from my_sdk.constants.metrics import REQUESTS_IN_PROGRESS
from my_sdk.constants.metrics import REQUESTS_PROCESSING_TIME
from my_sdk.constants.metrics import RESPONSES


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware для автоматического сбора RED-метрик Prometheus в FastAPI/Starlette.

    Фиксирует общее число входящих запросов, количество активных запросов в обработке,
    время выполнения запроса (`Histogram`), количество ответов по HTTP-статусам,
    необработанные исключения по типам и метаинформацию о версии сервиса (`Gauge`).
    В качестве метки `path` использует шаблон маршрута (например, `/items/{item_id}`),
    чтобы избежать высокой кардинальности метрик.
    """

    def __init__(
        self,
        app: ASGIApp,
        service_name: str,
        version: str,
        excluded_urls: frozenset[str] = frozenset(),
    ) -> None:
        """Инициализирует middleware сбора Prometheus-метрик.

        Args:
            app: Следующий ASGI-обработчик в цепочке приложения.
            service_name: Имя микросервиса для лейбла `service_name`.
            version: Версия микросервиса для метрики `INFO`.
            excluded_urls: Набор URL-путей, исключаемых из сбора метрик
                (например, `frozenset({"/health", "/metrics"})`).
        """
        super().__init__(app)
        self._service_name = service_name
        self._excluded_urls = excluded_urls
        INFO.labels(service_name=service_name, version=version).set(1)

    @staticmethod
    def _get_route_path(request: Request) -> str | None:
        """Возвращает шаблон пути маршрута (например, `/api/items/{item_id}`) или `None`.

        Args:
            request: Входящий объект запроса Starlette/FastAPI.

        Returns:
            Строка шаблона маршрута при полном совпадении (`Match.FULL`) или `None`.
        """
        for route in request.app.routes:
            match, _ = route.matches(request.scope)
            if match == Match.FULL:
                return route.path
        return None

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Обрабатывает HTTP-запрос и обновляет счётчики, гистограммы и гейджи Prometheus.

        Args:
            request: Входящий объект запроса Starlette/FastAPI.
            call_next: Функция передачи управления следующему обработчику.

        Returns:
            Сформированный HTTP-ответ `Response`.
        """
        if request.url.path in self._excluded_urls:
            return await call_next(request)

        if (path := self._get_route_path(request)) is None:
            return await call_next(request)

        service_name = self._service_name
        method = request.method

        REQUESTS.labels(service_name=service_name, method=method, path=path).inc()
        REQUESTS_IN_PROGRESS.labels(service_name=service_name, method=method, path=path).inc()
        before_time = time.perf_counter()
        status_code = HTTP_500_INTERNAL_SERVER_ERROR
        try:
            response = await call_next(request)

        except BaseException as e:
            EXCEPTIONS.labels(
                service_name=service_name,
                method=method,
                path=path,
                exception_type=type(e).__name__,
            ).inc()
            raise

        else:
            status_code = response.status_code
            REQUESTS_PROCESSING_TIME.labels(service_name=service_name, method=method, path=path).observe(
                time.perf_counter() - before_time
            )

        finally:
            RESPONSES.labels(
                service_name=service_name,
                method=method,
                path=path,
                status_code=status_code,
            ).inc()
            REQUESTS_IN_PROGRESS.labels(service_name=service_name, method=method, path=path).dec()

        return response
