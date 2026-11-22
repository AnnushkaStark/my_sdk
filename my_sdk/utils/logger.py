import contextvars
import json
import logging
import logging.config
from dataclasses import dataclass
from typing import Any
from typing import Literal
from typing import override

type LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", 10, 20, 30, 40, 50]

request_id_ctx_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")

_APP_FMT = (
    "time=%(asctime)s "
    "level=%(levelname)s "
    "name=%(name)s "
    "pid=%(process)d "
    "caller=%(module)s:%(lineno)d "
    "request_id=%(request_id)s "
    "trace_id=%(otelTraceID)s "
    "span_id=%(otelSpanID)s "
    "msg=%(message)s"
)

# fmt: off
_SYSTEM_FMT = (
    "time=%(asctime)s "
    "level=%(levelname)s "
    "name=%(name)s "
    "pid=%(process)d "
    "caller=%(module)s:%(lineno)d "
    "msg=%(message)s"
)
# fmt: on

_DATE_FMT = "%Y-%m-%dT%H:%M:%S"


class LogFormatter(logging.Formatter):
    """Экранирует поле msg в JSON, чтобы каждая запись лога оставалась в одну строку."""

    @override
    def formatMessage(self, record: logging.LogRecord) -> str:
        record.message = json.dumps(record.message, ensure_ascii=False)
        return super().formatMessage(record)


class ContextFilter(logging.Filter):
    """Добавляет в запись лога request_id и безопасные значения по умолчанию для OpenTelemetry."""

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx_var.get("")
        if not hasattr(record, "otelTraceID"):
            record.otelTraceID = ""
        if not hasattr(record, "otelSpanID"):
            record.otelSpanID = ""
        return True


def get_default_logging_config(log_level: LogLevel = "INFO") -> dict[str, Any]:
    """Формирует словарь конфигурации для `logging.config.dictConfig`.

    Args:
        log_level: Минимальный уровень логирования (по умолчанию `"INFO"`).

    Returns:
        Словарь конфигурации логгеров, хендлеров и форматтеров.
    """
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "context": {"()": ContextFilter},
        },
        "formatters": {
            "app": {
                "()": LogFormatter,
                "format": _APP_FMT,
                "datefmt": _DATE_FMT,
            },
            "system": {
                "()": LogFormatter,
                "format": _SYSTEM_FMT,
                "datefmt": _DATE_FMT,
            },
        },
        "handlers": {
            "stdout_app": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "app",
                "filters": ["context"],
            },
            "stdout_system": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "system",
            },
            "stderr": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
                "formatter": "system",
            },
        },
        "root": {
            "level": log_level,
            "handlers": ["stdout_system"],
        },
        "loggers": {
            "app": {
                "level": log_level,
                "handlers": ["stdout_app"],
                "propagate": False,
            },
            "system": {
                "level": log_level,
                "handlers": ["stdout_system"],
                "propagate": False,
            },
            "uvicorn": {"handlers": [], "propagate": True},
            "uvicorn.error": {"handlers": ["stderr"], "propagate": False},
            "uvicorn.access": {"handlers": [], "propagate": False},
            "gunicorn": {"handlers": [], "propagate": True},
            "gunicorn.error": {"handlers": ["stderr"], "propagate": False},
            "gunicorn.access": {"handlers": [], "propagate": False},
        },
    }


def configure_default_logging(log_level: LogLevel = "INFO") -> None:
    """Инициализирует стандартную конфигурацию логирования для микросервиса.

    Args:
        log_level: Минимальный уровень логирования (по умолчанию `"INFO"`).
    """
    logging.config.dictConfig(get_default_logging_config(log_level))


@dataclass(frozen=True, slots=True)
class Logger:
    """Контейнер разделённых логгеров для бизнес-событий и системных сообщений.

    Attributes:
        app: Логгер приложения с контекстом запроса (`request_id`, `trace_id`, `span_id`).
        system: Системный логгер для инфраструктуры и фоновых процессов.
    """

    app: logging.Logger
    system: logging.Logger


log = Logger(
    app=logging.getLogger("app"),
    system=logging.getLogger("system"),
)
