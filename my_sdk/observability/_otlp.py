from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING
from typing import Self

from fastapi import FastAPI
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pyroscope.otel import PyroscopeSpanProcessor

if TYPE_CHECKING:
    from sqlalchemy import Engine

    from .builder import ObservabilityBuilder


def _create_tracer_provider(
    endpoint: str,
    service_name: str,
    service_version: str,
    insecure: bool,
) -> TracerProvider:
    """Создаёт `TracerProvider` с OTLP gRPC-экспортёром и интеграцией Pyroscope.

    Args:
        endpoint: Адрес OTLP-коллектора или агента (например, `"alloy:4317"`).
        service_name: Имя микросервиса в атрибуте `service.name`.
        service_version: Версия микросервиса в атрибуте `service.version`.
        insecure: Использовать ли незашифрованное gRPC-соединение.

    Returns:
        Настроенный провайдер трассировки `TracerProvider`.
    """
    resource = Resource.create(
        attributes={
            "service.name": service_name,
            "service.version": service_version,
        }
    )
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(endpoint=endpoint, insecure=insecure),
        ),
    )
    tracer_provider.add_span_processor(PyroscopeSpanProcessor())
    return tracer_provider


class _OtlpBuilder:
    """Билдер для подключения OpenTelemetry-инструментаторов к компонентам приложения.

    Вызывайте методы `with_*` для включения нужных инструментаторов, а в конце
    вызовите `done()`, чтобы вернуться в родительский `ObservabilityBuilder`.

    Example:
        ```python
        ObservabilityBuilder(app, "my-service", "1.0.0")
            .with_otlp("alloy:4317")
                .with_logging()
                .with_httpx()
                .with_sqlalchemy(engine)
                .with_fastapi()
                .done()
            .with_prometheus()
            .with_pyroscope("pyroscope")
        ```
    """

    def __init__(
        self,
        parent: ObservabilityBuilder,
        app: FastAPI,
        tracer_provider: TracerProvider,
    ) -> None:
        """Инициализирует вложенный билдер OpenTelemetry-инструментации.

        Args:
            parent: Родительский экземпляр `ObservabilityBuilder`.
            app: Экземпляр приложения `FastAPI`.
            tracer_provider: Активный провайдер трассировки `TracerProvider`.
        """
        self._parent = parent
        self._app = app
        self._tracer_provider = tracer_provider

    def with_logging(self, *, set_logging_format: bool = True) -> Self:
        """Подключает инъекцию `trace_id` и `span_id` в стандартный `logging`.

        Args:
            set_logging_format: Переопределять ли форматтер логов автоматически.

        Returns:
            Текущий экземпляр `_OtlpBuilder` для продолжения цепочки вызовов.
        """
        LoggingInstrumentor().instrument(set_logging_format=set_logging_format)
        return self

    def with_httpx(self) -> Self:
        """Подключает автоматическую трассировку исходящих HTTP-запросов `httpx`.

        Returns:
            Текущий экземпляр `_OtlpBuilder` для продолжения цепочки вызовов.
        """
        HTTPXClientInstrumentor().instrument()
        return self

    def with_sqlalchemy(
        self,
        engine: Engine,
        *,
        enable_commenter: bool = False,
        commenter_options: dict[str, bool] | None = None,
        enable_attribute_commenter: bool = False,
    ) -> Self:
        """Подключает трассировку SQL-запросов для движка SQLAlchemy.

        Для асинхронного `AsyncEngine` передавайте `async_engine.sync_engine`.

        Args:
            engine: Синхронный движок SQLAlchemy (`Engine` или `async_engine.sync_engine`).
            enable_commenter: Добавлять ли метаданные трейса в SQL-комментарии.
            commenter_options: Словарь настроек SQL-комментатора.
            enable_attribute_commenter: Добавлять ли атрибуты спана в SQL-комментарии.

        Returns:
            Текущий экземпляр `_OtlpBuilder` для продолжения цепочки вызовов.
        """
        SQLAlchemyInstrumentor().instrument(
            engine=engine,
            enable_commenter=enable_commenter,
            commenter_options=commenter_options or {},
            enable_attribute_commenter=enable_attribute_commenter,
        )
        return self

    def with_fastapi(self, excluded_urls: Iterable[str] | None = None) -> Self:
        """Подключает автоматическую трассировку входящих HTTP-запросов FastAPI.

        Args:
            excluded_urls: Коллекция URL-путей, исключаемых из трассировки
                (например, `["/health", "/metrics"]`).

        Returns:
            Текущий экземпляр `_OtlpBuilder` для продолжения цепочки вызовов.
        """
        FastAPIInstrumentor.instrument_app(
            self._app,
            tracer_provider=self._tracer_provider,
            excluded_urls=",".join(excluded_urls) if excluded_urls else None,
        )
        return self

    def done(self) -> ObservabilityBuilder:
        """Завершает настройку OpenTelemetry и возвращает родительский `ObservabilityBuilder`.

        Returns:
            Экземпляр `ObservabilityBuilder` для подключения остальных бэкендов.
        """
        return self._parent
