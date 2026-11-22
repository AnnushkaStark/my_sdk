from __future__ import annotations

from typing import Self

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from ._otlp import _create_tracer_provider
from ._otlp import _OtlpBuilder
from ._prometheus import _init_prometheus
from ._pyroscope import _init_pyroscope


class ObservabilityBuilder:
    """Билдер для подключения систем наблюдаемости (observability) к приложению FastAPI.

    Каждый метод `with_*` сразу инициализирует соответствующий бэкенд и возвращает
    `self` (или вложенный `_OtlpBuilder`), позволяя объединять вызовы в цепочку.
    Все бэкенды опциональны — подключайте только те, что используются в вашей инфраструктуре.

    Example:
        Базовая настройка OTLP-трассировки, Prometheus-метрик и профилирования Pyroscope:

        ```python
        ObservabilityBuilder(
            app,
            service_name="my-service",
            service_version="1.0.0",
            excluded_urls=frozenset({"/health", "/metrics"}),
        ).with_otlp("alloy:4317")
            .with_logging()
            .with_httpx()
            .with_fastapi()
            .done()
        .with_prometheus()
        .with_pyroscope("pyroscope")
        ```

        Переопределение имени сервиса для отдельного бэкенда:

        ```python
        ObservabilityBuilder(
            app, service_name="my-service", service_version="1.0.0"
        )
            .with_otlp("alloy:4317")
                .with_logging()
                .with_fastapi()
                .done()
            .with_prometheus()
            .with_pyroscope(
                "pyroscope", 4040, service_name="my-service-profiling"
            )
        ```
    """

    def __init__(
        self,
        app: FastAPI,
        service_name: str,
        service_version: str,
        *,
        excluded_urls: frozenset[str] = frozenset(),
    ) -> None:
        """Инициализирует билдер наблюдаемости для FastAPI-приложения.

        Args:
            app: Экземпляр приложения `FastAPI`.
            service_name: Имя микросервиса для метаданных трассировки и профилирования.
            service_version: Версия микросервиса (например, `"1.0.0"`).
            excluded_urls: Набор URL-путей, исключаемых из сбора телеметрии.
        """
        self._app = app
        self._service_name = service_name
        self._service_version = service_version
        self._excluded_urls = excluded_urls

    def with_otlp(
        self,
        endpoint: str,
        *,
        service_name: str | None = None,
        service_version: str | None = None,
        insecure: bool = True,
    ) -> _OtlpBuilder:
        """Создаёт и регистрирует `TracerProvider` с экспортом трейсов по протоколу OTLP.

        Args:
            endpoint: Адрес OTLP-коллектора или агента (например, `"alloy:4317"`).
            service_name: Переопределение имени сервиса для OTLP (если отличается от базового).
            service_version: Переопределение версии сервиса для OTLP.
            insecure: Использовать ли незашифрованное gRPC-соединение (по умолчанию `True`).

        Returns:
            Вложенный билдер `_OtlpBuilder` для инструментации FastAPI, HTTPX и логов.
        """
        tracer_provider = _create_tracer_provider(
            endpoint=endpoint,
            service_name=service_name or self._service_name,
            service_version=service_version or self._service_version,
            insecure=insecure,
        )
        trace.set_tracer_provider(tracer_provider)
        return _OtlpBuilder(parent=self, app=self._app, tracer_provider=tracer_provider)

    def with_otlp_provider(self, tracer_provider: TracerProvider) -> _OtlpBuilder:
        """Подключает уже сконфигурированный внешний `TracerProvider`.

        Args:
            tracer_provider: Готовый экземпляр провайдера трассировки OpenTelemetry.

        Returns:
            Вложенный билдер `_OtlpBuilder` для дальнейшей настройки инструментаций.
        """
        trace.set_tracer_provider(tracer_provider)
        return _OtlpBuilder(parent=self, app=self._app, tracer_provider=tracer_provider)

    def with_prometheus(self) -> Self:
        """Подключает сбор HTTP-метрик и эндпоинт `/metrics` для Prometheus.

        Returns:
            Текущий экземпляр `ObservabilityBuilder` для продолжения цепочки вызовов.
        """
        _init_prometheus(self._app)
        return self

    def with_pyroscope(
        self,
        host: str,
        port: int = 4040,
        *,
        secure: bool = False,
        service_name: str | None = None,
    ) -> Self:
        """Подключает непрерывное профилирование (continuous profiling) в Pyroscope.

        Args:
            host: Хост сервера Pyroscope.
            port: Порт сервера Pyroscope (по умолчанию `4040`).
            secure: Использовать ли HTTPS при отправке профилей (по умолчанию `False`).
            service_name: Переопределение имени приложения в Pyroscope.

        Returns:
            Текущий экземпляр `ObservabilityBuilder` для продолжения цепочки вызовов.
        """
        _init_pyroscope(
            application_name=service_name or self._service_name,
            host=host,
            port=port,
            secure=secure,
        )
        return self
