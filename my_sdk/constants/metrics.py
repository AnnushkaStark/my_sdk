"""Определения стандартных RED-метрик Prometheus для HTTP-слоя микросервисов.

Содержит счётчики входящих запросов, ответов и исключений, гейджи активных
запросов и метаинформации о сервисе, а также гистограмму длительности обработки.
"""

from prometheus_client import Counter
from prometheus_client import Gauge
from prometheus_client import Histogram

INFO = Gauge(
    name="http_app_info",
    documentation="Application information.",
    labelnames=["service_name", "version"],
)
"""Метаинформация о запущенном микросервисе (`service_name`, `version`)."""

REQUESTS = Counter(
    name="http_requests_total",
    documentation="Total count of requests by method and path.",
    labelnames=["service_name", "path", "method"],
)
"""Общее количество входящих HTTP-запросов по методу и шаблону пути."""

REQUESTS_IN_PROGRESS = Gauge(
    name="http_requests_in_progress",
    documentation="Gauge of requests by method and path currently being processed",  # noqa: E501
    labelnames=["service_name", "path", "method"],
)
"""Количество HTTP-запросов, находящихся в обработке в текущий момент."""

REQUESTS_PROCESSING_TIME = Histogram(
    name="http_request_duration_seconds",
    documentation="Histogram of requests processing time by path (in seconds)",
    labelnames=["service_name", "path", "method"],
)
"""Гистограмма длительности обработки HTTP-запросов в секундах."""

RESPONSES = Counter(
    name="http_responses_total",
    documentation="Total count of responses by method, path and status codes.",
    labelnames=["service_name", "path", "method", "status_code"],
)
"""Общее количество HTTP-ответов в разрезе метода, шаблона пути и HTTP-статуса."""

EXCEPTIONS = Counter(
    name="http_exceptions_total",
    documentation="Total count of exceptions raised by path and exception type",  # noqa: E501
    labelnames=["service_name", "path", "method", "exception_type"],
)
"""Общее количество необработанных исключений по шаблону пути и классу ошибки."""
